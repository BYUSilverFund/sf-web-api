from fastapi import FastAPI
from app.routers import holdings

app = FastAPI(title="Portfolio Analytics API")

# Register routers
app.include_router(holdings.router, prefix="/holdings", tags=["Holdings"])
