import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.fund import (
    FundRequest,
    FundSummaryResponse,
    FundTimeSeriesResponse,
)
from app.services.fund import get_fund_summary, get_fund_time_series, get_fund_time_series_csv


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

@router.post(
    "/all-funds/csv",
    summary="Download all funds time series performance CSV",
    description="Returns aggregated All Funds performance time series as a CSV file.",
)
def download_get_fund_time_series_csv(request: FundRequest):

    # Call service function → returns CSV bytes
    csv_bytes = get_fund_time_series_csv(request)

    # Build filename using request dates
    start_str = request.start.strftime("%Y-%m-%d")
    end_str = request.end.strftime("%Y-%m-%d")
    filename = f"timeseries_performance_all_funds_{start_str}_to_{end_str}.csv"

    # Return downloadable CSV
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )