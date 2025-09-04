from fastapi import APIRouter
from app.services.holding import (
    get_holding_summary,
    get_holding_time_series,
    get_dividends,
    get_trades,
)
from app.models.holding import (
    HoldingRequest,
    HoldingSummaryResponse,
    HoldingTimeSeriesResponse,
    DividendsResponse,
    TradesResponse,
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
    description="Returns dividends for a fund/ticker over a date range.",
    response_description="Dividends for the requested holding.",
    tags=["Holding"],
)
def dividends(holding_request: HoldingRequest) -> DividendsResponse:
    return DividendsResponse(**get_dividends(holding_request))


@router.post(
    "/trades",
    response_model=TradesResponse,
    summary="Get Trades",
    description="Returns trades for a fund/ticker over a date range.",
    response_description="Trades for the requested holding.",
    tags=["Holding"],
)
def trades(holding_request: HoldingRequest) -> TradesResponse:
    return TradesResponse(**get_trades(holding_request))
