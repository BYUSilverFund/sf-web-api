from fastapi import APIRouter
from app.services.top_positions import get_top_positions
from app.models.top_positions import TopPositionsRequest, TopPositionsResponse

router = APIRouter()


@router.post(
    "/",
    response_model=TopPositionsResponse,
    summary="Get Top Positions",
    description="Returns top 10 positions by value for a given fund as of the last date of observation",
    response_description="Top 10 positions by value for a given fund.",
    tags=["Top Positions"],
)
def top_positions(holding_request: TopPositionsRequest) -> TopPositionsResponse:
    return TopPositionsResponse(**get_top_positions(holding_request))
