import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.holding import (
    DividendsResponse,
    HoldingRequest,
    HoldingSummaryResponse,
    HoldingTimeSeriesResponse,
    TradesResponse,
)
from app.services.holding import (
    get_dividends,
    get_holding_summary,
    get_holding_time_series,
    get_portfolio_time_series_csv,
    get_trades,
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


@router.post(
    "/fund/ticker/csv",
    summary="Download single holding time series CSV for a ticker with in a fund",
    description="Returns a CSV file containing the time series for a single holding.",
    tags=["Holding"],
)
def download_portfolio_time_series_csv(request: HoldingRequest):
    csv_bytes = get_portfolio_time_series_csv(request)

    start_str = request.start.strftime("%Y-%m-%d")
    end_str = request.end.strftime("%Y-%m-%d")
    fund = request.fund.lower()
    ticker = request.ticker.upper()

    filename = f"{fund}_{ticker}_{start_str}_to_{end_str}.csv"

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
