from fastapi import APIRouter
from app.services.holding import get_holding_summary, get_holding_time_series, get_dividends
from app.models.holding import (
    HoldingRequest,
    HoldingSummaryResponse,
    HoldingTimeSeriesResponse,
    DividendsResponse
)

router = APIRouter()


@router.post(
    "/summary",
    response_model=HoldingSummaryResponse,
    summary="Get Holding Summary",
    description="Returns summary statistics for a given fund/ticker over a date range.",
    response_description="Summary metrics for the requested holding.",
    tags=["Holding"],
)
def holding_summary(holding_request: HoldingRequest) -> HoldingSummaryResponse:
    return HoldingSummaryResponse(**get_holding_summary(holding_request))


@router.post(
    "/time-series",
    response_model=HoldingTimeSeriesResponse,
    summary="Get Holding Time Series Values",
    description="Returns time series values for a given fund/ticker over a date range.",
    response_description="Time series values for the requested holding.",
    tags=["Holding"],
)
def holding_time_series(holding_request: HoldingRequest) -> HoldingTimeSeriesResponse:
    return HoldingTimeSeriesResponse(**get_holding_time_series(holding_request))


@router.post(
    "/dividends",
    response_model=DividendsResponse,
    summary="Get Dividends",
    description="Returns dividends fund/ticker over a date range.",
    response_description="Dividends for the requested holding.",
    tags=["Holding"],
)
def dividends(holding_request: HoldingRequest) -> DividendsResponse:
    return DividendsResponse(**get_dividends(holding_request))
