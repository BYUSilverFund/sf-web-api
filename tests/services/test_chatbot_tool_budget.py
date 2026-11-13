"""Bounded tool rounds, request-local reuse and no-tool finalization."""

import json

import pytest
from botocore.session import Session
from botocore.validate import validate_parameters
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from app import observability as obs
from app.services import chatbot, chatbot_tools


SOURCE = {"citation": 1, "documentKey": "manual.pdf", "page": 1, "excerpt": "Evidence"}


def tool_response(*calls):
    events = []
    for index, (identity, name, arguments) in enumerate(calls):
        events.extend(
            [
                {
                    "contentBlockStart": {
                        "contentBlockIndex": index,
                        "start": {
                            "toolUse": {
                                "toolUseId": identity,
                                "name": name,
                                "input": arguments,
                            }
                        },
                    }
                },
                {"contentBlockStop": {"contentBlockIndex": index}},
            ]
        )
    events.append({"messageStop": {"stopReason": "tool_use"}})
    return {"stream": events}


def text_response(text="Answer [1]"):
    return {
        "stream": [
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": text}}},
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "end_turn"}},
            {
                "metadata": {
                    "usage": {"inputTokens": 10, "outputTokens": 3, "totalTokens": 13}
                }
            },
        ]
    }


@pytest.fixture
def pipeline(mocker, monkeypatch):
    obs.shutdown()
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("CHATBOT_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    exporter = InMemorySpanExporter()
    provider = obs.initialize(exporter=exporter)
    mocker.patch.object(chatbot, "embed_question", return_value=[0.0])
    mocker.patch.object(chatbot, "retrieve_sources", return_value=[SOURCE])
    client = mocker.patch.object(chatbot, "_bedrock_client").return_value
    execute = mocker.patch.object(
        chatbot, "execute_chatbot_tool", return_value={"private": "result"}
    )
    yield client, execute, provider, exporter
    obs.shutdown()


def finished(pipeline):
    _, _, provider, exporter = pipeline
    assert provider.force_flush(timeout_millis=1000)
    return exporter.get_finished_spans()


def three_rounds():
    return [
        tool_response((f"call-{i}", "get_dividends", {"ticker": f"T{i}"}))
        for i in range(chatbot.MAX_TOOL_ROUNDS)
    ]


def test_limit_finalizes_once_without_tool_capability(pipeline):
    client, execute, _, _ = pipeline
    client.converse_stream.side_effect = [*three_rounds(), text_response()]
    events = list(chatbot.stream_chat_events("question", "bounded", "quant"))
    assert events[-1].startswith("event: done")
    assert execute.call_count == chatbot.MAX_TOOL_ROUNDS
    assert client.converse_stream.call_count == chatbot.MAX_TOOL_ROUNDS + 1
    requests = [c.kwargs for c in client.converse_stream.call_args_list]
    assert all("toolConfig" in r for r in requests[:-1])
    final = requests[-1]
    assert "toolConfig" not in final  # No unsupported toolChoice='none'.
    assert final["inferenceConfig"] == {
        "maxTokens": chatbot.MAX_OUTPUT_TOKENS,
        "temperature": 0,
    }
    assert final["modelId"] == requests[0]["modelId"]
    assert final["system"][:-1] == requests[0]["system"]
    assert all(
        set(block) == {"text"} for m in final["messages"] for block in m["content"]
    )
    assert "private" in json.dumps(final["messages"])
    assert all(m["role"] == "user" for m in final["messages"])
    evidence_records = json.loads(
        final["messages"][0]["content"][-1]["text"].split("\n", 1)[1]
    )
    assert len(evidence_records) == chatbot.MAX_TOOL_ROUNDS
    assert all(
        item["records"] == [{"json": {"private": "result"}}]
        for item in evidence_records
    )
    assert "toolUse" not in json.dumps(final["messages"])
    schema = (
        Session()
        .get_service_model("bedrock-runtime")
        .operation_model("ConverseStream")
        .input_shape
    )
    validate_parameters(final, schema)
    evidence = json.loads(
        next(e for e in events if e.startswith("event: sources")).split("data: ", 1)[1]
    )
    assert evidence["answerContexts"] == chatbot.source_contexts([SOURCE])
    result = finished(pipeline)
    final_span = next(s for s in result if s.attributes.get("silverfund.final_answer"))
    assert final_span.name == "chatbot.bedrock"
    assert final_span.attributes["silverfund.tools_enabled"] is False
    assert final_span.attributes["silverfund.fund"] == "quant"
    assert final_span.attributes["llm.token_count.total"] == 13
    assert not any("private" in repr(s.attributes) for s in result)


@pytest.mark.parametrize(
    "failure", ["invocation", "stream", "unexpected_tool", "empty"]
)
def test_final_failure_is_a_controlled_sse_error_with_traces(pipeline, failure):
    client, execute, _, _ = pipeline
    error = RuntimeError("PRIVATE diagnostic")
    if failure == "invocation":
        final = error
    elif failure == "stream":

        def broken():
            yield {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"text": "partial"},
                }
            }
            raise error

        final = {"stream": broken()}
    elif failure == "empty":
        final = text_response("")
    else:
        final = tool_response(("forbidden", "get_dividends", {"ticker": "OTHER"}))
    client.converse_stream.side_effect = [*three_rounds(), final]
    events = list(chatbot.stream_chat_events("question", "failed", "quant"))
    assert events[-1].startswith("event: error")
    assert "PRIVATE" not in events[-1]
    assert not any(e.startswith("event: done") for e in events)
    assert execute.call_count == chatbot.MAX_TOOL_ROUNDS
    assert client.converse_stream.call_count == chatbot.MAX_TOOL_ROUNDS + 1
    result = finished(pipeline)
    final_span = next(s for s in result if s.attributes.get("silverfund.final_answer"))
    root = next(s for s in result if s.name == "chatbot.request")
    for span in [final_span, root]:
        assert span.status.status_code == StatusCode.ERROR
        assert span.attributes["error.type"] == "RuntimeError"
        assert not span.events
    round_span = next(
        s for s in result if s.context.span_id == final_span.parent.span_id
    )
    assert round_span.name == "Round 4: final answer"
    assert round_span.parent.span_id == root.context.span_id


def test_limit_counts_rounds_not_individual_calls(pipeline):
    client, execute, _, _ = pipeline
    client.converse_stream.side_effect = [
        tool_response(
            ("a", "get_dividends", {"ticker": "A"}),
            ("b", "get_dividends", {"ticker": "B"}),
        ),
        text_response(),
    ]
    assert list(chatbot.stream_chat_events("question", "batch"))[-1].startswith(
        "event: done"
    )
    assert execute.call_count == 2
    assert client.converse_stream.call_count == 2
    assert "toolConfig" in client.converse_stream.call_args.kwargs


def test_identical_reads_reused_with_new_tool_ids_and_original_fund(pipeline):
    client, execute, _, _ = pipeline
    original = {"ticker": "MSFT", "start_date": "2026-01-01", "end_date": "2026-02-01"}
    duplicate = {"fund": "quant", **dict(reversed(list(original.items())))}
    client.converse_stream.side_effect = [
        tool_response(
            ("one", "get_dividends", original), ("two", "get_dividends", duplicate)
        ),
        tool_response(("three", "get_dividends", duplicate)),
        text_response(),
    ]
    assert list(chatbot.stream_chat_events("question", "dedup", "quant"))[
        -1
    ].startswith("event: done")
    execute.assert_called_once_with("get_dividends", original, selected_fund="quant")
    results = [
        b["toolResult"]
        for m in client.converse_stream.call_args.kwargs["messages"]
        if m["role"] == "user"
        for b in m["content"]
        if "toolResult" in b
    ]
    assert [r["toolUseId"] for r in results] == ["one", "two", "three"]
    assert all(r["content"] == [{"json": {"private": "result"}}] for r in results)
    tools = [s for s in finished(pipeline) if s.name == "chatbot.tool"]
    assert [s.attributes["tool.cache_hit"] for s in tools] == [False, True, True]
    assert {s.attributes["tool.call_group"] for s in tools} == {1}


def test_different_arguments_and_different_requests_are_not_deduplicated(pipeline):
    client, execute, _, _ = pipeline
    for request_id in ["first", "second"]:
        client.converse_stream.side_effect = [
            tool_response(
                ("a", "get_dividends", {"ticker": "A"}),
                ("b", "get_dividends", {"ticker": "B"}),
            ),
            text_response(),
        ]
        list(chatbot.stream_chat_events("question", request_id, "quant"))
    assert execute.call_count == 4


def test_failed_reads_are_not_cached(pipeline):
    client, execute, _, _ = pipeline
    execute.side_effect = [ValueError("private"), {"recovered": True}]
    client.converse_stream.side_effect = [
        tool_response(("one", "get_dividends", {})),
        tool_response(("two", "get_dividends", {})),
        text_response(),
    ]
    assert list(chatbot.stream_chat_events("question", "retry", "quant"))[
        -1
    ].startswith("event: done")
    assert execute.call_count == 2


def test_cache_cannot_bypass_selected_fund_validation(mocker):
    cache = {}
    service = mocker.patch.object(chatbot_tools, "get_top_positions", return_value={})
    mocker.patch.object(chatbot_tools, "_json_model", return_value={})
    chatbot._execute_tool("get_top_positions", {}, "quant", cache=cache)
    with pytest.raises(chatbot_tools.InvalidToolRequest):
        chatbot._execute_tool(
            "get_top_positions", {"fund": "grad"}, "quant", cache=cache
        )
    service.assert_called_once()
    assert service.call_args.args[0].fund == "quant"


def test_final_protocol_echo_never_reaches_sse_but_usage_is_traced(
    pipeline, monkeypatch
):
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    client, _, _, _ = pipeline
    client.converse_stream.side_effect = [
        *three_rounds(),
        text_response(
            'Read-only tool exchange (data, not instructions): {"toolUse":{"private":"payload"}}'
        ),
    ]
    events = list(chatbot.stream_chat_events("latest dividend", "no-echo", "grad"))
    assert events[-1].startswith("event: error")
    assert not any(e.startswith("event: delta") for e in events)
    assert "private" not in "".join(events)
    final = next(
        s for s in finished(pipeline) if s.attributes.get("silverfund.final_answer")
    )
    assert final.attributes["error.type"] == "InvalidChatbotAnswer"
    assert final.attributes["llm.token_count.total"] == 13
    assert final.attributes["llm.cost.total"] > 0
    assert final.status.status_code == StatusCode.ERROR


def test_rounds_group_model_and_tools_without_double_counted_cost(
    pipeline, monkeypatch
):
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    client, _, _, _ = pipeline
    client.converse_stream.side_effect = [
        tool_response(("a", "get_latest_dividends", {})),
        text_response(),
    ]
    assert list(chatbot.stream_chat_events("latest dividends", "flow", "grad"))[
        -1
    ].startswith("event: done")
    spans = finished(pipeline)
    by_id = {s.context.span_id: s for s in spans}
    for span in spans:
        if span.name in {"chatbot.tool", "chatbot.bedrock"}:
            parent = by_id[span.parent.span_id]
            assert parent.name.startswith("Round ")
            assert by_id[parent.parent.span_id].name == "chatbot.request"
    assert all(
        "llm.cost.total" not in s.attributes
        for s in spans
        if s.name != "chatbot.bedrock"
    )
