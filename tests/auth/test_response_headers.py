"""Tests for non-blocking API security response headers."""


def test_health_response_includes_security_headers(test_client):
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert (
        response.headers["permissions-policy"]
        == "camera=(), geolocation=(), microphone=()"
    )
