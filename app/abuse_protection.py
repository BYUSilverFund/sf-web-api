"""Bounded, auditable protection for expensive API routes.

The limits are process-local. They protect each Elastic Beanstalk instance from
bursts; an edge/WAF limit is still required for a shared, account-wide limit.
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteLimit:
    requests_per_minute: int
    max_concurrent_requests: int


class RequestBodyTooLarge(Exception):
    """Raised before an oversized request is passed to an application handler."""


class AbuseProtectionMiddleware:
    """Apply body, rate, concurrency, and audit controls to costly routes."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_request_body_bytes: int,
        chat_limit: RouteLimit,
        export_limit: RouteLimit,
        trust_forwarded_for: bool = True,
    ) -> None:
        self.app = app
        self.max_request_body_bytes = max_request_body_bytes
        self.limits = {"chat": chat_limit, "export": export_limit}
        self.trust_forwarded_for = trust_forwarded_for
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._rate_lock = asyncio.Lock()
        self._semaphores = {
            route_group: asyncio.Semaphore(limit.max_concurrent_requests)
            for route_group, limit in self.limits.items()
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        route_group = self._route_group(scope["path"])
        request_id = self._request_id(scope)
        client_ip = self._client_ip(scope)
        content_length = self._content_length(scope)

        if content_length is not None and content_length > self.max_request_body_bytes:
            await self._reject(
                scope,
                receive,
                send,
                request_id,
                route_group,
                client_ip,
                413,
                "Request body is too large.",
            )
            return

        semaphore: asyncio.Semaphore | None = None
        if route_group is not None:
            if not await self._allow_request(route_group, client_ip):
                await self._reject(
                    scope,
                    receive,
                    send,
                    request_id,
                    route_group,
                    client_ip,
                    429,
                    "Rate limit exceeded.",
                    retry_after=60,
                )
                return

            semaphore = self._semaphores[route_group]
            if semaphore.locked():
                await self._reject(
                    scope,
                    receive,
                    send,
                    request_id,
                    route_group,
                    client_ip,
                    429,
                    "Service is busy. Please retry shortly.",
                    retry_after=1,
                )
                return
            await semaphore.acquire()

        started_at = time.perf_counter()
        response_status = 500
        response_started = False
        received_bytes = 0

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_request_body_bytes:
                    raise RequestBodyTooLarge
            return message

        async def audited_send(message: Message) -> None:
            nonlocal response_status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                response_status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, limited_receive, audited_send)
        except RequestBodyTooLarge:
            if not response_started:
                response_status = 413
                response = JSONResponse(
                    {"detail": "Request body is too large.", "requestId": request_id},
                    status_code=413,
                    headers={"X-Request-ID": request_id},
                )
                await response(scope, receive, send)
            else:
                logger.warning(
                    "event=request_body_limit_after_response request_id=%s route_group=%s",
                    request_id,
                    route_group,
                )
        finally:
            if semaphore is not None:
                semaphore.release()
            if route_group is not None:
                logger.info(
                    "event=api_audit request_id=%s route_group=%s client_ip=%s "
                    "status=%s duration_ms=%.2f",
                    request_id,
                    route_group,
                    client_ip,
                    response_status,
                    (time.perf_counter() - started_at) * 1000,
                )

    @staticmethod
    def _route_group(path: str) -> str | None:
        if path == "/chat/stream":
            return "chat"
        if "/csv" in path:
            return "export"
        return None

    @staticmethod
    def _request_id(scope: Scope) -> str:
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-request-id" and 0 < len(value) <= 128:
                return value.decode("ascii", errors="ignore")
        return str(uuid.uuid4())

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    def _client_ip(self, scope: Scope) -> str:
        if self.trust_forwarded_for:
            for name, value in scope.get("headers", []):
                if name.lower() == b"x-forwarded-for":
                    forwarded_for = value.decode("ascii", errors="ignore")
                    if forwarded_for:
                        # The ALB appends its immediate peer as the final value.
                        return forwarded_for.rsplit(",", maxsplit=1)[-1].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"

    async def _allow_request(self, route_group: str, client_ip: str) -> bool:
        now = time.monotonic()
        request_window = self._requests[(route_group, client_ip)]
        cutoff = now - 60
        async with self._rate_lock:
            while request_window and request_window[0] <= cutoff:
                request_window.popleft()
            if len(request_window) >= self.limits[route_group].requests_per_minute:
                return False
            request_window.append(now)
            return True

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        request_id: str,
        route_group: str | None,
        client_ip: str,
        status_code: int,
        detail: str,
        retry_after: int | None = None,
    ) -> None:
        headers = {"X-Request-ID": request_id}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        logger.warning(
            "event=api_abuse_rejected request_id=%s route_group=%s client_ip=%s "
            "status=%s",
            request_id,
            route_group,
            client_ip,
            status_code,
        )
        response = JSONResponse(
            {"detail": detail, "requestId": request_id},
            status_code=status_code,
            headers=headers,
        )
        await response(scope, receive, send)
