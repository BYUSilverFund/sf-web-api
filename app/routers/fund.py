from fastapi import APIRouter
from app.services.fund import get_fund_summary, get_fund_time_series
from app.models.fund import FundRequest, FundSummaryResponse, FundTimeSeriesResponse
router = APIRouter()

@router.post(
    "/summary",
    response_model=FundSummaryResponse,
    summary="Get Fund Summary",
    description="Returns summary statistics for a given fund over a date range.",
    response_description="Summary metrics for the requested fund.",
    tags=["Fund"]
)
def fund_summary(holding_request: FundRequest) -> FundSummaryResponse:
    return FundSummaryResponse(**get_fund_summary(holding_request))

@router.post(
    "/time-series",
    response_model=FundTimeSeriesResponse,
    summary="Get Fund Time Series Values",
    description="Returns time series values for a given fund over a date range.",
    response_description="Time series values for the requested fund.",
    tags=["Fund"]
)
def fund_time_series(holding_request: FundRequest) -> FundTimeSeriesResponse:
    return FundTimeSeriesResponse(**get_fund_time_series(holding_request))
