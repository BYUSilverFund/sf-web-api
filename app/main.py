from fastapi import FastAPI
from app.routers import holding, all_funds, benchmark, portfolio, top_positions
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Silver Fund API")

app.include_router(holding.router, prefix="/holdings", tags=["Holding"])
app.include_router(portfolio.router, prefix="/fund", tags=["Fund"])
app.include_router(all_funds.router, prefix="/all-funds", tags=["All Funds"])
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
