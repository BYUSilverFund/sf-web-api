from pydantic import BaseModel
from datetime import date


class AllPortfoliosRequest(BaseModel):
    start: date
    end: date

    class Config:
        json_schema_extra = {
            "example": {"start": "2024-08-20", "end": "2025-08-20"}
        }


class AllPortfoliosRecord(BaseModel):
    portfolio: str
    value: float
    total_return: float
    sharpe_ratio: float
    volatility: float
    dividends: float
    dividend_yield: float

class AllPortfoliosSummaryResponse(BaseModel):
    start: date
    end: date
    portfolios: list[AllPortfoliosRecord]