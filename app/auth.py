import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt


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
_JWKS_TIMEOUT_SECONDS = 5
_ALLOWED_JWT_ALGS = {"RS256"}


def _get_jwks(force_refresh: bool = False) -> Dict[str, Any]:
    global _jwks_cache, _jwks_last_fetch

    now = time.time()
    if (
        not force_refresh
        and _jwks_cache is not None
        and (now - _jwks_last_fetch) < _JWKS_TTL_SECONDS
    ):
        return _jwks_cache

    try:
        with urllib.request.urlopen(  # nosec B310
            JWKS_URL, timeout=_JWKS_TIMEOUT_SECONDS
        ) as response:
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

    alg = headers.get("alg")
    if alg not in _ALLOWED_JWT_ALGS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported token algorithm",
        )

    jwks = _get_jwks()
    keys = jwks.get("keys", [])

    key_data: Optional[Dict[str, Any]] = None
    for key in keys:
        if key.get("kid") == kid:
            key_data = key
            break

    if key_data is None:
        # One forced refresh in case of key rotation
        jwks = _get_jwks(force_refresh=True)
        keys = jwks.get("keys", [])
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
        claims = jwt.decode(
            token,
            public_key,
            algorithms=list(_ALLOWED_JWT_ALGS),
            issuer=COGNITO_ISSUER,
            options={"verify_aud": False},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to parse or verify token",
        ) from exc

    # Basic claim checks
    # Allow both access and id tokens, but enforce client binding
    token_use = claims.get("token_use")
    client_id = claims.get("client_id") or claims.get("aud")

    if "exp" not in claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing expiration",
        )

    if token_use not in {"access", "id"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported token type",
        )

    if isinstance(client_id, list):
        client_match = COGNITO_APP_CLIENT_ID in client_id
    else:
        client_match = client_id == COGNITO_APP_CLIENT_ID

    if not client_match:
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
