from datetime import date

from pydantic import BaseModel, ConfigDict
from app.models.portfolio import PortfolioRequest


class HoldingRequest(PortfolioRequest):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fund": "grad",
                "ticker": "AAPL",
                "start": "2024-08-20",
                "end": "2025-08-20",
            }
        }
    )

    ticker: str | None = None


class HoldingSummaryResponse(BaseModel):
    fund: str
    ticker: str
    start: date
    end: date
    trading_days: int
    active: bool
    shares: float
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
    shares: float
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
    shares: float
    dividends_per_share: float
    dividends: float


class DividendsResponse(BaseModel):
    fund: str
    ticker: str
    start: date
    end: date
    dividends: list[DividendsRecord]


class TradeRecord(BaseModel):
    date: date
    type: str
    shares: float
    price: float
    value: float
    ticker: str
    current_price: float | None = None


class TradesResponse(BaseModel):
    fund: str
    start: date
    end: date
    trades: list[TradeRecord]
