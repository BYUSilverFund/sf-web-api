"""
Advanced authentication tests covering JWT validation, JWKS caching, and token lifecycle.
Tests for app/auth.py with focus on security and edge cases.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from jose import jwt

import app.auth as auth_module
from app.auth import (
    _JWKS_TTL_SECONDS,
    COGNITO_APP_CLIENT_ID,
    COGNITO_ISSUER,
    _get_jwks,
    _verify_cognito_token,
)


@pytest.fixture(autouse=True)
def reset_jwks_cache_state():
    """Reset module-level JWKS cache state so cache tests are isolated."""
    auth_module._jwks_cache = None
    auth_module._jwks_last_fetch = 0.0
    yield
    auth_module._jwks_cache = None
    auth_module._jwks_last_fetch = 0.0


class TestJWKSCaching:
    """Test JWKS caching and refresh behavior."""

    def test_jwks_cache_returns_cached_value_within_ttl(self, mocker):
        """Verify that JWKS cache is returned within TTL without fetching."""
        mock_urlopen = mocker.patch("urllib.request.urlopen")
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"keys": [{"kid": "key1", "kty": "RSA"}]}
        ).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # First call - should fetch
        result1 = _get_jwks()
        assert len(result1["keys"]) == 1
        assert mock_urlopen.call_count == 1

        # Second call - should use cache
        result2 = _get_jwks()
        assert result2 == result1
        assert mock_urlopen.call_count == 1  # No additional call

    def test_jwks_cache_refreshes_after_ttl_expires(self, mocker):
        """Verify that JWKS cache is refreshed after TTL expires."""
        mock_urlopen = mocker.patch("urllib.request.urlopen")
        mock_response = MagicMock()
        base_time = time.time()

        # First response
        mock_response.read.return_value = json.dumps(
            {"keys": [{"kid": "key1", "kty": "RSA"}]}
        ).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        _get_jwks()
        assert mock_urlopen.call_count == 1

        # Fast-forward time past TTL
        with patch("app.auth.time.time") as mock_time:
            mock_time.return_value = base_time + _JWKS_TTL_SECONDS + 1

            # Second response
            mock_response.read.return_value = json.dumps(
                {"keys": [{"kid": "key2", "kty": "RSA"}]}
            ).encode()

            _get_jwks()
            assert mock_urlopen.call_count == 2  # New fetch after TTL

    def test_jwks_force_refresh(self, mocker):
        """Verify that force_refresh bypasses TTL cache."""
        mock_urlopen = mocker.patch("urllib.request.urlopen")
        mock_response = MagicMock()

        mock_response.read.return_value = json.dumps(
            {"keys": [{"kid": "key1", "kty": "RSA"}]}
        ).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        _get_jwks()
        assert mock_urlopen.call_count == 1

        _get_jwks(force_refresh=True)
        assert mock_urlopen.call_count == 2

    def test_jwks_fetch_failure_raises_http_exception(self, mocker):
        """Verify that JWKS fetch failure raises HTTPException."""
        mocker.patch(
            "urllib.request.urlopen", side_effect=ConnectionError("Network error")
        )

        with pytest.raises(HTTPException) as exc_info:
            _get_jwks(force_refresh=True)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to retrieve Cognito JWKS" in exc_info.value.detail

    def test_jwks_timeout_raises_http_exception(self, mocker):
        """Verify that JWKS fetch timeout raises HTTPException."""
        mocker.patch("urllib.request.urlopen", side_effect=TimeoutError())

        with pytest.raises(HTTPException) as exc_info:
            _get_jwks(force_refresh=True)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestTokenHeaderValidation:
    """Test JWT header validation."""

    def test_missing_kid_in_header_raises_exception(self, mocker):
        """Verify that missing 'kid' (key ID) in header raises exception."""
        mock_get_headers = mocker.patch("jose.jwt.get_unverified_headers")
        mock_get_headers.return_value = {
            "alg": "RS256",
            # Missing 'kid'
        }

        token = "some.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            _verify_cognito_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing key id" in exc_info.value.detail

    def test_unsupported_algorithm_raises_exception(self, mocker):
        """Verify that unsupported JWT algorithm raises exception."""
        mock_get_headers = mocker.patch("jose.jwt.get_unverified_headers")
        mock_get_headers.return_value = {
            "alg": "HS256",  # Unsupported, only RS256 allowed
            "kid": "test-key",
        }

        token = "some.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            _verify_cognito_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Unsupported token algorithm" in exc_info.value.detail

    def test_invalid_jwt_format_raises_exception(self, mocker):
        """Verify that invalid JWT format raises exception."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            side_effect=Exception("Invalid JWT format"),
        )

        token = "invalid.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            _verify_cognito_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token headers" in exc_info.value.detail


class TestKeyRotation:
    """Test JWT key handling and rotation scenarios."""

    def test_key_not_found_forces_jwks_refresh(self, mocker):
        """Verify that missing key ID triggers JWKS refresh."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "unknown-key",
            },
        )

        # First JWKS response (old key)
        first_keys = [{"kid": "old-key", "kty": "RSA"}]
        # Second JWKS response (after rotation)
        second_keys = [
            {"kid": "old-key", "kty": "RSA"},
            {"kid": "unknown-key", "kty": "RSA", "n": "test", "e": "AQAB"},
        ]

        mock_get_jwks = mocker.patch("app.auth._get_jwks")
        mock_get_jwks.side_effect = [
            {"keys": first_keys},
            {"keys": second_keys},
        ]

        mock_construct = mocker.patch("jose.jwk.construct")
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        # Mock JWT decode to succeed
        mocker.patch(
            "jose.jwt.decode",
            return_value={
                "sub": "user123",
                "exp": int(time.time()) + 3600,
                "token_use": "access",
                "client_id": COGNITO_APP_CLIENT_ID,
            },
        )

        token = "some.jwt.token"
        _verify_cognito_token(token)

        # Should call _get_jwks twice (initial + refresh)
        assert mock_get_jwks.call_count == 2

    def test_key_not_found_after_refresh_raises_exception(self, mocker):
        """Verify that missing key after refresh raises exception."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "missing-key",
            },
        )

        mocker.patch(
            "app.auth._get_jwks",
            return_value={"keys": [{"kid": "other-key", "kty": "RSA"}]},
        )

        token = "some.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            _verify_cognito_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Unable to find matching JWK" in exc_info.value.detail


class TestJWTClaimValidation:
    """Test JWT claim validation."""

    def test_missing_expiration_claim_raises_exception(self, mocker):
        """Verify that missing 'exp' claim raises exception."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "test-key",
            },
        )

        mocker.patch(
            "app.auth._get_jwks",
            return_value={"keys": [{"kid": "test-key", "kty": "RSA"}]},
        )

        mock_construct = mocker.patch("jose.jwk.construct")
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        # Claims without 'exp'
        mocker.patch(
            "jose.jwt.decode",
            return_value={
                "sub": "user123",
                "token_use": "access",
                "client_id": COGNITO_APP_CLIENT_ID,
                # Missing 'exp'
            },
        )

        token = "some.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            _verify_cognito_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "missing expiration" in exc_info.value.detail

    def test_unsupported_token_use_raises_exception(self, mocker):
        """Verify that unsupported token_use claim raises exception."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "test-key",
            },
        )

        mocker.patch(
            "app.auth._get_jwks",
            return_value={"keys": [{"kid": "test-key", "kty": "RSA"}]},
        )

        mock_construct = mocker.patch("jose.jwk.construct")
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        # Unsupported token_use
        mocker.patch(
            "jose.jwt.decode",
            return_value={
                "sub": "user123",
                "exp": int(time.time()) + 3600,
                "token_use": "refresh",  # Only 'access' and 'id' are allowed
                "client_id": COGNITO_APP_CLIENT_ID,
            },
        )

        token = "some.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            _verify_cognito_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Unsupported token type" in exc_info.value.detail

    def test_client_id_mismatch_raises_exception(self, mocker):
        """Verify that client_id mismatch raises exception."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "test-key",
            },
        )

        mocker.patch(
            "app.auth._get_jwks",
            return_value={"keys": [{"kid": "test-key", "kty": "RSA"}]},
        )

        mock_construct = mocker.patch("jose.jwk.construct")
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        # Mismatched client_id
        mocker.patch(
            "jose.jwt.decode",
            return_value={
                "sub": "user123",
                "exp": int(time.time()) + 3600,
                "token_use": "access",
                "client_id": "wrong-client-id",
            },
        )

        token = "some.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            _verify_cognito_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token client does not match" in exc_info.value.detail

    def test_client_id_as_list_matching(self, mocker):
        """Verify that client_id as list (aud claim) is handled correctly."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "test-key",
            },
        )

        mocker.patch(
            "app.auth._get_jwks",
            return_value={"keys": [{"kid": "test-key", "kty": "RSA"}]},
        )

        mock_construct = mocker.patch("jose.jwk.construct")
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        # client_id as list (common in id tokens with aud claim)
        mocker.patch(
            "jose.jwt.decode",
            return_value={
                "sub": "user123",
                "exp": int(time.time()) + 3600,
                "token_use": "id",
                "aud": [COGNITO_APP_CLIENT_ID, "other-client"],
            },
        )

        token = "some.jwt.token"
        result = _verify_cognito_token(token)

        assert result is not None
        assert "sub" in result


class TestSuccessfulTokenVerification:
    """Test successful token verification scenarios."""

    def test_valid_access_token_verification_succeeds(self, mocker):
        """Verify that valid access token is successfully verified."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "test-key",
            },
        )

        mocker.patch(
            "app.auth._get_jwks",
            return_value={"keys": [{"kid": "test-key", "kty": "RSA"}]},
        )

        mock_construct = mocker.patch("jose.jwk.construct")
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        expected_claims = {
            "sub": "user123",
            "exp": int(time.time()) + 3600,
            "token_use": "access",
            "client_id": COGNITO_APP_CLIENT_ID,
        }
        mocker.patch("jose.jwt.decode", return_value=expected_claims)

        token = "some.jwt.token"
        result = _verify_cognito_token(token)

        assert result == expected_claims

    def test_valid_id_token_verification_succeeds(self, mocker):
        """Verify that valid id token is successfully verified."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "test-key",
            },
        )

        mocker.patch(
            "app.auth._get_jwks",
            return_value={"keys": [{"kid": "test-key", "kty": "RSA"}]},
        )

        mock_construct = mocker.patch("jose.jwk.construct")
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        expected_claims = {
            "sub": "user123",
            "email": "user@example.com",
            "exp": int(time.time()) + 3600,
            "token_use": "id",
            "aud": COGNITO_APP_CLIENT_ID,
        }
        mocker.patch("jose.jwt.decode", return_value=expected_claims)

        token = "some.jwt.token"
        result = _verify_cognito_token(token)

        assert result == expected_claims


class TestTokenSignatureVerification:
    """Test JWT signature verification."""

    def test_invalid_signature_raises_exception(self, mocker):
        """Verify that invalid JWT signature raises exception."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "test-key",
            },
        )

        mocker.patch(
            "app.auth._get_jwks",
            return_value={"keys": [{"kid": "test-key", "kty": "RSA"}]},
        )

        mock_construct = mocker.patch("jose.jwk.construct")
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        # JWT decode fails due to invalid signature
        mocker.patch(
            "jose.jwt.decode", side_effect=jwt.JWTError("Signature verification failed")
        )

        token = "some.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            _verify_cognito_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Failed to parse or verify token" in exc_info.value.detail

    def test_token_verification_uses_correct_issuer(self, mocker):
        """Verify that token verification checks issuer claim."""
        mocker.patch(
            "jose.jwt.get_unverified_headers",
            return_value={
                "alg": "RS256",
                "kid": "test-key",
            },
        )

        mocker.patch(
            "app.auth._get_jwks",
            return_value={"keys": [{"kid": "test-key", "kty": "RSA"}]},
        )

        mock_construct = mocker.patch("jose.jwk.construct")
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        mock_decode = mocker.patch(
            "jose.jwt.decode",
            return_value={
                "sub": "user123",
                "exp": int(time.time()) + 3600,
                "token_use": "access",
                "client_id": COGNITO_APP_CLIENT_ID,
            },
        )

        token = "some.jwt.token"
        _verify_cognito_token(token)

        # Verify that decode was called with correct issuer
        call_kwargs = mock_decode.call_args[1]
        assert call_kwargs["issuer"] == COGNITO_ISSUER
