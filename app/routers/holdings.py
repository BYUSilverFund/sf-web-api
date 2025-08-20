from fastapi import APIRouter
from app.services.holdings_service import get_holding_summary
from app.models.holdings import HoldingRequest, HoldingSummaryResponse

router = APIRouter()

@router.post("/summary")
def holding_summary(holding_request: HoldingRequest) -> HoldingSummaryResponse:
    return HoldingSummaryResponse(**get_holding_summary(holding_request))
