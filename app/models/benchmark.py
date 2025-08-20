from pydantic import BaseModel
from datetime import date

class BenchmarkRequest(BaseModel):
    start: date
    end: date

    class Config:
        json_schema_extra = {
            "example": {
                "start": "2024-08-20",
                "end": "2025-08-20"
            }
        }

class BenchmarkSummaryResponse(BaseModel):
    start: date
    end: date
    adjusted_close: float
    total_return: float
    sharpe_ratio: float
    volatility: float
    dividends_per_share: float
    dividend_yield: float

class BenchmarkRecord(BaseModel):
    date: date
    adjusted_close: float
    return_: float
    cummulative_return: float
    dividends_per_share: float

class BenchmarkTimeSeriesResponse(BaseModel):
    start: date
    end: date
    records: list[BenchmarkRecord]

