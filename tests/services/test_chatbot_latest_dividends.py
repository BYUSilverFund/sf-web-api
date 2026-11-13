from datetime import date

import pytest

from app.services import chatbot_financial, chatbot_tools


def test_latest_dividends_queries_all_fund_holdings_without_guessed_dates(mocker):
    mocker.patch.object(chatbot_financial, "get_account_id_from_name", return_value=123)
    rows = [
        {
            "date": date(2026, 11, 5),
            "ticker": "ABC",
            "shares": 10,
            "dividends_per_share": 0.2,
            "dividends": 2,
        }
    ]
    connection = mocker.patch.object(
        chatbot_financial.engine, "connect"
    ).return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.all.return_value = rows
    result = chatbot_financial.get_latest_dividends("grad")
    query, params = connection.execute.call_args.args
    assert "MAX(date) OVER ()" in str(query)
    assert "dividends > 0" in str(query) and "LIMIT 51" in str(query)
    assert "BETWEEN" not in str(query)
    assert params == {"account_id": 123, "ticker": None}
    assert result["dividends"] == rows and result["date"] == date(2026, 11, 5)


def test_latest_tool_injects_fund_and_returns_valid_json(mocker):
    service = mocker.patch.object(
        chatbot_tools,
        "get_latest_dividends",
        return_value={
            "fund": "grad",
            "ticker": None,
            "date": None,
            "dividends": [],
            "truncated": False,
        },
    )
    result = chatbot_tools.execute_chatbot_tool(
        "get_latest_dividends", {}, selected_fund="grad"
    )
    service.assert_called_once_with("grad", None)
    assert result["dividends"] == [] and result["date"] is None
    with pytest.raises(chatbot_tools.InvalidToolRequest):
        chatbot_tools.execute_chatbot_tool(
            "get_latest_dividends", {"fund": "quant"}, selected_fund="grad"
        )
    service.assert_called_once()


def test_latest_tool_normalizes_only_explicit_ticker(mocker):
    service = mocker.patch.object(
        chatbot_tools,
        "get_latest_dividends",
        return_value={
            "fund": "grad",
            "ticker": "GOOG",
            "date": None,
            "dividends": [],
            "truncated": False,
        },
    )
    chatbot_tools.execute_chatbot_tool(
        "get_latest_dividends", {"ticker": "goog"}, selected_fund="grad"
    )
    service.assert_called_once_with("grad", "GOOG")


def test_latest_dividends_empty_result_is_not_a_fabricated_zero(mocker):
    connection = mocker.patch.object(
        chatbot_financial.engine, "connect"
    ).return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.all.return_value = []
    result = chatbot_financial.get_latest_dividends("grad")
    assert result["date"] is None and result["dividends"] == []


def test_latest_dividends_limits_tied_receipts_and_reports_truncation(mocker):
    connection = mocker.patch.object(
        chatbot_financial.engine, "connect"
    ).return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.all.return_value = [
        {"date": date(2026, 11, 5), "ticker": str(i), "dividends": 1} for i in range(51)
    ]
    result = chatbot_financial.get_latest_dividends("grad", "GOOG")
    assert len(result["dividends"]) == 50 and result["truncated"] is True
    assert connection.execute.call_args.args[1]["ticker"] == "GOOG"
