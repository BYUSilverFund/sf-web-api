import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.factor_exposures import get_factor_exposures


router = APIRouter()


@router.post(
    "/latest",
    summary="Get Latest Factor Exposures",
    description="Returns latest factor exposures",
    response_description="Latest factor exposures",
    tags=["Covariance Matrix"],
)
def factor_exposures() -> StreamingResponse:
    factor_exposures = get_factor_exposures()
    csv_string = factor_exposures.write_csv()
    csv_io = io.StringIO(csv_string)
    headers = {"Content-Disposition": "attachment; filename=factor_exposures.csv"}
    media_type = "text/csv"
    return StreamingResponse(content=csv_io, headers=headers, media_type=media_type)
