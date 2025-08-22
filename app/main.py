from fastapi import FastAPI
from app.routers import fund, holding, benchmark, portfolio, top_positions, all_portfolios
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Silver Fund API")

app.include_router(holding.router, prefix="/holdings", tags=["Holding"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
app.include_router(all_portfolios.router, prefix="/all-portfolios", tags=["All Portfolios"])
app.include_router(fund.router, prefix="/fund", tags=["Fund"])
app.include_router(benchmark.router, prefix="/benchmark", tags=["Benchmark"])
app.include_router(
    top_positions.router, prefix="/top-positions", tags=["Top Positions"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
