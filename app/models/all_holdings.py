from pydantic import BaseModel
from datetime import date


class AllHoldingsRequest(BaseModel):
    fund: str
    start: date
    end: date

    class Config:
        json_schema_extra = {
            "example": {"fund": "grad", "start": "2024-08-20", "end": "2025-08-20"}
        }


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
    holdings: list[AllHoldingsRecord]
