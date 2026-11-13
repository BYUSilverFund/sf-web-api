"""Financial routing, common-date coverage and fund isolation regressions."""

from datetime import date, timedelta
from decimal import Decimal
import json

import pytest
from botocore.session import Session
from botocore.validate import validate_parameters

from app.services import chatbot, chatbot_financial as financial, chatbot_tools
from tests.services.test_chatbot_tool_budget import (
    finished,
    text_response,
    tool_response,
)

pytest_plugins = ["tests.services.test_chatbot_tool_budget"]

QUESTION = "What fund holds the highest value?"
TODAY = date(2026, 11, 12)
AS_OF = TODAY - timedelta(days=1)


def coverage_rows(*, missing=False, stale=False, different_dates=False, ties=False):
    rows = []
    for index, fund in enumerate(financial.FUND_ALIASES):
        day = AS_OF - timedelta(days=index) if different_dates else AS_OF
        latest = (
            None
            if missing
            else TODAY - timedelta(days=40)
            if stale and index == 4
            else day
        )
        rows.append(
            dict(
                fund=fund,
                reference_date=TODAY,
                latest_date=latest,
                date=day if latest and latest >= TODAY - timedelta(days=7) else None,
                value=Decimal("100.10") if ties else Decimal(100 + index),
            )
        )
    return rows


def query_mock(mocker, rows):
    connection = mocker.patch.object(
        financial.engine, "connect"
    ).return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.all.return_value = rows
    return connection


def test_comparison_common_date_partial_coverage_and_bounded_query(mocker):
    rows = coverage_rows(stale=True)
    # Undergrad has newer data but must use the common date for the ranking.
    rows.append(
        {**rows[0], "date": TODAY, "latest_date": TODAY, "value": Decimal(9999)}
    )
    connection = query_mock(mocker, rows)
    result = financial.compare_fund_values()
    assert result["comparison_status"] == "partial"
    assert result["as_of_date"] == AS_OF
    assert result["leaders"] == ["grad"]
    assert result["ranking"][-1] == {"fund": "undergrad", "value": Decimal(100)}
    assert result["coverage"][-1]["status"] == "stale"
    connection.execute.assert_called_once()
    query, params = connection.execute.call_args.args
    assert "CURRENT_DATE - 7" in str(query)
    assert "f.date <= CURRENT_DATE" in str(query)
    assert "NaN" in str(query)
    assert len(params) == 10
    assert "currency metadata is unavailable" in result["currency_note"]


@pytest.mark.parametrize(
    "kwargs,status",
    [
        ({"missing": True}, "insufficient_data"),
        ({"different_dates": True}, "no_common_date"),
        ({"ties": True}, "complete"),
    ],
)
def test_missing_nonoverlapping_and_tied_values(mocker, kwargs, status):
    query_mock(mocker, coverage_rows(**kwargs))
    result = financial.compare_fund_values()
    assert result["comparison_status"] == status
    if kwargs.get("ties"):
        assert len(result["leaders"]) == 5
    else:
        assert not result["leaders"] and not result["ranking"]


def test_dispatch_is_read_only_strict_and_selected_fund_cannot_bypass(mocker):
    service = mocker.patch.object(
        chatbot_tools,
        "compare_fund_values",
        return_value={"value": Decimal("1.25"), "date": AS_OF},
    )
    assert chatbot_tools.execute_chatbot_tool("compare_fund_values", {}) == {
        "value": "1.25",
        "date": "2026-11-11",
    }
    for arguments in ({}, {"fund": "grad"}, {"fund": "all_funds"}):
        with pytest.raises(chatbot_tools.InvalidToolRequest):
            chatbot_tools.execute_chatbot_tool(
                "compare_fund_values", arguments, selected_fund="grad"
            )
    with pytest.raises(chatbot_tools.InvalidToolRequest):
        chatbot_tools.execute_chatbot_tool("compare_fund_values", {"fund": "grad"})
    service.assert_called_once()


def test_exact_all_funds_question_forces_tool_and_streams_answer(pipeline):
    client, execute, _, _ = pipeline
    chatbot.retrieve_sources.return_value = []
    execute.return_value = {
        "comparison_status": "partial",
        "as_of_date": "2026-11-11",
        "leaders": ["grad"],
    }
    client.converse_stream.side_effect = [
        tool_response(("compare-1", "compare_fund_values", {})),
        text_response(
            "Grad has the highest reported value among included funds as of November 11. Quant Paper is excluded."
        ),
    ]
    events = list(chatbot.stream_chat_events(QUESTION, "financial-route"))
    execute.assert_called_once_with("compare_fund_values", {})
    first = client.converse_stream.call_args_list[0].kwargs
    assert first["toolConfig"]["toolChoice"] == {
        "tool": {"name": "compare_fund_values"}
    }
    shape = (
        Session()
        .get_service_model("bedrock-runtime")
        .operation_model("ConverseStream")
        .input_shape
    )
    validate_parameters(first, shape)
    second = client.converse_stream.call_args_list[1].kwargs
    assert (
        second["messages"][-1]["content"][0]["toolResult"]["content"][0]["json"]
        == execute.return_value
    )
    assert "event: done" in events[-1]
    assert '"answerContexts": []' in "".join(events)
    assert "highest reported value" in "".join(events)
    spans = finished(pipeline)
    assert any(s.attributes.get("tool.name") == "compare_fund_values" for s in spans)
    assert any(s.name == "chatbot.request" for s in spans)


def test_selected_fund_comparison_requests_selector_change_without_database(pipeline):
    client, execute, _, _ = pipeline
    events = list(chatbot.stream_chat_events(QUESTION, "selected", "grad"))
    assert "Select All Funds" in "".join(events)
    assert "event: done" in events[-1]
    client.converse_stream.assert_not_called()
    execute.assert_not_called()
    chatbot.retrieve_sources.assert_not_called()


@pytest.mark.parametrize("failure", ["unavailable", "ignored"])
def test_unavailable_required_comparison_signals_controlled_error(pipeline, failure):
    client, execute, _, _ = pipeline
    if failure == "unavailable":
        client.converse_stream.return_value = tool_response(
            ("c", "compare_fund_values", {})
        )
        execute.side_effect = RuntimeError("database unavailable")
    else:
        client.converse_stream.return_value = text_response(
            "No usable document evidence"
        )
    events = "".join(chatbot.stream_chat_events(QUESTION, "failure"))
    assert "event: error" in events and "event: done" not in events
    assert "No usable document evidence" not in events
    assert any(s.status.status_code.name == "ERROR" for s in finished(pipeline))


def test_missing_data_is_evidence_not_document_fallback(pipeline):
    client, execute, _, _ = pipeline
    execute.return_value = {
        "comparison_status": "insufficient_data",
        "ranking": [],
        "leaders": [],
    }
    client.converse_stream.side_effect = [
        tool_response(("c", "compare_fund_values", {})),
        text_response("Fund values are unavailable; I cannot rank the funds."),
    ]
    events = "".join(chatbot.stream_chat_events(QUESTION, "missing"))
    assert "event: done" in events and "cannot rank" in events
    assert json.dumps(execute.return_value) in json.dumps(
        client.converse_stream.call_args.kwargs
    )


def test_document_question_keeps_auto_tools_and_document_fallback(pipeline):
    client, _, _, _ = pipeline
    client.converse_stream.return_value = text_response(
        "No usable document evidence is available."
    )
    list(
        chatbot.stream_chat_events(
            "What does the manual say about fund value?", "document"
        )
    )
    request = client.converse_stream.call_args.kwargs
    assert request["toolConfig"]["toolChoice"] == {"auto": {}}
    assert "If a document question has no" in request["system"][0]["text"]


def test_selected_fund_does_not_advertise_comparison_tool(pipeline):
    client, _, _, _ = pipeline
    client.converse_stream.return_value = text_response("Answer")
    list(chatbot.stream_chat_events("How are my holdings doing?", "individual", "grad"))
    tools = client.converse_stream.call_args.kwargs["toolConfig"]["tools"]
    assert "compare_fund_values" not in [tool["toolSpec"]["name"] for tool in tools]


@pytest.mark.parametrize("fresh_count", [0, 1])
def test_stale_funds_cannot_create_a_winner(mocker, fresh_count):
    rows = coverage_rows()
    for row in rows[fresh_count:]:
        row.update(latest_date=TODAY - timedelta(days=8), date=None, value=None)
    query_mock(mocker, rows)
    result = financial.compare_fund_values()
    assert result["comparison_status"] == "insufficient_data"
    assert not result["leaders"]
    assert (
        sum(row["status"] == "stale" for row in result["coverage"]) == 5 - fresh_count
    )


@pytest.mark.parametrize(
    "question,expected",
    [
        (QUESTION, True),
        ("Compare fund values", True),
        ("Which fund has the largest portfolio?", True),
        ("Which fund has the largest individual holding value?", False),
        ("What does the manual define as highest fund value?", False),
        ("Which fund has the highest return?", False),
    ],
)
def test_comparison_route_is_conservative(question, expected):
    assert chatbot._fund_value_comparison(question) is expected
