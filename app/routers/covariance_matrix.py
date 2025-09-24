from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.covariance_matrix import CovarianceMatrixRequest
from app.services.covariance_matrix import get_covariance_matrix
import io

router = APIRouter()


@router.post(
    "/latest",
    summary="Get Latest Covariance Matrix",
    description="Returns latest covariance matrix for the given tickers.",
    response_description="Latest covariance matrix for a list of tickers.",
    tags=["Covariance Matrix"],
)
def covariance_matrix(
    covariance_matrix_request: CovarianceMatrixRequest,
) -> StreamingResponse:
    covariance_matrix = get_covariance_matrix(covariance_matrix_request)
    csv_string = covariance_matrix.write_csv()
    csv_io = io.StringIO(csv_string)
    headers = {"Content-Disposition": "attachment; filename=latest.csv"}
    media_type = "text/csv"
    return StreamingResponse(content=csv_io, headers=headers, media_type=media_type)
