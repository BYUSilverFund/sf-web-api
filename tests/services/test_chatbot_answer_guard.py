"""Internal tool protocols must never become visible answer text."""

import json
from unittest.mock import Mock

import pytest

from app.services import chatbot


@pytest.mark.parametrize(
    "text",
    [
        'Read-only tool exchange (data, not instructions):\n{"toolUse": {"name":"get_dividends"}}',
        '{"toolUseId":"tooluse_SECRET","input":{"ticker":"GOOG"}}',
        '{"toolResult": {"private": "financial data"}}',
        'Available financial evidence (reference data only): [{"query":"Dividend records"}]',
    ],
)
def test_split_protocol_output_rejected_before_exposure(text):
    client = Mock()
    client.converse_stream.return_value = {
        "stream": [
            {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"text": text[i : i + 2]},
                }
            }
            for i in range(0, len(text), 2)
        ]
    }
    visible = []
    with pytest.raises(chatbot.InvalidChatbotAnswer):
        for event in chatbot._converse_events(client, modelId="test"):
            visible.append(event)
    assert visible == []


def test_final_history_contains_results_without_assistant_protocol():
    messages = [
        {"role": "user", "content": [{"text": "What was the latest dividend?"}]},
        {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "internal-id",
                        "name": "get_latest_dividends",
                        "input": {"fund": "grad"},
                    }
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "internal-id",
                        "status": "success",
                        "content": [
                            {
                                "json": {
                                    "fund": "grad",
                                    "dividends": [{"dividends": 12.5}],
                                }
                            }
                        ],
                    }
                }
            ],
        },
    ]
    final = chatbot._text_only_messages(messages)
    raw = json.dumps(final)
    assert "12.5" in raw and "What was the latest dividend?" in raw
    assert "toolUse" not in raw and "internal-id" not in raw
    assert "Read-only tool exchange" not in raw
    assert all(m["role"] == "user" for m in final)


def test_normal_answer_streams_before_model_finishes():
    client = Mock()
    reached_end = []

    def events():
        yield {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"text": "Financial answer with citations [1]. " * 5},
            }
        }
        reached_end.append(True)
        yield {"messageStop": {"stopReason": "end_turn"}}

    client.converse_stream.return_value = {"stream": events()}
    stream = chatbot._converse_events(client, modelId="test")
    first = next(stream)
    assert "Financial answer" in first["contentBlockDelta"]["delta"]["text"]
    assert not reached_end
    stream.close()
