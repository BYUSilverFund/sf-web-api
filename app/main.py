from fastapi import FastAPI
from app.routers import fund, holding

app = FastAPI(title="Silver Fund API")

app.include_router(holding.router, prefix="/holdings", tags=["Holding"])
app.include_router(fund.router, prefix="/fund", tags=['Fund'])