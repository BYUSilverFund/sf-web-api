from fastapi import APIRouter
from fastapi.responses import Response

from app.models.all_holdings import (
    AllHoldingsRequest,
    AllHoldingsSummaryResponse,
    AllHoldingsTimeSeriesResponse,
)
from app.services.all_holdings import (
    get_all_holdings_summary,
    get_all_holdings_time_series,
    get_all_holdings_time_series_csv,
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
def all_holdings_summary(
    holding_request: AllHoldingsRequest,
) -> AllHoldingsSummaryResponse:
    return AllHoldingsSummaryResponse(**get_all_holdings_summary(holding_request))


@router.post(
    "/time-series",
    response_model=AllHoldingsTimeSeriesResponse,
    summary="Get Fund Holdings Time Series Values",
    description="Returns time series values for a given fund's holdings over a date range.",
    response_description="Time series values for the requested fund's holdings.",
    tags=["All Holdings"],
)
def all_holdings_time_series(
    all_holdings_request: AllHoldingsRequest,
) -> AllHoldingsTimeSeriesResponse:
    return AllHoldingsTimeSeriesResponse(
        **get_all_holdings_time_series(all_holdings_request)
    )


@router.post(
    "/csv",
    summary="Download all a time series for all holdings for a fund",
    description="Download all a time series for all holdings for a fund.",
)
def download_all_holdings_summary_csv(request: AllHoldingsRequest) -> Response:
    csv_bytes = get_all_holdings_time_series_csv(request)

    filename = f"{request.fund}_holdings_summary.csv".replace(" ", "_").lower()

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
