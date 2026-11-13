"""Opt-in local root Q&A; all exporters/model boundaries are offline mocks."""

import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from app import observability as obs
from app import trace_content as content
from app.services import chatbot


@pytest.fixture
def capture(monkeypatch):
    obs.shutdown()
    monkeypatch.setenv("CHATBOT_TRACE_CONTENT_ENABLED", "true")
    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    exporter = InMemorySpanExporter()
    provider = obs.initialize(exporter=exporter)
    yield provider, exporter
    obs.shutdown()


@pytest.fixture
def answer(mocker):
    mocker.patch.object(chatbot, "embed_question", return_value=[1.0])
    mocker.patch.object(
        chatbot,
        "retrieve_sources",
        return_value=[
            {
                "citation": 1,
                "documentKey": "private.pdf",
                "page": 1,
                "excerpt": "PRIVATE source not exported",
            }
        ],
    )
    return mocker.patch.object(
        chatbot, "_stream_answer", return_value=iter(["Hello ", "world [1]."])
    )


def roots(capture):
    provider, exporter = capture
    assert provider.force_flush(timeout_millis=1000)
    return [s for s in exporter.get_finished_spans() if s.name == "chatbot.request"]


def test_actual_question_and_combined_streamed_answer_on_root(capture, answer):
    events = list(
        chatbot.stream_chat_events("Actual question", "content-request", "grad")
    )
    span = roots(capture)[0]
    assert span.attributes["input.value"] == "Actual question"
    assert span.attributes["output.value"] == "Hello world [1]."
    assert (
        span.attributes["input.mime_type"]
        == span.attributes["output.mime_type"]
        == "text/plain"
    )
    assert span.attributes["silverfund.content.status"] == "completed"
    assert span.attributes["silverfund.fund"] == "grad"
    assert span.attributes["silverfund.request_id"] == "content-request"
    assert "PRIVATE source" not in repr(span.attributes)
    assert events[-1].startswith("event: done")
    assert json.loads(events[-2].split("data: ", 1)[1])[
        "answerContexts"
    ] == chatbot.source_contexts(
        [
            {
                "citation": 1,
                "documentKey": "private.pdf",
                "page": 1,
                "excerpt": "PRIVATE source not exported",
            }
        ]
    )
    answer.assert_called_once()  # No second iteration or inference.


def test_capture_preserves_identical_sse_when_disabled(capture, answer, monkeypatch):
    observed = list(chatbot.stream_chat_events("question", "same", "grad"))
    monkeypatch.setenv("CHATBOT_TRACE_CONTENT_ENABLED", "false")
    answer.return_value = iter(["Hello ", "world [1]."])
    baseline = list(chatbot.stream_chat_events("question", "same", "grad"))
    assert observed == baseline
    assert "input.value" not in roots(capture)[1].attributes


def test_streaming_is_lazy_across_threads_and_partial_output_is_not_published(
    capture, answer
):
    stream = chatbot.stream_chat_events("question", "lazy", "quant")
    answer.assert_not_called()
    with (
        ThreadPoolExecutor(max_workers=1) as first,
        ThreadPoolExecutor(max_workers=1) as second,
    ):
        assert "event: meta" in first.submit(next, stream).result()
        answer.assert_not_called()
        assert "event: delta" in second.submit(next, stream).result()
        assert roots(capture) == []
        first.submit(stream.close).result()
    span = roots(capture)[0]
    assert span.attributes["input.value"] == "question"
    assert "output.value" not in span.attributes
    assert span.attributes["silverfund.content.status"] == "cancelled"
    assert span.attributes["stream.cancelled"]


def test_cancellation_after_done_is_conservatively_not_marked_complete(capture, answer):
    stream = chatbot.stream_chat_events("question", "after-done")
    while "event: done" not in next(stream):
        pass
    stream.close()
    span = roots(capture)[0]
    assert span.attributes["silverfund.content.status"] == "cancelled"
    assert "output.value" not in span.attributes


@pytest.mark.parametrize(
    "field,value",
    [
        ("CHATBOT_TRACE_CONTENT_ENABLED", "false"),
        ("CHATBOT_TRACE_CONTENT_ENABLED", "1"),
        ("CHATBOT_OBSERVABILITY_ENABLED", "false"),
        ("APP_ENVIRONMENT", "production"),
        ("APP_ENVIRONMENT", "staging"),
        ("APP_ENVIRONMENT", ""),
        ("PHOENIX_COLLECTOR_ENDPOINT", "https://remote.example/v1/traces"),
        ("PHOENIX_COLLECTOR_ENDPOINT", "http://127.0.0.1:9999/v1/traces"),
    ],
)
def test_capture_fails_closed_even_when_provider_was_previously_local(
    capture, answer, monkeypatch, field, value
):
    monkeypatch.setenv(field, value)
    assert list(chatbot.stream_chat_events("PRIVATE question", "disabled"))[
        -1
    ].startswith("event: done")
    span = roots(capture)[0]
    assert (
        "input.value" not in span.attributes and "output.value" not in span.attributes
    )


def test_flag_absent_defaults_to_metadata_only(capture, answer, monkeypatch):
    monkeypatch.delenv("CHATBOT_TRACE_CONTENT_ENABLED")
    list(chatbot.stream_chat_events("PRIVATE question", "default"))
    assert "input.value" not in roots(capture)[0].attributes


def test_disabled_observability_does_not_start_exporter(answer, monkeypatch):
    obs.shutdown()
    monkeypatch.setenv("CHATBOT_TRACE_CONTENT_ENABLED", "true")
    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "false")
    exporter = Mock()
    assert obs.initialize(exporter=exporter) is None
    assert list(chatbot.stream_chat_events("question", "no-provider"))[-1].startswith(
        "event: done"
    )
    exporter.export.assert_not_called()


def test_remote_collector_is_rejected_at_initialization(answer, monkeypatch, caplog):
    obs.shutdown()
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("CHATBOT_TRACE_CONTENT_ENABLED", "true")
    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "https://remote.example/v1/traces")
    exporter = Mock()
    assert obs.initialize(exporter=exporter) is None
    assert (
        "event: done"
        in list(chatbot.stream_chat_events("PRIVATE question", "remote"))[-1]
    )
    exporter.export.assert_not_called()
    assert "PRIVATE question" not in caplog.text


def test_errors_do_not_publish_partial_answers(capture, answer):
    def broken():
        yield "Partial answer"
        raise ValueError("PRIVATE diagnostic")

    answer.return_value = broken()
    events = list(chatbot.stream_chat_events("question", "failed"))
    span = roots(capture)[0]
    assert events[-1].startswith("event: error")
    assert span.attributes["silverfund.content.status"] == "error"
    assert span.status.status_code == StatusCode.ERROR
    assert "output.value" not in span.attributes
    assert "PRIVATE diagnostic" not in repr(span.attributes)


def test_truncation_has_bounded_memory_and_leaves_response_untouched(capture, answer):
    text = "A" * (content.MAX_BUFFER_CHARS * 2)
    answer.return_value = iter([text])
    events = list(chatbot.stream_chat_events("Q" * 5000, "bounded"))
    span = roots(capture)[0]
    assert len(span.attributes["input.value"]) == content.MAX_INPUT_CHARS
    assert len(span.attributes["output.value"]) == content.MAX_OUTPUT_CHARS
    assert span.attributes["silverfund.content.input_truncated"]
    assert span.attributes["silverfund.content.output_truncated"]
    assert json.loads(events[1].split("data: ", 1)[1])["text"] == text


def test_credentials_redacted_across_delta_and_truncation_boundaries(
    capture, answer, monkeypatch
):
    secret = "unique-configured-secret-value"
    monkeypatch.setenv("PHOENIX_API_KEY", secret)
    key = "AKIA" + "A" * 16
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signature"
    question = f"Bearer bearer-token-value {key} {jwt} sk-test12345678 password=database-password"
    answer.return_value = iter(
        [secret[:12], secret[12:], " AWS_SECRET_ACCESS_KEY=other-private-value"]
    )
    events = list(chatbot.stream_chat_events(question, "redacted"))
    span = roots(capture)[0]
    exported = span.attributes["input.value"] + span.attributes["output.value"]
    for value in [
        secret,
        key,
        jwt,
        "bearer-token-value",
        "sk-test12345678",
        "database-password",
        "other-private-value",
    ]:
        assert value not in exported
    assert "[REDACTED]" in exported
    assert span.attributes["silverfund.content.redacted"]
    assert secret in "".join(
        json.loads(e.split("data: ", 1)[1])["text"]
        for e in events
        if e.startswith("event: delta")
    )


def test_long_known_secret_clipped_inside_buffer_cannot_leak(
    capture, answer, monkeypatch
):
    secret = "LONG-CREDENTIAL-" + "s" * content.MAX_BUFFER_CHARS
    monkeypatch.setenv("AWS_SESSION_TOKEN", secret)
    answer.return_value = iter(["Prefix " + secret])
    list(chatbot.stream_chat_events("question", "long-secret"))
    output = roots(capture)[0].attributes["output.value"]
    assert output == "Prefix [REDACTED]"


def test_private_key_block_redaction(capture, answer):
    question = (
        "-----BEGIN PRIVATE KEY-----\nprivate-key-value\n-----END PRIVATE KEY-----"
    )
    list(chatbot.stream_chat_events(question, "pem"))
    assert roots(capture)[0].attributes["input.value"] == "[REDACTED]"


def test_cleanup_failure_cannot_prevent_span_end(capture):
    @obs.traced("chatbot.request", "CHAIN")
    def pipeline(question):
        try:
            yield chatbot._sse("delta", {"text": "unfinished"})
        finally:
            raise RuntimeError("PRIVATE cleanup detail")

    stream = pipeline("question")
    next(stream)
    with pytest.raises(RuntimeError, match="cleanup detail"):
        stream.close()
    span = roots(capture)[0]
    assert span.end_time is not None
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["stream.cleanup_error_type"] == "RuntimeError"
    assert span.attributes["silverfund.content.status"] == "error"
    assert "output.value" not in span.attributes
    assert "PRIVATE" not in repr(span.attributes)


def test_export_failure_is_independent_of_content_capture(capture, answer):
    provider, _ = capture
    exporter = Mock(spec=SpanExporter)
    exporter.export.side_effect = ConnectionError("collector unavailable")
    # Install another real batch processor; failures happen only on its worker.
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=10))
    assert list(chatbot.stream_chat_events("question", "outage"))[-1].startswith(
        "event: done"
    )
    assert provider.force_flush(timeout_millis=1000)
    assert roots(capture)[0].attributes["output.value"] == "Hello world [1]."
    assert exporter.export.called


def test_capture_failure_itself_cannot_break_sse(capture, answer, mocker):
    mocker.patch.object(
        content.RequestContentCapture,
        "observe",
        side_effect=ValueError("PRIVATE capture detail"),
    )
    assert list(chatbot.stream_chat_events("question", "broken-capture"))[
        -1
    ].startswith("event: done")
