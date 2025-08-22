from fastapi import APIRouter
from app.services.portfolio import get_portfolio_summary, get_portfolio_time_series
from app.models.portfolio import PortfolioRequest, PortfolioSummaryResponse, PortfolioTimeSeriesResponse

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
    tags=["Fund"],
)
def fund_time_series(holding_request: PortfolioRequest) -> PortfolioTimeSeriesResponse:
    return PortfolioTimeSeriesResponse(**get_portfolio_time_series(holding_request))
