from fastapi import FastAPI
from app.routers import fund, holdings

app = FastAPI(title="Silver Fund API")

app.include_router(holdings.router, prefix="/holdings", tags=["Holdings"])
app.include_router(fund.router, prefix="/fund", tags=['Fund'])