from fastapi import APIRouter
from app.services.all_funds import get_all_funds_summary, get_all_funds_time_series
from app.models.all_funds import AllFundsRequest, AllFundsSummaryResponse, AllFundsTimeSeriesResponse
router = APIRouter()

@router.post(
    "/summary",
    response_model=AllFundsSummaryResponse,
    summary="Get All Funds Summary",
    description="Returns summary statistics for all funds combined over a date range.",
    response_description="Summary metrics for all funds combined.",
    tags=["All Funds"]
)
def fund_summary(holding_request: AllFundsRequest) -> AllFundsSummaryResponse:
    return AllFundsSummaryResponse(**get_all_funds_summary(holding_request))

@router.post(
    "/time-series",
    response_model=AllFundsTimeSeriesResponse,
    summary="Get All Funds Time Series Values",
    description="Returns time series values for all funds combined over a date range.",
    response_description="Time series values for all funds combined.",
    tags=["All Funds"]
)
def fund_time_series(holding_request: AllFundsRequest) -> AllFundsTimeSeriesResponse:
    return AllFundsTimeSeriesResponse(**get_all_funds_time_series(holding_request))
