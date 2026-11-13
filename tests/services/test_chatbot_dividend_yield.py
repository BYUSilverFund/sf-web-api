"""Dividend cash receipts must never masquerade as a portfolio yield."""

import pytest

from app.services import chatbot


@pytest.mark.parametrize("spelling", ["yield", "yeil", "yeild", "yiel", "yeld"])
def test_current_dividend_yield_asks_for_period_without_querying_receipts(
    mocker, spelling
):
    embed = mocker.patch.object(chatbot, "embed_question")
    infer = mocker.patch.object(chatbot, "_stream_answer")
    events = "".join(
        chatbot.stream_chat_events(
            f"what is our current dividend {spelling}",
            "yield-question",
            "brigham_capital",
        )
    )
    assert "trailing 12-month or year-to-date" in events
    assert "Brigham Capital" in events
    assert '"answerContexts": []' in events and "event: done" in events
    assert "event: error" not in events
    embed.assert_not_called()
    infer.assert_not_called()


@pytest.mark.parametrize(
    "question",
    [
        "What is our trailing 12-month dividend yield?",
        "What is our YTD dividend yield?",
        "What is our dividend yield in 2026?",
        "How is dividend yield calculated?",
        "What does the manual say about dividend yield?",
        "What was our latest dividend received?",
    ],
)
def test_period_definition_and_receipt_requests_keep_existing_pipeline(question):
    assert not chatbot._dividend_yield_needs_period(question)


def test_cross_fund_clarification_precedes_yield_period(mocker):
    embed = mocker.patch.object(chatbot, "embed_question")
    events = "".join(
        chatbot.stream_chat_events(
            "What is Grad's current dividend yield?", "conflict", "brigham_capital"
        )
    )
    assert "different fund" in events
    embed.assert_not_called()


def test_all_funds_yield_requests_fund_and_period(mocker):
    embed = mocker.patch.object(chatbot, "embed_question")
    events = "".join(
        chatbot.stream_chat_events("what is our current dividend yield", "all")
    )
    assert "select or name the fund" in events
    embed.assert_not_called()
