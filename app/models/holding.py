from pydantic import BaseModel
from datetime import date


class HoldingRequest(BaseModel):
    fund: str
    ticker: str
    start: date
    end: date

    class Config:
        json_schema_extra = {
            "example": {
                "fund": "grad",
                "ticker": "AAPL",
                "start": "2024-08-20",
                "end": "2025-08-20",
            }
        }


class HoldingSummaryResponse(BaseModel):
    fund: str
    ticker: str
    start: date
    end: date
    active: bool
    shares: int
    price: float
    value: float
    total_return: float
    volatility: float
    dividends: float
    dividends_per_share: float
    dividend_yield: float
    alpha: float
    beta: float


class HoldingRecord(BaseModel):
    date: date
    weight: float
    price: float
    shares: int
    value: float
    return_: float
    cummulative_return: float
    dividends: float
    dividends_per_share: float
    benchmark_return: float
    benchmark_cummulative_return: float


class HoldingTimeSeriesResponse(BaseModel):
    fund: str
    ticker: str
    start: date
    end: date
    records: list[HoldingRecord]


class DividendsRecord(BaseModel):
    date: date
    shares: int
    dividends_per_share: float
    dividends: float


class DividendsResponse(BaseModel):
    fund: str
    ticker: str
    start: date
    end: date
    dividends: list[DividendsRecord]


class TradesRecord(BaseModel):
    date: date
    type: str
    shares: int
    price: float
    value: float


class TradesResponse(BaseModel):
    fund: str
    ticker: str
    start: date
    end: date
    trades: list[TradesRecord]
