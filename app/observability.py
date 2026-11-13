"""Optional local Phoenix tracing. No automatic payload or exception capture.

Own the provider rather than replacing OpenTelemetry's process-wide singleton.
Tests can inject an exporter; production always uses bounded batch export.
"""

import inspect
import json
import logging
import os
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from contextvars import ContextVar
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

import anyio
from openinference.semconv.trace import SpanAttributes as Attributes
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import Status, StatusCode
from starlette.concurrency import iterate_in_threadpool
from starlette.responses import StreamingResponse

from app.trace_content import RequestContentCapture

logger = logging.getLogger(__name__)
_provider: TracerProvider | None = None
_configured_endpoint: str | None = None
_selected_fund = ContextVar("silverfund_fund", default="all_funds")
_noop = trace.NoOpTracerProvider().get_tracer(__name__)


def collector_endpoint(value: str) -> str:
    """Accept a local Phoenix base URL or its explicit HTTP/protobuf endpoint."""
    url = urlsplit(value)
    if (
        url.scheme not in {"http", "https"}
        or url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path.rstrip("/") not in {"", "/v1/traces"}
    ):
        raise ValueError("Expected a loopback Phoenix HTTP collector URL")
    return urlunsplit((url.scheme, url.netloc, "/v1/traces", "", ""))


def initialize(*, exporter: SpanExporter | None = None) -> TracerProvider | None:
    """Initialize once at lifespan startup; never contact Phoenix at startup."""
    global _provider, _configured_endpoint
    if _provider is not None:
        return _provider
    if os.getenv("CHATBOT_OBSERVABILITY_ENABLED", "").lower() != "true":
        return None
    if os.getenv("APP_ENVIRONMENT", "").lower() not in {"local", "development", "dev"}:
        logger.warning(
            "Chatbot tracing requires an explicit local/development environment"
        )
        return None
    provider = None
    try:
        endpoint = collector_endpoint(
            os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
        )
        key = os.getenv("PHOENIX_API_KEY", "").strip()
        if exporter is None:
            if not key:
                raise ValueError("Phoenix API key required")
            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers={"Authorization": f"Bearer {key}"},
                timeout=2,
            )
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": "sf-web-api",
                    "openinference.project.name": os.getenv(
                        "PHOENIX_PROJECT_NAME", "silverfund-local"
                    ),
                }
            ),
            sampler=ALWAYS_ON,
            shutdown_on_exit=False,
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                exporter,
                max_queue_size=512,
                max_export_batch_size=64,
                schedule_delay_millis=1000,
                export_timeout_millis=2000,
            )
        )
        _provider = provider
        _configured_endpoint = endpoint
    except Exception:
        # Do not include exception text: malformed configuration may contain secrets.
        logger.warning("Chatbot tracing unavailable; check local Phoenix configuration")
        if provider is not None:
            provider.shutdown()
    return _provider


def shutdown() -> None:
    """Drain the bounded queue on application shutdown, never per SSE event."""
    global _provider, _configured_endpoint
    provider, _provider = _provider, None
    _configured_endpoint = None
    if provider is not None:
        try:
            provider.shutdown()
        except Exception:
            logger.warning("Chatbot tracing shutdown failed")


@asynccontextmanager
async def lifespan(app):
    initialize()
    try:
        yield
    finally:
        await anyio.to_thread.run_sync(shutdown)


def current_span():
    return trace.get_current_span()


def record_error(error: BaseException) -> None:
    """Exception messages and stack traces can contain private input or results."""
    span = current_span()
    span.set_attribute("error.type", type(error).__name__)
    span.set_status(Status(StatusCode.ERROR))


def request_metadata(request_id: str) -> None:
    span = current_span()
    span.set_attribute("silverfund.request_id", request_id)
    span.set_attribute(Attributes.METADATA, json.dumps({"request_id": request_id}))


@contextmanager
def _activate(span, fund):
    token = _selected_fund.set(fund)
    try:
        with trace.use_span(
            span,
            end_on_exit=False,
            record_exception=False,
            set_status_on_exception=False,
        ):
            yield
    finally:
        _selected_fund.reset(token)


def _request_content_capture(span, question):
    """Fail closed unless both the active provider and current config are local."""
    if (
        _provider is None
        or not span.is_recording()
        or os.getenv("CHATBOT_TRACE_CONTENT_ENABLED", "").lower() != "true"
        or os.getenv("CHATBOT_OBSERVABILITY_ENABLED", "").lower() != "true"
        or os.getenv("APP_ENVIRONMENT", "").lower()
        not in {"local", "development", "dev"}
    ):
        return None
    try:
        endpoint = collector_endpoint(
            os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
        )
        if endpoint != _configured_endpoint:
            return None
        return RequestContentCapture(span, question)
    except Exception:
        logger.warning(
            "Chatbot content capture unavailable; metadata tracing continues"
        )
        return None


def _capture_safely(capture, method, value):
    if capture is not None:
        try:
            getattr(capture, method)(value)
        except Exception:
            # Never log payloads, credentials or exception messages.
            logger.warning("Chatbot content capture failed; response continues")
            capture.answer = ""
            capture.secrets = ()
            try:
                capture.span.set_attribute("silverfund.content.status", "capture_error")
            except Exception:
                pass
            return None
    return capture


def traced(name: str, kind: str):
    """Trace functions or sync generators without holding context across yields.

    Starlette may advance a sync generator on different worker threads. Attach
    context only during next()/close(), preserving parentage and avoiding leaks.
    """

    def decorate(function):
        signature = inspect.signature(function)

        def start(args, kwargs):
            fund = (
                signature.bind(*args, **kwargs).arguments.get(
                    "fund", _selected_fund.get()
                )
                or "all_funds"
            )
            tracer = _provider.get_tracer(__name__) if _provider else _noop
            return tracer.start_span(
                name,
                attributes={
                    Attributes.OPENINFERENCE_SPAN_KIND: kind,
                    "silverfund.fund": fund,
                },
            ), fund

        def finish(span, started):
            span.set_attribute("duration_ms", (perf_counter() - started) * 1000)
            span.end()

        if inspect.isgeneratorfunction(function):

            @wraps(function)
            def streaming(*args, **kwargs):
                span, fund = start(args, kwargs)
                started = perf_counter()
                iterator = function(*args, **kwargs)
                capture = (
                    _request_content_capture(
                        span, signature.bind(*args, **kwargs).arguments["question"]
                    )
                    if name == "chatbot.request"
                    else None
                )
                lifecycle = "incomplete"
                try:
                    while True:
                        with _activate(span, fund):
                            try:
                                item = next(iterator)
                            except StopIteration as completed:
                                lifecycle = "exhausted"
                                return completed.value
                            except BaseException as error:
                                lifecycle = "error"
                                record_error(error)
                                raise
                        capture = _capture_safely(capture, "observe", item)
                        yield item
                except GeneratorExit:
                    lifecycle = "cancelled"
                    span.set_attribute("stream.cancelled", True)
                    raise
                finally:
                    try:
                        with _activate(span, fund):
                            try:
                                iterator.close()
                            except BaseException as error:
                                lifecycle = "error"
                                record_error(error)
                                span.set_attribute(
                                    "stream.cleanup_error_type", type(error).__name__
                                )
                                raise
                    finally:
                        _capture_safely(capture, "finish", lifecycle)
                        finish(span, started)

            return streaming

        @wraps(function)
        def regular(*args, **kwargs):
            span, fund = start(args, kwargs)
            started = perf_counter()
            try:
                with _activate(span, fund):
                    try:
                        return function(*args, **kwargs)
                    except BaseException as error:
                        record_error(error)
                        raise
            finally:
                finish(span, started)

        return regular

    return decorate


async def sse_iterator(iterator):
    """Close the sync pipeline on ASGI disconnect as well as normal exhaustion."""
    try:
        async for item in iterate_in_threadpool(iterator):
            yield item
    finally:
        with anyio.CancelScope(shield=True):
            close = getattr(iterator, "close", None)
            if close is not None:
                await anyio.to_thread.run_sync(close)


class ChatStreamingResponse(StreamingResponse):
    """Ensure disconnects close a suspended async iterator and its sync pipeline."""

    async def stream_response(self, send):
        try:
            await super().stream_response(send)
        finally:
            with anyio.CancelScope(shield=True):
                await self.body_iterator.aclose()


@contextmanager
def closing_iterator(iterator):
    """Accept any iterator while closing generators and SDK streams when supported."""
    try:
        yield iterator
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            close()
