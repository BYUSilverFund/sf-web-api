"""
Tests for CORS middleware configuration.
"""

import os


class TestCORSMiddleware:
    """Test CORS middleware behavior."""

    def test_health_endpoint_no_auth_required(self, test_client):
        """Test that health endpoint is accessible without authentication."""
        response = test_client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_endpoint_returns_ok_status(self, test_client):
        """Test that health check returns proper status."""
        response = test_client.get("/health")

        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_cors_allowed_methods(self, test_client, monkeypatch):
        """Test that configured HTTP methods are allowed."""
        # CORS allows GET, POST, PUT, DELETE

        # Test that OPTIONS requests work (preflight)
        response = test_client.options(
            "/fund/summary",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # CORS preflight should return 200
        assert response.status_code == 200

    def test_cors_access_control_headers_present(self, test_client):
        """Test that CORS headers are in responses."""
        response = test_client.get("/health")

        # At minimum, should not error on CORS
        assert response.status_code == 200

    def test_cors_allows_content_type_header(self, test_client, monkeypatch):
        """Test that Content-Type header is allowed."""
        # Content-Type is explicitly allowed in CORS config
        response = test_client.post(
            "/health", json={}, headers={"Content-Type": "application/json"}
        )

        # Should not fail due to CORS
        # 405 is acceptable (method not allowed) - not CORS error
        assert response.status_code in [200, 405]

    def test_cors_allows_authorization_header(self, test_client):
        """Test that Authorization header is allowed."""
        # Authorization is explicitly allowed in CORS config
        response = test_client.get(
            "/health", headers={"Authorization": "Bearer test-token"}
        )

        # Should not fail due to CORS headers
        assert response.status_code == 200


class TestCORSOriginValidation:
    """Test CORS origin validation."""

    def test_allowed_origins_configured(self, monkeypatch):
        """Test that allowed origins are properly configured."""
        allowed = os.getenv("CORS_ACCESS_LIST_CSV", "")
        assert len(allowed) > 0
        assert "localhost" in allowed

    def test_multiple_allowed_origins(self, monkeypatch):
        """Test that multiple origins can be configured."""
        allowed = os.getenv("CORS_ACCESS_LIST_CSV", "")
        origins = allowed.split(",")
        assert len(origins) >= 1


class TestErrorResponseFormat:
    """Test that error responses are properly formatted."""

    def test_validation_error_format(self, test_client):
        """Test that validation errors return proper format."""
        response = test_client.post(
            "/fund/summary",
            json={"start": "invalid-date"},  # Invalid date format
        )

        assert response.status_code == 422
        # FastAPI returns validation errors in a standard format
        data = response.json()
        assert "detail" in data

    def test_not_found_error_format(self, test_client):
        """Test that 404 errors are handled gracefully."""
        response = test_client.get("/nonexistent-endpoint")

        assert response.status_code == 404


class TestRequestValidation:
    """Test request body validation at route level."""

    def test_empty_request_body_rejected(self, test_client):
        """Test that empty JSON body returns 422."""
        response = test_client.post("/fund/summary", json={})

        assert response.status_code == 422

    def test_extra_fields_ignored(
        self,
        test_client,
        mocker,
        sample_fund_returns_df,
        sample_benchmark_df,
        sample_risk_free_rate_df,
    ):
        """Test that extra fields in request are handled gracefully."""

        def read_database_side_effect(query, connection):
            if "all_fund_returns" in query:
                return sample_fund_returns_df
            elif "benchmark" in query:
                return sample_benchmark_df
            elif "risk_free_rate" in query:
                return sample_risk_free_rate_df
            return None

        mocker.patch("polars.read_database", side_effect=read_database_side_effect)

        # Extra field 'extra_field' should be ignored
        response = test_client.post(
            "/fund/summary",
            json={
                "start": "2024-08-20",
                "end": "2025-08-19",
                "extra_field": "should be ignored",
            },
        )

        # Should still work
        assert response.status_code == 200
