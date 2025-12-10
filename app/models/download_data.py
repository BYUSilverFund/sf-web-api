from datetime import date

from pydantic import BaseModel


class DownloadDataAllPortfolioRequest(BaseModel):
    start: date
    end: date

    class Config:
        json_schema_extra = {
            "example": {
                "start": "2024-08-20",
                "end": "2025-08-20",
            }
        }


class DownloadDataAllPortfolioRecord(BaseModel):
    date: date
    portfolio: str
    ticker: str
    value: float
    return_: float
    dividends: float
    return_bmk: float
    return_rf: float


class DownloadDataAllPortfolioResponse(BaseModel):
    records: list[DownloadDataAllPortfolioRecord]
