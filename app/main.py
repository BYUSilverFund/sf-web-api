from fastapi import FastAPI
from app.routers import (
    fund,
    holding,
    benchmark,
    portfolio,
    top_positions,
    all_portfolios,
    all_holdings,
)
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Silver Fund API")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "https://main.d296w26r2ifyvl.amplifyapp.com",
        "https://silverfund.byu.edu",
        "https://www.silverfund.byu.edu"
        # Add production frontend URLs here, e.g. "https://yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Restrict to necessary methods
    allow_headers=["Authorization", "Content-Type"],  # Restrict to necessary headers
)

# Health check endpoint
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
