import json
from unittest.mock import MagicMock

import pytest

from app.services import chatbot


@pytest.mark.parametrize(
    "block",
    [
        "$$\n" + "x + y = z\n" * 150 + "\n$$",
        "\\[\n" + "x + y = z\n" * 150 + "\n\\]",
        "\\begin{align}\n" + "x &= y\n" * 200 + "\n\\end{align}",
        "| A | B |\n| --- | --- |\n" + "| 1 | 2 |\n" * 150,
        "```python\n" + "value = 1\n" * 150 + "\n```",
        "A paragraph with $x = y$ " * 80,
    ],
)
def test_complete_blocks_extend_soft_target(block):
    assert (
        chatbot._bounded_excerpt(block + "\n\nLater paragraph", 6000) == block.rstrip()
    )


@pytest.mark.parametrize("opening", ["$$", "\\[", "\\begin{align}", "```"])
def test_unclosed_blocks_are_omitted(opening):
    assert chatbot._bounded_excerpt("Intro\n\n" + opening + "\nx = y", 6000) == "Intro"


def test_long_block_is_omitted_without_partial_evidence():
    assert chatbot._bounded_excerpt("x" * 6001, 6000) == ""
    assert chatbot._bounded_excerpt("Intro\n\n" + "x" * 6001, 6000) == "Intro"


def test_retrieval_budget_metadata_and_stream_consistency(mocker):
    rows = [
        dict(
            document_key=f"doc-{i}",
            page=2,
            excerpt="x" * 5900,
            source_metadata={
                "page_start": 2,
                "page_end": 3,
                "pages": [2, 3],
                "pdf_pages": [2, 3],
            },
        )
        for i in range(5)
    ]
    connection = MagicMock()
    connection.execute.side_effect = [
        MagicMock(
            **{
                "mappings.return_value.one.return_value": {
                    "ingestion_state_table": True,
                    "embeddings_table": True,
                }
            }
        ),
        MagicMock(**{"mappings.return_value": rows}),
    ]
    mocker.patch.object(
        chatbot.engine, "connect"
    ).return_value.__enter__.return_value = connection
    sources = chatbot.retrieve_sources([0.0])
    assert len(sources) == 4
    assert sum(len(s["excerpt"]) for s in sources) <= chatbot.MAX_CONTEXT_CHARS
    assert sources[0]["pageEnd"] == 3
    assert sources[0]["pages"] == [2, 3]
    assert sources[0]["pdfPages"] == [2, 3]
    assert not sources[0]["truncated"]
    assert (
        connection.execute.call_args.args[0].text.count("ORDER BY chunks.embedding <=>")
        == 1
    )
    assert connection.execute.call_args.args[1]["limit"] == 5

    mocker.patch.object(chatbot, "embed_question", return_value=[0.0])
    mocker.patch.object(chatbot, "retrieve_sources", return_value=sources)
    client = mocker.patch.object(chatbot, "_bedrock_client").return_value
    client.converse_stream.return_value = {"stream": []}
    events = list(chatbot.stream_chat_events("Question", "req"))
    returned = json.loads(
        next(e.split("data: ", 1)[1] for e in events if e.startswith("event: sources"))
    )
    assert returned["sources"] == sources
    prompt = client.converse_stream.call_args.kwargs["messages"][0]["content"][0][
        "text"
    ]
    for source in sources:
        assert source["excerpt"] in prompt
        assert json.dumps({k: v for k, v in source.items() if k != "excerpt"}) in prompt


def test_truncation_at_block_boundary(mocker):
    text = "a" * 1200 + "\n\nOmitted"
    assert chatbot._bounded_excerpt(text, 6000) == "a" * 1200


def test_remaining_budget_keeps_whole_prefix():
    text = "a" * 900 + "\n\n" + "b" * 900
    assert chatbot._bounded_excerpt(text, 1000) == "a" * 900
    assert chatbot._bounded_excerpt(text, 1802) == text


def _retrieve_rows(mocker, rows):
    connection = mocker.patch.object(
        chatbot.engine, "connect"
    ).return_value.__enter__.return_value
    connection.execute.side_effect = [
        MagicMock(
            **{
                "mappings.return_value.one.return_value": {
                    "ingestion_state_table": True,
                    "embeddings_table": True,
                }
            }
        ),
        MagicMock(**{"mappings.return_value": rows}),
    ]
    return chatbot.retrieve_sources([0.0])


def test_omitted_blocks_keep_citation_gaps_and_visible_warning(mocker):
    omitted_equation = "$$\n" + "x = y\n" * 1100 + "$$"
    rows = [
        {"document_key": "oversized-only", "page": 1, "excerpt": omitted_equation},
        {
            "document_key": "prefix",
            "page": 2,
            "excerpt": "Introduction\n\n" + omitted_equation,
        },
        {"document_key": "complete", "page": 4, "excerpt": "Complete evidence"},
    ]
    sources = _retrieve_rows(mocker, rows)
    assert [s["citation"] for s in sources] == [2, 3]
    assert sources[0]["truncated"] is True
    assert sources[0]["excerpt"] == "Introduction" + chatbot.SOURCE_TRUNCATION_NOTICE
    assert sources[1]["truncated"] is False
    assert all("$$" not in s["excerpt"] for s in sources)

    mocker.patch.object(chatbot, "embed_question", return_value=[0.0])
    mocker.patch.object(chatbot, "retrieve_sources", return_value=sources)
    client = mocker.patch.object(chatbot, "_bedrock_client").return_value
    client.converse_stream.return_value = {"stream": []}
    events = list(chatbot.stream_chat_events("Explain", "test"))
    returned = json.loads(
        next(e.split("data: ", 1)[1] for e in events if e.startswith("event: sources"))
    )
    assert returned["sources"] == sources
    prompt = client.converse_stream.call_args.kwargs["messages"][0]["content"][0][
        "text"
    ]
    assert "oversized-only" not in prompt
    assert omitted_equation not in prompt
    assert sources[0]["excerpt"] in prompt
    assert "[2] prefix" in prompt and "[3] complete" in prompt


@pytest.mark.parametrize("size", [5999, 6000, 6001])
def test_notice_cannot_break_hard_cap_or_survive_without_evidence(mocker, size):
    sources = _retrieve_rows(
        mocker,
        [
            {"document_key": "doc", "page": 1, "excerpt": "a" * size + "\n\nOmitted"},
        ],
    )
    # The prefix cannot fit alongside its warning: omit the whole source.
    assert sources == []


def test_notice_is_included_in_total_budget(mocker):
    sources = _retrieve_rows(
        mocker,
        [
            {
                "document_key": str(i),
                "page": i + 1,
                "excerpt": "a" * 5800 + "\n\n" + "b" * 6001,
            }
            for i in range(chatbot.MAX_SOURCES)
        ],
    )
    assert len(sources) == 4
    assert all(s["truncated"] for s in sources)
    assert all(s["excerpt"].endswith(chatbot.SOURCE_TRUNCATION_NOTICE) for s in sources)
    assert all(len(s["excerpt"]) <= chatbot.MAX_SOURCE_CHARS for s in sources)
    assert sum(len(s["excerpt"]) for s in sources) <= chatbot.MAX_CONTEXT_CHARS


def test_no_evidence_does_not_claim_library_is_unindexed(mocker):
    sources = _retrieve_rows(
        mocker,
        [
            {"document_key": "doc", "page": 1, "excerpt": "x" * 6001},
        ],
    )
    assert sources == []
    client = mocker.patch.object(chatbot, "_bedrock_client").return_value
    client.converse_stream.return_value = {"stream": []}
    list(chatbot._stream_answer("Question", sources, "test"))
    system = client.converse_stream.call_args.kwargs["system"][0]["text"]
    assert "no usable document evidence" in system
    assert "library is not indexed" not in system


@pytest.mark.parametrize(
    "value",
    [None, [], "[2, 3]", [True], [-1], [0], [2, "3"], [2**31], list(range(1, 102))],
)
def test_invalid_or_oversized_page_lists_are_omitted(mocker, value):
    sources = _retrieve_rows(
        mocker,
        [
            {
                "document_key": "doc",
                "page": 2,
                "excerpt": "Evidence",
                "source_metadata": {
                    "pdf_pages": value,
                    "pages": value,
                    "page_start": True,
                    "page_end": -1,
                },
            },
        ],
    )
    assert sources == [
        {
            "citation": 1,
            "documentKey": "doc",
            "page": 2,
            "excerpt": "Evidence",
            "truncated": False,
        }
    ]


def test_whitespace_normalization_does_not_falsely_claim_omission(mocker):
    original = "\n\n  Indented paragraph\n\n\nNext paragraph  \n\n"
    sources = _retrieve_rows(
        mocker,
        [
            {"document_key": "doc", "page": 1, "excerpt": original},
        ],
    )
    assert sources[0]["excerpt"] == original.lstrip("\r\n").rstrip()
    assert sources[0]["truncated"] is False
    assert chatbot.SOURCE_TRUNCATION_NOTICE not in sources[0]["excerpt"]
