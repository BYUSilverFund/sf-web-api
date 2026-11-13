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
    assert 'event: sources\ndata: {"sources": [], "answerContexts": []}' in events[3]
    assert "event: done" in events[4]


def test_chat_stream_preserves_source_contract(test_client, mocker, monkeypatch):
    import json

    # Exercise the real router and SSE service; external boundaries stay mocked.
    monkeypatch.delenv("BEDROCK_CHAT_MODEL_ID", raising=False)
    sources = [
        {
            "citation": 2,
            "documentKey": "manual.pdf",
            "page": 4,
            "pdfPages": [4, 5],
            "truncated": True,
            "excerpt": "Introduction" + chatbot_service.SOURCE_TRUNCATION_NOTICE,
        },
        {
            "citation": 5,
            "documentKey": "other.pdf",
            "page": 9,
            "truncated": False,
            "excerpt": "$$x = y$$",
        },
    ]
    mocker.patch.object(chatbot_service, "embed_question", return_value=[0.0])
    mocker.patch.object(chatbot_service, "retrieve_sources", return_value=sources)
    mocker.patch.object(
        chatbot_service.engine,
        "connect",
        side_effect=AssertionError("No database access"),
    )
    client = mocker.patch.object(chatbot_service, "_bedrock_client").return_value
    client.converse_stream.return_value = {
        "stream": [
            {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"text": "Evidence [2] [5]"},
                }
            },
            {"messageStop": {"stopReason": "end_turn"}},
        ]
    }
    app = test_client.app
    app.dependency_overrides[cognito_auth] = lambda: {"sub": "test-user"}
    try:
        response = test_client.post("/chat/stream", json={"message": " Explain "})
    finally:
        app.dependency_overrides.pop(cognito_auth, None)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    frames = response.text.strip().split("\n\n")
    assert [frame.splitlines()[0] for frame in frames] == [
        "event: meta",
        "event: delta",
        "event: sources",
        "event: done",
    ]
    assert json.loads(frames[2].split("data: ", 1)[1])["sources"] == sources
    call = client.converse_stream.call_args.kwargs
    assert call["modelId"] == "us.amazon.nova-2-lite-v1:0"
    assert call["inferenceConfig"] == {"maxTokens": 1200, "temperature": 0}
    prompt = call["messages"][0]["content"][0]["text"]
    assert "Question:\nExplain" in prompt
    for source in sources:
        assert source["excerpt"] in prompt
        assert f"[{source['citation']}] {source['documentKey']}" in prompt


def test_chat_stream_rejects_overlong_message(test_client, mocker):
    app = test_client.app
    app.dependency_overrides[cognito_auth] = lambda: {"sub": "test-user"}
    stream = mocker.patch("app.routers.chatbot.stream_chat_events")
    try:
        response = test_client.post("/chat/stream", json={"message": "x" * 4001})
    finally:
        app.dependency_overrides.pop(cognito_auth, None)
    assert response.status_code == 422
    stream.assert_not_called()


def test_selected_fund_requires_authentication(test_client):
    assert (
        test_client.post(
            "/chat/stream", json={"message": "holdings?", "fund": "quant"}
        ).status_code
        == 401
    )


def test_selected_fund_route_and_validation(test_client, mocker):
    test_client.app.dependency_overrides[cognito_auth] = lambda: {"sub": "test-user"}
    events = mocker.patch(
        "app.routers.chatbot.stream_chat_events",
        return_value=iter(["event: done\ndata: {}\n\n"]),
    )
    try:
        assert (
            test_client.post(
                "/chat/stream", json={"message": "holdings?", "fund": "quant"}
            ).status_code
            == 200
        )
        assert events.call_args.args[2] == "quant"
        events.reset_mock()
        assert (
            test_client.post(
                "/chat/stream", json={"message": "holdings?", "fund": "bogus"}
            ).status_code
            == 422
        )
        events.assert_not_called()
    finally:
        test_client.app.dependency_overrides.pop(cognito_auth, None)
