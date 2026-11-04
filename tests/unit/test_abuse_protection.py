import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.abuse_protection import AbuseProtectionMiddleware, RouteLimit


def _client(
    *,
    max_body_bytes: int = 64,
    requests_per_minute: int = 2,
    max_concurrent_requests: int = 1,
    trust_forwarded_for: bool = False,
    chat_handler=None,
) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        AbuseProtectionMiddleware,
        max_request_body_bytes=max_body_bytes,
        chat_limit=RouteLimit(requests_per_minute, max_concurrent_requests),
        export_limit=RouteLimit(requests_per_minute, max_concurrent_requests),
        trust_forwarded_for=trust_forwarded_for,
    )

    @app.post("/chat/stream")
    def chat():
        if chat_handler:
            return chat_handler()
        return {"ok": True}

    @app.post("/fund/all-funds/csv")
    def export():
        return {"ok": True}

    return TestClient(app)


def test_rejects_oversized_request_body():
    client = _client(max_body_bytes=4)

    response = client.post("/chat/stream", content=b"12345")

    assert response.status_code == 413
    assert response.headers["x-request-id"]
    assert response.json()["detail"] == "Request body is too large."


def test_rate_limits_expensive_chat_route_and_emits_request_id():
    client = _client(requests_per_minute=2)

    first = client.post("/chat/stream")
    second = client.post("/chat/stream")
    rejected = client.post("/chat/stream")

    assert first.status_code == 200
    assert first.headers["x-request-id"]
    assert second.status_code == 200
    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "60"


def test_rate_limits_csv_exports():
    client = _client(requests_per_minute=1)

    assert client.post("/fund/all-funds/csv").status_code == 200
    assert client.post("/fund/all-funds/csv").status_code == 429


def test_rejects_concurrent_expensive_requests():
    entered = Event()
    release = Event()

    def slow_chat():
        entered.set()
        release.wait(timeout=2)
        return {"ok": True}

    client = _client(requests_per_minute=10, chat_handler=slow_chat)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first_request = executor.submit(client.post, "/chat/stream")
        assert entered.wait(timeout=2)
        busy_response = client.post("/chat/stream")
        release.set()
        first_response = first_request.result(timeout=2)

    assert first_response.status_code == 200
    assert busy_response.status_code == 429
    assert busy_response.headers["retry-after"] == "1"


def test_audit_log_uses_forwarded_client_ip_without_request_body(caplog):
    caplog.set_level(logging.INFO, logger="app.abuse_protection")
    client = _client(requests_per_minute=10, trust_forwarded_for=True)

    response = client.post(
        "/chat/stream",
        content=b"sensitive request content",
        headers={"X-Forwarded-For": "198.51.100.8"},
    )

    assert response.status_code == 200
    audit_records = [
        record.getMessage()
        for record in caplog.records
        if "event=api_audit" in record.getMessage()
    ]
    assert any("client_ip=198.51.100.8" in record for record in audit_records)
    assert all("sensitive request content" not in record for record in audit_records)


def test_rejects_chunked_oversized_request_body():
    async def downstream(scope, receive, send):
        while True:
            if not (await receive()).get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = AbuseProtectionMiddleware(
        downstream,
        max_request_body_bytes=4,
        chat_limit=RouteLimit(10, 1),
        export_limit=RouteLimit(10, 1),
    )
    request_messages = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ]
    )
    sent_messages = []

    async def receive():
        return next(request_messages)

    async def send(message):
        sent_messages.append(message)

    asyncio.run(
        middleware(
            {"type": "http", "path": "/chat/stream", "headers": []}, receive, send
        )
    )

    assert sent_messages[0]["status"] == 413
