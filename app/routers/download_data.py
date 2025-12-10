import csv
from io import StringIO

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.download_data import (
    DownloadDataAllPortfolioRequest,
)
from app.services.download_data import get_portfolio_performance


router = APIRouter(tags=["Reports"])


@router.post(
    "/all-funds/csv",
    summary="Download all funds time series performance CSV",
    description="Returns fund-level performance time series over a user-specified date range.",
    response_description="CSV download containing the performance time series.",
)
def download_portfolio_performance_csv(
    request: DownloadDataAllPortfolioRequest,
):
    result = get_portfolio_performance(request)

    start_str = request.start.strftime("%Y-%m-%d")
    end_str = request.end.strftime("%Y-%m-%d")

    filename = f"timeseries_performance_all_funds{start_str}_to_{end_str}"

    # Create in-memory CSV
    output = StringIO()
    writer = csv.writer(output)

    # Header rows
    writer.writerow(
        ["date", "portfolio", "value", "return", "dividends", "return_bmk", "return_rf"]
    )

    # Loops through preformance df to display each row
    for row in result["timeseries_performance"]:
        writer.writerow(
            [
                row["date"],
                row["portfolio"],
                row["value"],
                row["return"],
                row["dividends"],
                row["return_bmk"],
                row["return_rf"],
            ]
        )

    # Resets the file pointer to the start so the whole csv file can be read during download
    output.seek(0)

    # Returns a downloadable csv file
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
