from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.covariance_matrix import TickersList, Fund
from app.services.covariance_matrix import (
    get_covariance_matrix,
    get_tickers,
    get_fund_tickers,
)
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
    tickers: TickersList,
) -> StreamingResponse:
    covariance_matrix = get_covariance_matrix(tickers)
    csv_string = covariance_matrix.write_csv()
    csv_io = io.StringIO(csv_string)
    headers = {"Content-Disposition": "attachment; filename=latest.csv"}
    media_type = "text/csv"
    return StreamingResponse(content=csv_io, headers=headers, media_type=media_type)


@router.post(
    "/tickers",
    response_model=TickersList,
    summary="Get Covariance Matrix Tickers",
    description="Returns the available tickers for the latest covariance matrix.",
    response_description="List of tickers.",
    tags=["Covariance Matrix"],
)
def tickers() -> TickersList:
    return TickersList(tickers=get_tickers())


@router.post(
    "/fund-tickers",
    response_model=TickersList,
    summary="Get Fund Tickers",
    description="Returns the latest tickers for a given fund",
    response_description="List of tickers.",
    tags=["Covariance Matrix"],
)
def fund_tickers(fund: Fund) -> TickersList:
    return TickersList(tickers=get_fund_tickers(fund))
