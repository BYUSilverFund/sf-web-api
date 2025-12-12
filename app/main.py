import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    all_holdings,
    all_portfolios,
    benchmark,
    covariance_matrix,
    download_data,
    fund,
    holding,
    portfolio,
    timeseries_performance_report,
    top_positions,
)


app = FastAPI(title="Silver Fund API")

app.include_router(
    timeseries_performance_report.router, prefix="/reports", tags=["Reports"]
)
app.include_router(holding.router, prefix="/holding", tags=["Holding"])
app.include_router(all_holdings.router, prefix="/all-holdings", tags=["All Holdings"])
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
    covariance_matrix.router, prefix="/covariance-matrix", tags=["Covariance Matrix"]
)


# Health check endpoint
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
