"""Offline integration tests: real pipeline, SDK and batching; mocked I/O."""

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from time import perf_counter
from unittest.mock import Mock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from app import observability as obs
from app.auth import cognito_auth
from app.main import create_app
from app.services import chatbot
from fastapi.testclient import TestClient


@pytest.fixture
def telemetry(monkeypatch):
    obs.shutdown()
    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    exporter = InMemorySpanExporter()
    provider = obs.initialize(exporter=exporter)
    yield provider, exporter
    obs.shutdown()


def spans(telemetry):
    provider, exporter = telemetry
    assert provider.force_flush(timeout_millis=1000)
    return exporter.get_finished_spans()


@pytest.fixture
def pipeline(mocker):
    client = mocker.patch.object(chatbot, "_bedrock_client").return_value
    client.invoke_model.return_value = {
        "body": BytesIO(
            json.dumps(
                {
                    "embedding": [0.0] * 1024,
                    "inputTextTokenCount": 7,
                }
            ).encode()
        )
    }
    client.converse_stream.return_value = {
        "stream": iter(
            [
                {
                    "contentBlockDelta": {
                        "contentBlockIndex": 0,
                        "delta": {"text": "PRIVATE answer [3]"},
                    }
                },
                {"messageStop": {"stopReason": "end_turn"}},
                {
                    "metadata": {
                        "usage": {
                            "inputTokens": 20,
                            "outputTokens": 8,
                            "totalTokens": 28,
                        }
                    }
                },
            ]
        )
    }
    connection = mocker.patch.object(
        chatbot.engine, "connect"
    ).return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.one.return_value = {
        "ingestion_state_table": "present",
        "embeddings_table": "present",
    }
    connection.execute.return_value.mappings.return_value.__iter__.return_value = iter(
        [
            {
                "document_key": "PRIVATE document.pdf",
                "page": 2,
                "excerpt": "PRIVATE evidence",
                "source_metadata": {},
            }
        ]
    )
    return client


def test_real_pipeline_metadata_and_privacy(telemetry, pipeline):
    events = list(chatbot.stream_chat_events("PRIVATE question", "request-123"))
    assert "event: done" in events[-1]
    result = spans(telemetry)
    by_name = {s.name: s for s in result}
    assert set(by_name) == {
        "chatbot.request",
        "chatbot.embedding",
        "chatbot.bedrock.embedding",
        "chatbot.retrieval",
        "chatbot.bedrock",
        "Round 1: model and tools",
    }
    root = by_name["chatbot.request"]
    assert root.attributes["silverfund.request_id"] == "request-123"
    assert json.loads(root.attributes["metadata"])["request_id"] == "request-123"
    assert root.attributes["duration_ms"] > 0
    for child in result[:-1]:
        expected_parent = (
            by_name["chatbot.embedding"]
            if child.name == "chatbot.bedrock.embedding"
            else by_name["Round 1: model and tools"]
            if child.name == "chatbot.bedrock"
            else root
        )
        assert child.parent.span_id == expected_parent.context.span_id
        assert child.context.trace_id == root.context.trace_id
        assert root.start_time <= child.start_time <= child.end_time <= root.end_time
    assert (
        by_name["chatbot.bedrock.embedding"].attributes["llm.token_count.prompt"] == 7
    )
    retrieval = by_name["chatbot.retrieval"].attributes
    assert retrieval["retrieval.source_count"] == 1
    assert retrieval["retrieval.citation_ids"] == ("1",)
    llm = by_name["chatbot.bedrock"].attributes
    assert llm["llm.model_name"]
    assert llm["llm.token_count.prompt"] == 20
    assert llm["llm.token_count.completion"] == 8
    assert llm["llm.token_count.total"] == 28
    assert "PRIVATE" not in repr([(s.attributes, s.events, s.status) for s in result])
    assert all(not s.events for s in result)


def test_stream_lifetime_and_worker_thread_context(telemetry, pipeline):
    stream = chatbot.stream_chat_events("question", "streamed")
    assert spans(telemetry) == ()
    with (
        ThreadPoolExecutor(max_workers=1) as first,
        ThreadPoolExecutor(max_workers=1) as second,
    ):
        assert "meta" in first.submit(next, stream).result()
        assert spans(telemetry) == ()
        assert "delta" in second.submit(next, stream).result()
        assert not any(
            s.name in {"chatbot.request", "chatbot.bedrock"} for s in spans(telemetry)
        )
        for executor in (first, second):
            assert not executor.submit(
                lambda: trace.get_current_span().get_span_context().is_valid
            ).result()
        assert "sources" in first.submit(next, stream).result()
        assert "done" in second.submit(next, stream).result()
        assert not any(s.name == "chatbot.request" for s in spans(telemetry))
        with pytest.raises(StopIteration):
            first.submit(next, stream).result()
    assert len({s.context.trace_id for s in spans(telemetry)}) == 1


def test_close_during_stream_ends_nested_spans(telemetry, pipeline):
    stream = chatbot.stream_chat_events("question", "closed")
    next(stream)
    next(stream)
    stream.close()
    result = {s.name: s for s in spans(telemetry)}
    assert result["chatbot.request"].attributes["stream.cancelled"]
    assert result["chatbot.bedrock"].attributes["stream.cancelled"]
    assert not trace.get_current_span().get_span_context().is_valid


@pytest.mark.asyncio
async def test_asgi_send_disconnect_closes_pipeline(telemetry, pipeline):
    iterator = obs.sse_iterator(chatbot.stream_chat_events("question", "disconnect"))
    response = obs.ChatStreamingResponse(iterator)

    async def send(message):
        if message["type"] == "http.response.body":
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await response.stream_response(send)
    assert next(s for s in spans(telemetry) if s.name == "chatbot.request").attributes[
        "stream.cancelled"
    ]


@pytest.mark.parametrize(
    "error", [ValueError("PRIVATE credentials"), RuntimeError("PRIVATE message")]
)
def test_pipeline_error_is_safe_and_preserves_sse(telemetry, pipeline, error):
    pipeline.invoke_model.side_effect = error
    events = list(chatbot.stream_chat_events("PRIVATE question", "error-request"))
    assert "event: error" in events[-1]
    assert "PRIVATE" not in events[-1]
    result = spans(telemetry)
    assert {s.name for s in result} == {
        "chatbot.embedding",
        "chatbot.bedrock.embedding",
        "chatbot.request",
    }
    for span in result:
        assert span.status.status_code == StatusCode.ERROR
        assert span.attributes["error.type"] == type(error).__name__
        assert span.status.description is None
        assert not span.events
        assert "PRIVATE" not in repr(span.attributes)


@pytest.mark.parametrize(
    "failure",
    [None, chatbot.InvalidToolRequest("PRIVATE args"), RuntimeError("PRIVATE result")],
)
def test_tool_round_tracing(telemetry, pipeline, mocker, failure):
    first = {
        "stream": iter(
            [
                {
                    "contentBlockStart": {
                        "contentBlockIndex": 0,
                        "start": {
                            "toolUse": {
                                "toolUseId": "tool-1",
                                "name": "get_top_positions",
                                "input": {"fund": "undergrad"},
                            }
                        },
                    }
                },
                {"contentBlockStop": {"contentBlockIndex": 0}},
                {"messageStop": {"stopReason": "tool_use"}},
            ]
        )
    }
    pipeline.converse_stream.side_effect = [
        first,
        pipeline.converse_stream.return_value,
    ]
    mocker.patch.object(
        chatbot,
        "execute_chatbot_tool",
        return_value={"PRIVATE": "results"},
        side_effect=failure,
    )
    events = list(chatbot.stream_chat_events("question", "tools"))
    assert "event: done" in events[-1]
    result = spans(telemetry)
    tool = next(s for s in result if s.name == "chatbot.tool")
    root = next(s for s in result if s.name == "chatbot.request")
    parent = next(s for s in result if s.context.span_id == tool.parent.span_id)
    assert parent.name == "Round 1: model and tools"
    assert parent.parent.span_id == root.context.span_id
    assert tool.attributes["tool.name"] == "get_top_positions"
    assert tool.attributes["duration_ms"] >= 0
    assert len([s for s in result if s.name == "chatbot.bedrock"]) == 2
    assert (tool.status.status_code == StatusCode.ERROR) == (failure is not None)
    assert "PRIVATE" not in repr([(s.attributes, s.events) for s in result])


def test_disabled_by_default(monkeypatch, pipeline, mocker):
    obs.shutdown()
    monkeypatch.delenv("CHATBOT_OBSERVABILITY_ENABLED", raising=False)
    factory = mocker.patch.object(obs, "OTLPSpanExporter")
    assert obs.initialize() is None
    assert "event: done" in list(chatbot.stream_chat_events("question", "disabled"))[-1]
    factory.assert_not_called()


@pytest.mark.parametrize("environment", ["prod", "production", "", "staging"])
def test_local_environment_required(monkeypatch, environment):
    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("APP_ENVIRONMENT", environment)
    assert obs.initialize(exporter=InMemorySpanExporter()) is None


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:6006",
        "http://127.0.0.1:6006/",
        "http://localhost:6006/v1/traces",
    ],
)
def test_http_endpoint_normalization(url):
    assert obs.collector_endpoint(url).endswith("/v1/traces")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "http://localhost:6006/wrong",
        "grpc://localhost:4317",
        "http://secret@localhost:6006",
        "http://localhost:6006/?key=secret",
    ],
)
def test_invalid_endpoint_rejected(url):
    with pytest.raises(ValueError):
        obs.collector_endpoint(url)


def test_configuration_and_auth_header(monkeypatch, mocker):
    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.setenv("PHOENIX_API_KEY", "private-key")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    factory = mocker.patch.object(
        obs, "OTLPSpanExporter", return_value=InMemorySpanExporter()
    )
    try:
        assert obs.initialize() is obs.initialize()
        factory.assert_called_once_with(
            endpoint="http://localhost:6006/v1/traces",
            headers={"Authorization": "Bearer private-key"},
            timeout=2,
        )
    finally:
        obs.shutdown()


def test_startup_failure_does_not_prevent_chat(monkeypatch, mocker, pipeline, caplog):
    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("PHOENIX_API_KEY", "private-key")
    mocker.patch.object(
        obs, "OTLPSpanExporter", side_effect=RuntimeError("private-key")
    )
    with TestClient(create_app()) as client:
        client.app.dependency_overrides[cognito_auth] = lambda: {"sub": "user"}
        response = client.post("/chat/stream", json={"message": "question"})
        assert response.status_code == 200
        assert "event: done" in response.text
    assert "private-key" not in caplog.text


def test_collector_outage_never_blocks_sse(monkeypatch, pipeline):
    started, release = threading.Event(), threading.Event()

    class UnavailableExporter(SpanExporter):
        def export(self, batch):
            started.set()
            release.wait(timeout=3)
            raise ConnectionError("collector unavailable")

    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    obs.initialize(exporter=UnavailableExporter())
    try:
        # Enqueue enough to wake the batch worker while it is stalled exporting.
        for _ in range(70):
            with obs._provider.get_tracer("test").start_as_current_span("queued"):
                pass
        assert started.wait(timeout=1)
        before = perf_counter()
        events = list(chatbot.stream_chat_events("question", "outage"))
        assert perf_counter() - before < 1
        assert "event: done" in events[-1]
    finally:
        release.set()
        obs.shutdown()


def test_real_http_exporter_timeout_offline(monkeypatch, pipeline):
    import requests

    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    monkeypatch.setenv("PHOENIX_API_KEY", "private-key")
    session = Mock(spec=requests.Session)
    session.request.side_effect = requests.exceptions.Timeout("offline")
    # Use the installed OTLP transport with mocked HTTP only.
    exporter = obs.OTLPSpanExporter(
        endpoint="http://localhost:6006/v1/traces", timeout=0.01, session=session
    )
    provider = obs.initialize(exporter=exporter)
    try:
        assert (
            "event: done" in list(chatbot.stream_chat_events("question", "timeout"))[-1]
        )
        assert provider.force_flush(timeout_millis=1000)
        assert session.request.called
    finally:
        obs.shutdown()


@pytest.mark.parametrize("fund", [None, "quant", "grad"])
def test_selected_fund_on_all_pipeline_spans(telemetry, pipeline, fund):
    events = list(chatbot.stream_chat_events("definition please", "fund-trace", fund))
    assert "event: done" in events[-1]
    result = spans(telemetry)
    assert {s.name for s in result} == {
        "chatbot.request",
        "chatbot.embedding",
        "chatbot.bedrock.embedding",
        "chatbot.retrieval",
        "chatbot.bedrock",
        "Round 1: model and tools",
    }
    assert all(s.attributes["silverfund.fund"] == (fund or "all_funds") for s in result)
    assert obs._selected_fund.get() == "all_funds"
    source_event = next(e for e in events if e.startswith("event: sources"))
    payload = json.loads(source_event.split("data: ", 1)[1])
    assert payload["answerContexts"] == chatbot.source_contexts(payload["sources"])


def test_conflicting_fund_trace_preserves_empty_evidence(telemetry, mocker):
    embed = mocker.patch.object(chatbot, "embed_question")
    events = list(
        chatbot.stream_chat_events("What does Grad hold?", "clarify", "quant")
    )
    embed.assert_not_called()
    result = spans(telemetry)
    assert len(result) == 1
    assert result[0].attributes["silverfund.fund"] == "quant"
    assert '"answerContexts": []' in events[-2]


def test_selected_fund_tool_span(telemetry, mocker):
    mocker.patch.object(chatbot, "execute_chatbot_tool", return_value={})
    chatbot._execute_tool("get_top_positions", {}, "quant")
    tool = spans(telemetry)[0]
    assert tool.attributes["silverfund.fund"] == "quant"
    assert tool.attributes["tool.name"] == "get_top_positions"
    chatbot.execute_chatbot_tool.assert_called_once_with(
        "get_top_positions", {}, selected_fund="quant"
    )


def test_interleaved_streams_keep_their_fund_context(telemetry):
    @obs.traced("child", "TOOL")
    def child():
        return obs._selected_fund.get()

    @obs.traced("request", "CHAIN")
    def streaming(fund):
        yield child()
        yield child()

    quant, grad = streaming("quant"), streaming("grad")
    assert next(quant) == "quant"
    assert next(grad) == "grad"
    assert next(quant) == "quant"
    assert next(grad) == "grad"
    quant.close()
    grad.close()
    result = spans(telemetry)
    roots = {s.context.span_id: s for s in result if s.name == "request"}
    for span in result:
        if span.parent:
            assert (
                span.attributes["silverfund.fund"]
                == roots[span.parent.span_id].attributes["silverfund.fund"]
            )
    assert obs._selected_fund.get() == "all_funds"
