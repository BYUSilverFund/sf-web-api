"""Execute the real route/runtime and, when checked out, the evaluation consumer."""

import importlib.util
import json
from pathlib import Path
import os

import pytest

from app.auth import cognito_auth
from app.services import chatbot


def test_api_evidence_is_exactly_what_generation_received(test_client, mocker):
    sources = [
        {
            "citation": 4,
            "documentKey": "fixture.pdf",
            "page": 2,
            "pdfPages": [2, 3],
            "excerpt": "Evidence café",
            "truncated": False,
        }
    ]
    mocker.patch.object(chatbot, "embed_question", return_value=[1.0])
    mocker.patch.object(chatbot, "retrieve_sources", return_value=sources)
    client = mocker.patch.object(chatbot, "_bedrock_client").return_value
    client.converse_stream.return_value = {
        "stream": [
            {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"text": "Answer [4]"},
                }
            }
        ]
    }
    test_client.app.dependency_overrides[cognito_auth] = lambda: {"sub": "offline"}
    try:
        response = test_client.post("/chat/stream", json={"message": "Explain"})
    finally:
        test_client.app.dependency_overrides.pop(cognito_auth, None)
    assert response.status_code == 200
    frames = response.text.strip().split("\n\n")
    payload = json.loads(frames[-2].split("data: ", 1)[1])
    assert payload["sources"] == sources
    assert payload["answerContexts"] == chatbot.source_contexts(sources)
    text = client.converse_stream.call_args.kwargs["messages"][0]["content"][0]["text"]
    assert text == "Question:\nExplain\n\nRetrieved excerpts:\n" + "\n\n".join(
        payload["answerContexts"]
    )


def test_actual_api_stream_with_actual_evaluation_parser(mocker):
    path = Path(
        os.getenv(
            "SF_EVALUATION_ADAPTER",
            str(
                Path(__file__).resolve().parents[3] / "sf-chatbot/app/evaluation/api.py"
            ),
        )
    )
    if not path.exists():
        pytest.skip("Sibling sf-chatbot checkout required for consumer contract check")
    spec = importlib.util.spec_from_file_location("sf_evaluation_adapter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sources = [
        {
            "citation": 2,
            "documentKey": "fixture.pdf",
            "page": 1,
            "pdfPages": [1, 2],
            "excerpt": "Evidence",
        }
    ]
    mocker.patch.object(chatbot, "embed_question", return_value=[1.0])
    mocker.patch.object(chatbot, "retrieve_sources", return_value=sources)
    mocker.patch.object(
        chatbot, "_stream_answer", return_value=iter(["Answer ", "[2]"])
    )
    data = "".join(chatbot.stream_chat_events("Question", "offline")).encode()
    result = module.parse_response(bytes([byte]) for byte in data)
    assert result["answer_contexts"] == chatbot.source_contexts(sources)
    assert result["sources"][0]["pdf_pages"] == [1, 2]
    assert result["api_sources"] == sources
    mocker.patch.object(
        chatbot, "retrieve_sources", side_effect=RuntimeError("offline failure")
    )
    with pytest.raises(module.EvaluationError):
        module.parse_response(
            frame.encode()
            for frame in chatbot.stream_chat_events("Question", "offline")
        )


def test_current_local_schema_matches_ingestion_contract():
    root = Path(__file__).resolve().parents[2]
    sql = (root / "migrations/002_chatbot_ingestion_schema.sql").read_text()
    assert "VECTOR(1024)" in sql
    assert "pdf_pages JSONB NOT NULL" in sql
    sibling = root.parent / "sf-chatbot/db/init/01-chatbot-schema.sql"
    if sibling.exists():
        assert sql.split("\n", 1)[1] == sibling.read_text()


def test_question_embeddings_match_ingestion_vector_contract(monkeypatch, mocker):
    import io

    monkeypatch.delenv("BEDROCK_EMBEDDING_MODEL_ID", raising=False)
    client = mocker.patch.object(chatbot, "_bedrock_client").return_value
    client.invoke_model.return_value = {
        "body": io.BytesIO(
            json.dumps({"embedding": [0.0] * chatbot.EMBEDDING_DIMENSIONS}).encode()
        )
    }
    vector = chatbot.embed_question("Question")
    call = client.invoke_model.call_args.kwargs
    assert call["modelId"] == "amazon.titan-embed-text-v2:0"
    assert json.loads(call["body"]) == {
        "inputText": "Question",
        "dimensions": 1024,
        "normalize": True,
    }
    assert len(vector) == 1024
