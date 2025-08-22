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

    class Config:
        json_schema_extra = {
            'example':{
                "start": "2024-08-20",
                "end": "2025-08-20",
                "portfolios": [
                    {
                    "portfolio": "brigham_capital",
                    "value": 203800.455207737,
                    "total_return": 18.58858191782018,
                    "sharpe_ratio": 0.9136704699419118,
                    "volatility": 20.344952068990455,
                    "dividends": 1987.9800000000002,
                    "dividend_yield": 0.9754541509603701
                    },
                    {
                    "portfolio": "grad",
                    "value": 1732858.40818768,
                    "total_return": 19.99979004211745,
                    "sharpe_ratio": 1.085405425780803,
                    "volatility": 18.42610103752733,
                    "dividends": 16522.01,
                    "dividend_yield": 0.9534541265422626
                    },
                    {
                    "portfolio": "quant",
                    "value": 1411173.9393394,
                    "total_return": 14.195829889866761,
                    "sharpe_ratio": 0.7458034688223226,
                    "volatility": 19.034277102898166,
                    "dividends": 12718.75,
                    "dividend_yield": 0.9012886112362528
                    },
                    {
                    "portfolio": "undergrad",
                    "value": 1383950.8661264,
                    "total_return": 15.603862189184614,
                    "sharpe_ratio": 0.8384868134783325,
                    "volatility": 18.609549891970765,
                    "dividends": 13288.480689999999,
                    "dividend_yield": 0.9601844267198375
                    }
                ]
            }
        }