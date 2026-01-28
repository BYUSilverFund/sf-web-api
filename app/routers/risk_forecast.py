from fastapi import APIRouter

from app.services.risk_forecast import (
    all_funds_risk_forecast,
    fund_risk_forecast,
)


router = APIRouter()


@router.get(
    "/all_funds",
    summary="Get All Funds Risk Forecast",
    description="Returns beta, variance, and volatility forecast for the aggregate of all funds",
    response_description="Portfolio risk forecast for all funds",
    tags=["Risk Forecast"],
)
def all_fund_risk_forecasts() -> dict:
    return all_funds_risk_forecast()


@router.get(
    "/{fund}",
    summary="Get Single Fund Risk Forecast",
    description="Returns beta, variance, and volatility forecast for a single fund",
    response_description="Portfolio risk forecast for specified fund",
    tags=["Risk Forecast"],
)
def fund_risk_forecasts(fund: str) -> dict:
    return fund_risk_forecast(fund)
