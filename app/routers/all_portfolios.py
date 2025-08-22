from fastapi import APIRouter
from app.services.all_portfolios import get_all_portfolios_summary
from app.models.all_portfolios import (
    AllPortfoliosRequest,
    AllPortfoliosSummaryResponse,
)

router = APIRouter()


@router.post(
    "/summary",
    response_model=AllPortfoliosSummaryResponse,
    summary="Get All Portfolios Summary",
    description="Returns summary statistics for all portfolios over a date range.",
    response_description="Summary metrics for all portfolios.",
    tags=["All Portfolios"],
)
def all_portfolios_summary(holding_request: AllPortfoliosRequest) -> AllPortfoliosSummaryResponse:
    return AllPortfoliosSummaryResponse(**get_all_portfolios_summary(holding_request))
