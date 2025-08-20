from pydantic import BaseModel
from datetime import date

class HoldingRequest(BaseModel):
    fund: str
    ticker: str
    start: date
    end: date

class HoldingSummaryResponse(BaseModel):
    fund: str
    ticker: str
    start: date
    end: date
    shares: int
    price: float
    value: float
    total_return: float
    volatility: float
    dividends_per_share: float
    dividend_yield: float
    alpha: float
    beta: float
