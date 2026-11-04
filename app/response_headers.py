"""Non-blocking security response headers for the API."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityResponseHeadersMiddleware:
    """Add headers without reading or buffering response bodies, including SSE."""

    _HEADERS = (
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), geolocation=(), microphone=()"),
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing_names = {name.lower() for name, _ in headers}
                headers.extend(
                    (name, value)
                    for name, value in self._HEADERS
                    if name not in existing_names
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, with_security_headers)
