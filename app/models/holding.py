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
                "beta": 1.242227333139131,
            }
        }


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

    class Config:
        json_schema_extra = {
            "example": {
                "fund": "grad",
                "ticker": "AAPL",
                "start": "2024-08-20",
                "end": "2025-08-20",
                "records": [
                    {
                        "date": "2024-08-20",
                        "weight": 0.020509278518708873,
                        "price": 226.51,
                        "shares": 130,
                        "value": 29446.3,
                        "return_": 0.00274469874717783,
                        "cummulative_return": 0.002744698747177754,
                        "dividends": 0,
                        "dividends_per_share": 0,
                        "benchmark_return": -0.00251230538187614,
                    },
                    {
                        "date": "2024-08-21",
                        "weight": 0.020337176033715987,
                        "price": 226.4,
                        "shares": 130,
                        "value": 29432,
                        "return_": -0.0004856297735199329,
                        "cummulative_return": 0.002257736066226812,
                        "dividends": 0,
                        "dividends_per_share": 0,
                        "benchmark_return": 0.00371478439878012,
                    },
                ],
            }
        }
