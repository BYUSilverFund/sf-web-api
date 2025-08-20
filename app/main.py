from fastapi import FastAPI
from app.routers import holdings

app = FastAPI(title="Silver Fund API")

app.include_router(holdings.router, prefix="/holdings", tags=["Holdings"])
