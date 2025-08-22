from fastapi import APIRouter
from app.services.fund import get_fund_summary, get_fund_time_series
from app.models.fund import (
    FundRequest,
    FundSummaryResponse,
    FundTimeSeriesResponse,
)

router = APIRouter()


@router.post(
    "/summary",
    response_model=FundSummaryResponse,
    summary="Get Fund Summary",
    description="Returns summary statistics for all portfolios combined over a date range.",
    response_description="Summary metrics for all portfolios combined.",
    tags=["Fund"],
)
def fund_summary(holding_request: FundRequest) -> FundSummaryResponse:
    return FundSummaryResponse(**get_fund_summary(holding_request))


@router.post(
    "/time-series",
    response_model=FundTimeSeriesResponse,
    summary="Get All Funds Time Series Values",
    description="Returns time series values for all funds combined over a date range.",
    response_description="Time series values for all funds combined.",
    tags=["Fund"],
)
def fund_time_series(holding_request: FundRequest) -> FundTimeSeriesResponse:
    return FundTimeSeriesResponse(**get_fund_time_series(holding_request))
