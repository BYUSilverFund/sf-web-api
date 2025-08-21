from fastapi import FastAPI
from app.routers import fund, holding, all_funds, benchmark, top_positions

app = FastAPI(title="Silver Fund API")

app.include_router(holding.router, prefix="/holdings", tags=["Holding"])
app.include_router(fund.router, prefix="/fund", tags=["Fund"])
app.include_router(all_funds.router, prefix="/all-funds", tags=["All Funds"])
app.include_router(benchmark.router, prefix="/benchmark", tags=["Benchmark"])
app.include_router(
    top_positions.router, prefix="/top-positions", tags=["Top Positions"]
)
