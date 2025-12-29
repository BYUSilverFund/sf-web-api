import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.all_portfolios import (
    AllPortfoliosRequest,
    AllPortfoliosSummaryResponse,
)
from app.services.all_portfolios import (
    get_all_portfolios_csv,
    get_all_portfolios_summary,
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
def all_portfolios_summary(
    holding_request: AllPortfoliosRequest,
) -> AllPortfoliosSummaryResponse:
    return AllPortfoliosSummaryResponse(**get_all_portfolios_summary(holding_request))


@router.post(
    "/csv",
    summary="Download all portfolios summary CSV",
    description="Returns the All Portfolios summary table as a downloadable CSV file.",
    tags=["All Portfolios"],
)
def download_all_portfolios_csv(request: AllPortfoliosRequest):
    # Get CSV bytes from service
    csv_bytes = get_all_portfolios_csv(request)

    # Build filename
    start_str = request.start.strftime("%Y-%m-%d")
    end_str = request.end.strftime("%Y-%m-%d")
    filename = f"all_portfolios_{start_str}_to_{end_str}.csv"

    # Return CSV download
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
