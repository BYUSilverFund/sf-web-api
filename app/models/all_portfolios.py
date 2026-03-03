from datetime import date

from pydantic import BaseModel, ConfigDict


class AllPortfoliosRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"start": "2024-08-20", "end": "2025-08-20"}}
    )

    start: date
    end: date


class AllPortfoliosRecord(BaseModel):
    portfolio: str
    value: float
    total_return: float
    volatility: float
    sharpe_ratio: float
    dividends: float
    dividend_yield: float
    alpha: float
    beta: float
    tracking_error: float
    information_ratio: float


class AllPortfoliosSummaryResponse(BaseModel):
    start: date
    end: date
    trading_days: int
    portfolios: list[AllPortfoliosRecord]
