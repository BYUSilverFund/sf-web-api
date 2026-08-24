"""
Shared test configuration and fixtures.
"""

from datetime import date, timedelta

import polars as pl
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def test_client():
    """Create a test client for FastAPI."""
    return TestClient(app)


@pytest.fixture
def sample_date_range():
    """Provide a standard date range for testing."""
    end = date(2025, 8, 20)
    start = end - timedelta(days=365)
    return start, end


@pytest.fixture
def mock_db_engine(mocker):
    """Mock the database engine."""
    return mocker.MagicMock()


@pytest.fixture
def sample_fund_returns_df():
    """Create sample fund returns data as Polars DataFrame."""
    start = date(2024, 8, 20)
    dates = [start + timedelta(days=i) for i in range(252)]

    df = pl.DataFrame(
        {
            "date": dates,
            "value": [100.0 + (i * 0.05) for i in range(252)],
            "return": [0.0001 * (i % 5) for i in range(252)],
            "dividends": [0.1 if i % 20 == 0 else 0.0 for i in range(252)],
        }
    )
    return df


@pytest.fixture
def sample_benchmark_df():
    """Create sample benchmark data as Polars DataFrame."""
    start = date(2024, 8, 20)
    dates = [start + timedelta(days=i) for i in range(252)]

    df = pl.DataFrame(
        {
            "date": dates,
            "return": [0.00008 * (i % 5) for i in range(252)],
        }
    )
    return df


@pytest.fixture
def sample_risk_free_rate_df():
    """Create sample risk-free rate data as Polars DataFrame."""
    start = date(2024, 8, 20)
    dates = [start + timedelta(days=i) for i in range(252)]

    df = pl.DataFrame(
        {
            "date": dates,
            "return": [0.00002 for _ in range(252)],
        }
    )
    return df


@pytest.fixture
def mock_fund_db_read_database(
    mocker, sample_fund_returns_df, sample_benchmark_df, sample_risk_free_rate_df
):
    """Mock pl.read_database to return sample data based on query."""

    def read_database_side_effect(query, connection=None, *args, **kwargs):
        if "all_fund_returns" in query:
            return sample_fund_returns_df
        elif "benchmark" in query:
            return sample_benchmark_df
        elif "risk_free_rate" in query:
            return sample_risk_free_rate_df
        return pl.DataFrame()

    return mocker.patch("polars.read_database", side_effect=read_database_side_effect)


@pytest.fixture
def mock_cognito_jwks(mocker):
    """Mock Cognito JWKS endpoint."""
    return mocker.patch(
        "app.auth._get_jwks",
        return_value={
            "keys": [
                {
                    "kid": "test-key-id",
                    "kty": "RSA",
                    "alg": "RS256",
                    "n": "test-n",
                    "e": "AQAB",
                }
            ]
        },
    )


@pytest.fixture
def valid_jwt_token():
    """Provide a sample JWT token string for testing."""
    # This is a mock token - in real tests, you'd generate proper JWTs
    return "eyJhbGciOiJSUzI1NiIsImtpZCI6InRlc3Qta2V5LWlkIn0.eyJzdWIiOiJ1c2VyMTIzIiwiaWF0IjoxNjk0MDE0NDAwLCJleHAiOjMzODgwMjg4MDB9.mock-signature"


@pytest.fixture(autouse=True)
def set_test_env_vars(monkeypatch):
    """Set required environment variables for testing."""
    monkeypatch.setenv("COGNITO_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_test123")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "test-app-client-id")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_ENDPOINT", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv(
        "CORS_ACCESS_LIST_CSV", "http://localhost:3000,http://localhost:8080"
    )
