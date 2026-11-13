from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.funds import FUND_ALIASES, mentioned_funds
from app.routers.chatbot import ChatRequest, stream_chat
from app.services import chatbot, chatbot_tools


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("all_funds", None),
        ("All funds", None),
        ("quant", "quant"),
        ("Brigham Capital", "brigham_capital"),
        ("Quant Paper", "quant_paper"),
    ],
)
def test_request_fund(value, expected):
    assert ChatRequest(message=" hello ", fund=value).fund == expected
    assert ChatRequest(message="hello").fund is None


@pytest.mark.parametrize("value", ["", " ", "unknown", 12, [], {}])
def test_invalid_fund(value):
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", fund=value)


def test_route_passes_structured_fund(mocker):
    events = mocker.patch(
        "app.routers.chatbot.stream_chat_events", return_value=iter([])
    )
    stream_chat(ChatRequest(message="hello", fund="quant"), {"sub": "verified"})
    assert events.call_args.args[0] == "hello"
    assert events.call_args.args[2] == "quant"


@pytest.mark.parametrize(
    "question",
    [
        "What does Grad hold?",
        "Compare quant and undergrad",
        "quant_paper returns",
        "Quant Paper Fund positions",
    ],
)
def test_conflicts_stop_before_embedding_or_tools(question, mocker):
    embed = mocker.patch.object(chatbot, "embed_question")
    output = "".join(chatbot.stream_chat_events(question, "req", "quant"))
    assert "Please clarify" in output
    assert "event: done" in output
    embed.assert_not_called()


def test_longest_alias_and_word_boundaries():
    assert mentioned_funds("Quant Paper Fund and undergraduate fund") == {
        "quant_paper",
        "undergrad",
    }
    assert mentioned_funds("graduate fund, Brigham Capital, quantitative fund") == {
        "grad",
        "brigham_capital",
        "quant",
    }
    assert mentioned_funds("graduated quantitative estimates for MSFT") == set()


def test_selection_reaches_retrieval_and_answer(mocker):
    mocker.patch.object(chatbot, "embed_question", return_value=[1.0])
    retrieve = mocker.patch.object(chatbot, "retrieve_sources", return_value=[])
    answer = mocker.patch.object(
        chatbot, "_stream_answer", return_value=iter(["answer"])
    )
    list(chatbot.stream_chat_events("positions?", "req", "undergrad"))
    retrieve.assert_called_once_with([1.0], "undergrad")
    answer.assert_called_once_with("positions?", [], "req", "undergrad")


@pytest.mark.parametrize("fund", [None, *FUND_ALIASES])
def test_filter_is_bound_before_ranking_and_handles_old_schema(fund, mocker):
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.one.return_value = {
        "ingestion_state_table": True,
        "embeddings_table": True,
    }
    connection.execute.return_value.mappings.return_value.__iter__.return_value = iter(
        []
    )
    engine = mocker.patch.object(chatbot, "engine")
    engine.connect.return_value.__enter__.return_value = connection
    assert chatbot.retrieve_sources([1.0], fund) == []
    query, params = connection.execute.call_args.args
    sql = str(query)
    assert sql.index("document_scope") < sql.index("ORDER BY") < sql.index("LIMIT")
    assert "to_jsonb(chunks)->>'document_scope' = 'shared'" in sql
    assert "NULLIF(BTRIM(to_jsonb(chunks)->>'fund'), '') IS NULL" in sql
    assert "to_jsonb(chunks)->>'document_scope' = 'fund'" in sql
    assert "ANY(:fund_aliases)" in sql
    assert params["fund"] == fund
    assert params["fund_aliases"] == list(FUND_ALIASES.get(fund, ()))
    assert "chunks.fund" not in sql  # safely yields no scoped evidence before migration


def test_tool_context_fills_missing_fund_without_mutating_input(mocker):
    service = mocker.patch.object(chatbot_tools, "get_top_positions", return_value={})
    mocker.patch.object(chatbot_tools, "_json_model", return_value={})
    raw = {}
    chatbot_tools.execute_chatbot_tool("get_top_positions", raw, selected_fund="quant")
    assert service.call_args.args[0].fund == "quant"
    assert raw == {}


def test_tool_context_cannot_cross_fund(mocker):
    service = mocker.patch.object(chatbot_tools, "get_top_positions")
    with pytest.raises(chatbot_tools.InvalidToolRequest, match="clarification"):
        chatbot_tools.execute_chatbot_tool(
            "get_top_positions", {"fund": "grad"}, selected_fund="quant"
        )
    service.assert_not_called()


def test_selected_fund_in_model_context(mocker):
    client = mocker.patch.object(chatbot, "_bedrock_client").return_value
    client.converse_stream.return_value = {"stream": []}
    list(chatbot._stream_answer("holdings", [], "req", "quant_paper"))
    assert "Selected fund: quant_paper" in str(
        client.converse_stream.call_args.kwargs["system"]
    )


@pytest.mark.parametrize(
    "name", [tool["toolSpec"]["name"] for tool in chatbot.CHATBOT_TOOL_CONFIG["tools"]]
)
def test_every_financial_tool_rejects_cross_fund_before_service(name, mocker):
    services = [
        mocker.patch.object(chatbot_tools, service)
        for service in (
            "get_portfolio_summary",
            "get_top_positions",
            "get_all_holdings_summary",
            "get_holding_summary",
            "get_trades",
            "get_dividends",
        )
    ]
    with pytest.raises(chatbot_tools.InvalidToolRequest, match="conflicts"):
        chatbot._execute_tool(name, {"fund": "grad"}, "quant")
    for service in services:
        service.assert_not_called()
