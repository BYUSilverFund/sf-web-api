from fastapi import APIRouter, Depends

from app.auth import cognito_auth
from app.services.risk_forecast import (
    all_funds_risk_forecast,
    fund_holding_risk_forecast,
)


router = APIRouter()


@router.get(
    "/all_funds",
    summary="Get All Funds Risk Forecast",
    description="Returns beta, variance, and volatility forecast for the aggregate of all funds",
    response_description="Portfolio risk forecast for all funds",
    tags=["Risk Forecast"],
)
def all_fund_risk_forecasts(_claims=Depends(cognito_auth)) -> dict:
    return all_funds_risk_forecast()


@router.get(
    "/{fund}",
    summary="Get Single Fund Risk Forecast (with holdings)",
    description="Returns beta, volatility, tracking error, and holdings-level risk for a single fund",
    response_description="Portfolio and holdings risk forecast for specified fund",
    tags=["Risk Forecast"],
)
def fund_risk_forecasts(fund: str, _claims=Depends(cognito_auth)) -> dict:
    # fund_holding_risk_forecast returns:
    # { "fund": fund, "fund_level": {...}, "holdings": [...] }
    result = fund_holding_risk_forecast(fund)
    fund_level = result["fund_level"]
    return {
        "beta": fund_level["beta"],
        "volatility": fund_level["volatility"],
        "tracking_error": fund_level["tracking_error"],
        "holdings": result["holdings"],
    }


@router.get(
    "/{fund}/holdings",
    summary="Get Single Fund Holding Risk Forecast",
    description="Returns risk forecast metrics at the holding level for a single fund",
    response_description="Holding-level risk forecast for specified fund",
    tags=["Risk Forecast"],
)
def fund_holding_risk_forecasts(fund: str, _claims=Depends(cognito_auth)) -> dict:
    return fund_holding_risk_forecast(fund)
