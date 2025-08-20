from fastapi import APIRouter
from app.services.holdings_service import get_holding_summary
from app.models.holdings import HoldingRequest, HoldingSummaryResponse

router = APIRouter()

@router.post(
    "/summary",
    response_model=HoldingSummaryResponse,
    summary="Get Holding Summary",
    description="Returns summary statistics for a given fund/ticker over a date range.",
    response_description="Summary metrics for the requested holding.",
    tags=["Holdings"]
)
def holding_summary(holding_request: HoldingRequest) -> HoldingSummaryResponse:
    return HoldingSummaryResponse(**get_holding_summary(holding_request))
