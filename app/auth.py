import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt
from jose.utils import base64url_decode


COGNITO_REGION = os.getenv("COGNITO_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")

if not (COGNITO_REGION and COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID):
    # Fail fast with a clear error if configuration is missing
    missing = [
        name
        for name, value in [
            ("COGNITO_REGION", COGNITO_REGION),
            ("COGNITO_USER_POOL_ID", COGNITO_USER_POOL_ID),
            ("COGNITO_APP_CLIENT_ID", COGNITO_APP_CLIENT_ID),
        ]
        if not value
    ]
    raise RuntimeError(
        f"Missing required Cognito configuration environment variables: {', '.join(missing)}"
    )

COGNITO_ISSUER = (
    f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
)
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

_security_scheme = HTTPBearer(auto_error=False)

_jwks_cache: Optional[Dict[str, Any]] = None
_jwks_last_fetch: float = 0.0
_JWKS_TTL_SECONDS = 3600


def _get_jwks() -> Dict[str, Any]:
    global _jwks_cache, _jwks_last_fetch

    now = time.time()
    if _jwks_cache is not None and (now - _jwks_last_fetch) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    try:
        with urllib.request.urlopen(JWKS_URL) as response:  # nosec B310
            body = response.read().decode("utf-8")
            _jwks_cache = json.loads(body)
            _jwks_last_fetch = now
            return _jwks_cache
    except Exception as exc:  # pragma: no cover - network/infra failure
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve Cognito JWKS",
        ) from exc


def _verify_cognito_token(token: str) -> Dict[str, Any]:
    jwks = _get_jwks()
    keys = jwks.get("keys", [])

    try:
        headers = jwt.get_unverified_headers(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token headers",
        ) from exc

    kid = headers.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing key id in token headers",
        )

    key_data: Optional[Dict[str, Any]] = None
    for key in keys:
        if key.get("kid") == kid:
            key_data = key
            break

    if key_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find matching JWK for token",
        )

    public_key = jwk.construct(key_data)

    try:
        message, encoded_signature = token.rsplit(".", 1)
        decoded_signature = base64url_decode(encoded_signature.encode("utf-8"))

        if not public_key.verify(message.encode("utf-8"), decoded_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
            )

        claims = jwt.get_unverified_claims(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to parse or verify token",
        ) from exc

    # Basic claim checks
    exp = claims.get("exp")
    if exp is None or time.time() > float(exp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is expired",
        )

    issuer = claims.get("iss")
    if issuer != COGNITO_ISSUER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
        )

    # Allow both access and id tokens, but enforce client binding
    token_use = claims.get("token_use")
    client_id = claims.get("client_id") or claims.get("aud")

    if token_use not in {"access", "id"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported token type",
        )

    if client_id != COGNITO_APP_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token client does not match application",
        )

    return claims


async def cognito_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security_scheme),
) -> Dict[str, Any]:
    """FastAPI dependency to protect routes with AWS Cognito.

    - Skips verification for CORS preflight (OPTIONS) requests.
    - Expects an Authorization: Bearer <JWT> header containing a Cognito token.
    - Returns the decoded claims if verification succeeds.
    """

    if request.method == "OPTIONS":
        # Let CORS middleware handle preflight without auth
        return {}

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = credentials.credentials
    return _verify_cognito_token(token)
