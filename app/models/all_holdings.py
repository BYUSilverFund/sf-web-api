from datetime import date

from pydantic import BaseModel, ConfigDict


class AllHoldingsRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"fund": "grad", "start": "2024-08-20", "end": "2025-08-20"}
        }
    )

    fund: str
    start: date
    end: date


class AllHoldingsRecord(BaseModel):
    ticker: str
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


class AllHoldingsSummaryResponse(BaseModel):
    start: date
    end: date
    trading_days: int
    holdings: list[AllHoldingsRecord]


class AllHoldingsTimeSeriesRecord(BaseModel):
    date: date
    ticker: str
    price: float
    shares: float
    fx_rate_to_base: float


class AllHoldingsTimeSeriesResponse(BaseModel):
    fund: str
    start: date
    end: date
    records: list[AllHoldingsTimeSeriesRecord]
