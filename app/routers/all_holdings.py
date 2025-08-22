from fastapi import APIRouter
from app.services.all_holdings import get_all_holdings_summary
from app.models.all_holdings import (
    AllHoldingsRequest,
    AllHoldingsSummaryResponse,
)

router = APIRouter()


@router.post(
    "/summary",
    response_model=AllHoldingsSummaryResponse,
    summary="Get All Holdings Summary",
    description="Returns summary statistics for all holdings for the given fund over a date range.",
    response_description="Summary metrics for all holdings for a specific fund.",
    tags=["All Holdings"],
)
def all_holdings_summary(holding_request: AllHoldingsRequest) -> AllHoldingsSummaryResponse:
    return AllHoldingsSummaryResponse(**get_all_holdings_summary(holding_request))
