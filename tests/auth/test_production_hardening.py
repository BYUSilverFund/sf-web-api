"""Production-only host and documentation hardening tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def production_client(monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "prod")
    monkeypatch.setenv("TRUSTED_HOSTS_CSV", "api.silverfund.byu.edu")
    return TestClient(create_app())


def test_production_disables_api_documentation(production_client):
    headers = {"host": "api.silverfund.byu.edu"}
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert production_client.get(path, headers=headers).status_code == 404


def test_production_rejects_untrusted_hosts(production_client):
    assert (
        production_client.get(
            "/not-found", headers={"host": "attacker.example"}
        ).status_code
        == 400
    )
    assert (
        production_client.get(
            "/not-found", headers={"host": "api.silverfund.byu.edu"}
        ).status_code
        == 404
    )


def test_health_check_bypasses_host_validation_for_alb(production_client):
    response = production_client.get("/health", headers={"host": "10.0.12.34:5000"})
    assert response.status_code == 200


def test_production_requires_explicit_trusted_hosts(monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "prod")
    monkeypatch.delenv("TRUSTED_HOSTS_CSV", raising=False)
    with pytest.raises(RuntimeError, match="TRUSTED_HOSTS_CSV"):
        create_app()
