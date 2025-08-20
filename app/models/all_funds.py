from pydantic import BaseModel
from datetime import date

class AllFundsRequest(BaseModel):
    start: date
    end: date

    class Config:
        json_schema_extra = {
            "example": {
                "start": "2024-08-20",
                "end": "2025-08-20"
            }
        }

class AllFundsSummaryResponse(BaseModel):
    start: date
    end: date
    value: float
    total_return: float
    sharpe_ratio: float
    volatility: float
    dividends: float
    dividend_yield: float
    alpha: float
    beta: float
    tracking_error: float
    information_ratio: float

class AllFundsRecord(BaseModel):
    date: date
    value: float
    return_: float
    cummulative_return: float
    dividends: float
    benchmark_return: float
    benchmark_cummulative_return: float

class AllFundsTimeSeriesResponse(BaseModel):
    start: date
    end: date
    records: list[AllFundsRecord]

