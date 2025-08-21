from pydantic import BaseModel
from datetime import date

class AllFundsRequest(BaseModel):
    start: date
    end: date

    class Config:
        json_schema_extra = {
            "example": {
                "start": "2024-08-20",
                "end": "2025-08-20"
            }
        }

class AllFundsSummaryResponse(BaseModel):
    start: date
    end: date
    value: float
    total_return: float
    sharpe_ratio: float
    volatility: float
    dividends: float
    dividend_yield: float
    alpha: float
    beta: float
    tracking_error: float
    information_ratio: float

    class Config:
        json_schema_extra = {
            "example": {
                "start": "202`4-08-20",
                "end": "2025-08-20",
                "value": 4747703.984369247,
                "total_return": 17.262062335422847,
                "sharpe_ratio": 0.9262607401727467,
                "volatility": 18.636288451784633,
                "dividends": 44517.22069,
                "dividend_yield": 0.937657883401387,
                "alpha": 0.01938024415807343,
                "beta": 0.9641972842451537,
                "tracking_error": 2.0333490886080763,
                "information_ratio": 0.009531193766310007
            }
        }

class AllFundsRecord(BaseModel):
    date: date
    value: float
    return_: float
    cummulative_return: float
    dividends: float
    benchmark_return: float
    benchmark_cummulative_return: float

class AllFundsTimeSeriesResponse(BaseModel):
    start: date
    end: date
    records: list[AllFundsRecord]

    class Config:
        json_schema_extra = {
            "example": {
                "start": "2024-08-20",
                "end": "2025-08-20",
                "records": [
                    {
                    "date": "2024-08-20",
                    "value": 4035253.245729191,
                    "return_": -0.2971149867009693,
                    "cummulative_return": -0.2971149867009748,
                    "dividends": 0,
                    "benchmark_return": -0.25122084490348,
                    "benchmark_cummulative_return": -0.25122084490347696
                    },
                    {
                    "date": "2024-08-21",
                    "value": 4059537.089053361,
                    "return_": 0.60179230014551,
                    "cummulative_return": 0.3028892983319986,
                    "dividends": 0,
                    "benchmark_return": 0.37146868608184797,
                    "benchmark_cummulative_return": 0.11931463440664203
                    }
                ]
            }
        }

