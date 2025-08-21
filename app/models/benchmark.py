from pydantic import BaseModel
from datetime import date


class BenchmarkRequest(BaseModel):
    start: date
    end: date

    class Config:
        json_schema_extra = {"example": {"start": "2024-08-20", "end": "2025-08-20"}}


class BenchmarkSummaryResponse(BaseModel):
    start: date
    end: date
    adjusted_close: float
    total_return: float
    sharpe_ratio: float
    volatility: float
    dividends_per_share: float
    dividend_yield: float

    class Config:
        json_schema_extra = {
            "example": {
                "start": "2024-08-20",
                "end": "2025-08-20",
                "adjusted_close": 363.480010986328,
                "total_return": 15.45198669189627,
                "sharpe_ratio": 0.8037452078981817,
                "volatility": 19.224981424528412,
                "dividends_per_share": 3.8089999999999997,
                "dividend_yield": 1.0479255763374762,
            }
        }


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

    class Config:
        json_schema_extra = {
            "example": {
                "start": "2024-08-20",
                "end": "2025-08-20",
                "records": [
                    {
                        "date": "2024-08-20",
                        "adjusted_close": 314.041259765625,
                        "return_": -0.25122084490348,
                        "cummulative_return": -0.25122084490347696,
                        "dividends_per_share": 0,
                    },
                    {
                        "date": "2024-08-21",
                        "adjusted_close": 315.207824707031,
                        "return_": 0.37146868608184797,
                        "cummulative_return": 0.11931463440664203,
                        "dividends_per_share": 0,
                    },
                ],
            }
        }
