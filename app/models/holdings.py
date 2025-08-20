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
                "end": "2025-08-20"
            }
        }

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

    class Config:
        json_schema_extra = {
            "example": {
                "fund": "grad",
                "ticker": "AAPL",
                "start": "2024-08-20",
                "end": "2025-08-20",
                "shares": 16,
                "price": 230.89,
                "value": 3694.24,
                "total_return": 2.0548440660156597,
                "volatility": 32.10053897561645,
                "dividends_per_share": 1.02,
                "dividend_yield": 0.441768807657326,
                "alpha": -0.1320799680465235,
                "beta": 1.242227333139131
            }
        }
