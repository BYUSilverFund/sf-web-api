import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.portfolio import (
    PortfolioRequest,
    PortfolioSummaryResponse,
    PortfolioTimeSeriesResponse,
)
from app.services.portfolio import (
    get_portfolio_summary,
    get_portfolio_time_series,
    get_portfolio_time_series_csv,
)


router = APIRouter()


@router.post(
    "/summary",
    response_model=PortfolioSummaryResponse,
    summary="Get Portfolio Summary",
    description="Returns summary statistics for a given portfolio over a date range.",
    response_description="Summary metrics for the requested portfolio.",
    tags=["Portfolio"],
)
def portfolio_summary(holding_request: PortfolioRequest) -> PortfolioSummaryResponse:
    return PortfolioSummaryResponse(**get_portfolio_summary(holding_request))


@router.post(
    "/time-series",
    response_model=PortfolioTimeSeriesResponse,
    summary="Get Fund Time Series Values",
    description="Returns time series values for a given fund over a date range.",
    response_description="Time series values for the requested fund.",
    tags=["Portfolio"],
)
def portfolio_time_series(
    holding_request: PortfolioRequest,
) -> PortfolioTimeSeriesResponse:
    return PortfolioTimeSeriesResponse(**get_portfolio_time_series(holding_request))


@router.post(
    "/portfolio/csv",
    summary="Download single portfolio time series CSV",
    description="Returns a CSV file containing the time series for a single portfolio.",
    tags=["Portfolio"],
)
def download_portfolio_time_series_csv(request: PortfolioRequest):
    csv_bytes = get_portfolio_time_series_csv(request)

    start_str = request.start.strftime("%Y-%m-%d")
    end_str = request.end.strftime("%Y-%m-%d")
    fund = request.fund.lower()

    filename = f"portfolio_{fund}_{start_str}_to_{end_str}.csv"

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
