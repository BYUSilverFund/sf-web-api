from pydantic import BaseModel
from datetime import date


class FundRequest(BaseModel):
    fund: str
    start: date
    end: date

    class Config:
        json_schema_extra = {
            "example": {"fund": "grad", "start": "2024-08-20", "end": "2025-08-20"}
        }


class FundSummaryResponse(BaseModel):
    fund: str
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
                "fund": "grad",
                "start": "2024-08-20",
                "end": "2025-08-20",
                "value": 1739522.36818768,
                "total_return": 20.46126675427733,
                "sharpe_ratio": 1.1305155062718004,
                "volatility": 18.09905891671865,
                "dividends": 16522.01,
                "dividend_yield": 0.9498015261058954,
                "alpha": 0.049038466899782446,
                "beta": 0.942991340240139,
                "tracking_error": 3.62578673540609,
                "information_ratio": 0.013524917618821316,
            }
        }


class FundRecord(BaseModel):
    date: date
    value: float
    return_: float
    cummulative_return: float
    dividends: float
    benchmark_return: float
    benchmark_cummulative_return: float


class FundTimeSeriesResponse(BaseModel):
    fund: str
    start: date
    end: date
    records: list[FundRecord]

    class Config:
        json_schema_extra = {
            "example": {
                "fund": "grad",
                "start": "2024-08-20",
                "end": "2025-08-20",
                "records": [
                    {
                        "date": "2024-08-20",
                        "value": 1440189.47043864,
                        "return_": -0.26742265271267684,
                        "cummulative_return": -0.26742265271267884,
                        "dividends": 0,
                        "benchmark_return": -0.25122084490348,
                        "benchmark_cummulative_return": -0.25122084490347696,
                    },
                    {
                        "date": "2024-08-21",
                        "value": 1451636.34043864,
                        "return_": 0.7948169483917699,
                        "cummulative_return": 0.525268775111476,
                        "dividends": 0,
                        "benchmark_return": 0.37146868608184797,
                        "benchmark_cummulative_return": 0.11931463440664203,
                    },
                ],
            }
        }
