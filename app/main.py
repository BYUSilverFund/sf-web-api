import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import Receive, Scope, Send

from app.abuse_protection import AbuseProtectionMiddleware, RouteLimit
from app.response_headers import SecurityResponseHeadersMiddleware
from app.routers import (
    all_holdings,
    all_portfolios,
    benchmark,
    chatbot,
    covariance_matrix,
    factor_exposures,
    fund,
    holding,
    portfolio,
    risk_forecast,
    top_positions,
)


def _positive_int_env(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


def _is_production() -> bool:
    return os.getenv("APP_ENVIRONMENT", "").strip().lower() in {"prod", "production"}


def _trusted_hosts() -> list[str]:
    return [
        host.strip()
        for host in os.getenv("TRUSTED_HOSTS_CSV", "").split(",")
        if host.strip()
    ]


class HealthcheckTrustedHostMiddleware(TrustedHostMiddleware):
    """Allow ALB's IP-address Host header only for the unauthenticated health check."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == "/health":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


def create_app() -> FastAPI:
    production = _is_production()
    trusted_hosts = _trusted_hosts()
    if production and not trusted_hosts:
        raise RuntimeError("TRUSTED_HOSTS_CSV must be set in production")

    app = FastAPI(
        title="Silver Fund API",
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )

    app.add_middleware(
        AbuseProtectionMiddleware,
        max_request_body_bytes=_positive_int_env("MAX_REQUEST_BODY_BYTES", 65_536),
        chat_limit=RouteLimit(
            requests_per_minute=_positive_int_env("CHAT_REQUESTS_PER_MINUTE", 12),
            max_concurrent_requests=_positive_int_env(
                "CHAT_MAX_CONCURRENT_REQUESTS", 4
            ),
        ),
        export_limit=RouteLimit(
            requests_per_minute=_positive_int_env("EXPORT_REQUESTS_PER_MINUTE", 30),
            max_concurrent_requests=_positive_int_env(
                "EXPORT_MAX_CONCURRENT_REQUESTS", 2
            ),
        ),
    )
    app.add_middleware(SecurityResponseHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ACCESS_LIST_CSV", "").split(","),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    if production:
        app.add_middleware(
            HealthcheckTrustedHostMiddleware, allowed_hosts=trusted_hosts
        )

    app.include_router(holding.router, prefix="/holding", tags=["Holding"])
    app.include_router(
        all_holdings.router, prefix="/all-holdings", tags=["All Holdings"]
    )
    app.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
    app.include_router(
        all_portfolios.router, prefix="/all-portfolios", tags=["All Portfolios"]
    )
    app.include_router(fund.router, prefix="/fund", tags=["Fund"])
    app.include_router(benchmark.router, prefix="/benchmark", tags=["Benchmark"])
    app.include_router(
        top_positions.router, prefix="/top-positions", tags=["Top Positions"]
    )
    app.include_router(
        covariance_matrix.router,
        prefix="/covariance-matrix",
        tags=["Covariance Matrix"],
    )
    app.include_router(
        factor_exposures.router, prefix="/factor-exposures", tags=["Factor Exposures"]
    )
    app.include_router(
        risk_forecast.router, prefix="/risk_forecast", tags=["Risk Forecast"]
    )
    app.include_router(chatbot.router, prefix="/chat", tags=["Chatbot"])

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
