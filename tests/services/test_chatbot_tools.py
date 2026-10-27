from datetime import date

import polars as pl
import pytest

from app.services import chatbot_tools, holding
from app.services.chatbot_tools import InvalidToolRequest, execute_chatbot_tool


def _trade_row(index: int) -> dict:
    return {
        "date": date(2025, 1, index),
        "type": "BUY",
        "shares": float(index),
        "price": 10.0,
        "value": float(index * 10),
        "ticker": f"T{index}",
    }


@pytest.mark.parametrize(
    "input_overrides",
    [
        {"sort_by": "date; DROP TABLE trades"},
        {"limit": 51},
        {"limit": 0},
        {"fund": "not_a_fund"},
        {"start_date": "2025-02-01", "end_date": "2025-01-01"},
    ],
)
def test_invalid_trade_tool_inputs_are_rejected_without_service_call(
    mocker, input_overrides
):
    trade_service = mocker.patch.object(chatbot_tools, "get_trades")
    tool_input = {
        "fund": "grad",
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        **input_overrides,
    }

    with pytest.raises(InvalidToolRequest):
        execute_chatbot_tool("get_trades", tool_input)

    trade_service.assert_not_called()


def test_trade_tool_forwards_sort_controls_and_caps_returned_rows(mocker):
    trade_service = mocker.patch.object(
        chatbot_tools,
        "get_trades",
        return_value={
            "fund": "grad",
            "start": date(2025, 1, 1),
            "end": date(2025, 1, 31),
            "trades": [_trade_row(index) for index in range(1, 6)],
        },
    )

    result = execute_chatbot_tool(
        "get_trades",
        {
            "fund": "grad",
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "sort_by": "value",
            "sort_desc": False,
            "limit": 3,
        },
    )

    assert trade_service.call_args.kwargs == {
        "sort_by": "value",
        "sort_desc": False,
        "limit": 3,
    }
    assert len(result["trades"]) == 3
    assert result["truncated"] is True


def test_trade_tool_defaults_to_50_newest_first(mocker):
    trade_service = mocker.patch.object(
        chatbot_tools,
        "get_trades",
        return_value={
            "fund": "grad",
            "start": date(2025, 1, 1),
            "end": date(2025, 1, 31),
            "trades": [],
        },
    )

    execute_chatbot_tool(
        "get_trades",
        {
            "fund": "grad",
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        },
    )

    assert trade_service.call_args.kwargs == {
        "sort_by": "date",
        "sort_desc": None,
        "limit": 50,
    }


def test_list_tool_schema_exposes_allowlisted_sort_and_50_row_maximum():
    tools_by_name = {
        tool["toolSpec"]["name"]: tool["toolSpec"]
        for tool in chatbot_tools.CHATBOT_TOOL_CONFIG["tools"]
    }
    properties = tools_by_name["get_trades"]["inputSchema"]["json"]["properties"]

    assert properties["sort_by"]["anyOf"][0]["enum"] == [
        "date",
        "value",
        "ticker",
        "price",
        "shares",
        "type",
    ]
    assert properties["sort_by"]["anyOf"][1] == {"type": "null"}
    assert properties["sort_desc"]["anyOf"] == [
        {"type": "boolean"},
        {"type": "null"},
    ]
    assert properties["limit"]["maximum"] == 50


def test_list_results_sort_allowlisted_values_and_apply_requested_limit():
    result = {
        "holdings": [
            {"ticker": "A", "value": 10.0},
            {"ticker": "B", "value": None},
            {"ticker": "C", "value": 30.0},
            {"ticker": "D", "value": 20.0},
        ]
    }

    limited = chatbot_tools._sort_and_limit(
        result,
        key="holdings",
        sort_by="value",
        sort_desc=None,
        limit=3,
    )

    assert [row["ticker"] for row in limited["holdings"]] == ["C", "D", "A"]
    assert limited["truncated"] is True


def test_trade_query_uses_fixed_sort_mapping_and_bound_limit(mocker):
    query_result = pl.DataFrame(
        schema={
            "report_date": pl.Date,
            "buy_sell": pl.String,
            "quantity": pl.Float64,
            "trade_price": pl.Float64,
            "symbol": pl.String,
            "benchmark_price": pl.Float64,
            "benchmark_close": pl.Float64,
            "current_price": pl.Float64,
            "trade_value": pl.Float64,
        }
    )
    read_database = mocker.patch.object(pl, "read_database", return_value=query_result)
    mocker.patch.object(holding, "get_account_id_from_name", return_value=123)
    request = holding.HoldingRequest(
        fund="grad", start="2025-01-01", end="2025-01-31", ticker=None
    )

    result = holding.get_trades(request, sort_by="value", sort_desc=False, limit=7)

    query = read_database.call_args.kwargs["query"]
    parameters = read_database.call_args.kwargs["execute_options"]["parameters"]
    assert "ORDER BY trade_value ASC NULLS LAST" in query
    assert "LIMIT :limit" in query
    assert parameters["limit"] == 7
    assert result["trades"] == []


def test_trade_query_rejects_unallowlisted_sort_before_database_call(mocker):
    read_database = mocker.patch.object(pl, "read_database")
    request = holding.HoldingRequest(
        fund="grad", start="2025-01-01", end="2025-01-31", ticker=None
    )

    with pytest.raises(ValueError, match="Unsupported trade sort column"):
        holding.get_trades(request, sort_by="date; DROP TABLE trades", limit=5)

    read_database.assert_not_called()
