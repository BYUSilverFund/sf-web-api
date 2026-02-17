from fastapi import APIRouter, Depends

from app.auth import cognito_auth
from app.services.risk_forecast import (
    all_funds_risk_forecast,
    fund_holding_risk_forecast,
    fund_risk_forecast,
)


router = APIRouter()


@router.get(
    "/all_funds",
    summary="Get All Funds Risk Forecast",
    description="Returns beta, volatility, and tracking error forecast for the aggregate of all funds",
    response_description="Portfolio risk forecast for all funds",
    tags=["Risk Forecast"],
)
def all_fund_risk_forecasts(_claims=Depends(cognito_auth)) -> dict:
    return all_funds_risk_forecast()


@router.get(
    "/{fund}",
    summary="Get Single Fund Risk Forecast",
    description="Returns beta, volatility, and tracking error for a single fund",
    response_description="Portfolio risk forecast for specified fund",
    tags=["Risk Forecast"],
)
def fund_risk_forecasts(fund: str, _claims=Depends(cognito_auth)) -> dict:
    return fund_risk_forecast(fund)


@router.get(
    "/{fund}/holdings/{ticker}",
    summary="Get Single Fund Holding Risk Forecast",
    description="Returns risk forecast metrics for a single holding within a fund",
    response_description="Holding-level risk forecast for specified fund and ticker",
    tags=["Risk Forecast"],
)
def fund_holding_risk_forecasts(
    fund: str, ticker: str, _claims=Depends(cognito_auth)
) -> dict:
    return fund_holding_risk_forecast(fund, ticker)
