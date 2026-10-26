from app.auth import cognito_auth
from app.services import chatbot as chatbot_service


def test_chat_stream_requires_authentication(test_client):
    response = test_client.post("/chat/stream", json={"message": "hello"})

    assert response.status_code == 401


def test_chat_stream_returns_sse(test_client, mocker):
    app = test_client.app
    app.dependency_overrides[cognito_auth] = lambda: {"sub": "test-user"}
    mocker.patch(
        "app.routers.chatbot.stream_chat_events",
        return_value=iter(
            [
                'event: meta\ndata: {"requestId":"test"}\n\n',
                'event: delta\ndata: {"text":"hello"}\n\n',
                'event: sources\ndata: {"sources":[]}\n\n',
                "event: done\ndata: {}\n\n",
            ]
        ),
    )
    try:
        response = test_client.post("/chat/stream", json={"message": "  hello  "})
    finally:
        app.dependency_overrides.pop(cognito_auth, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: meta" in response.text
    assert '"text":"hello"' in response.text
    assert "event: sources" in response.text
    assert "event: done" in response.text


def test_chat_stream_rejects_blank_message(test_client, mocker):
    app = test_client.app
    app.dependency_overrides[cognito_auth] = lambda: {"sub": "test-user"}
    try:
        response = test_client.post("/chat/stream", json={"message": "   "})
    finally:
        app.dependency_overrides.pop(cognito_auth, None)

    assert response.status_code == 422


def test_chat_service_streams_events_without_indexed_sources(mocker):
    mocker.patch.object(chatbot_service, "embed_question", return_value=[0.0] * 1024)
    mocker.patch.object(chatbot_service, "retrieve_sources", return_value=[])
    mocker.patch.object(
        chatbot_service, "_stream_answer", return_value=iter(["not ", "indexed"])
    )

    events = list(chatbot_service.stream_chat_events("Where are the docs?", "req-1"))

    assert 'event: meta\ndata: {"requestId": "req-1"}' in events[0]
    assert 'event: delta\ndata: {"text": "not "}' in events[1]
    assert 'event: delta\ndata: {"text": "indexed"}' in events[2]
    assert 'event: sources\ndata: {"sources": []}' in events[3]
    assert "event: done" in events[4]
