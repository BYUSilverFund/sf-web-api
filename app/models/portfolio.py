from datetime import date

from pydantic import BaseModel


class PortfolioRequest(BaseModel):
    fund: str
    start: date
    end: date

    class Config:
        json_schema_extra = {
            "example": {"fund": "grad", "start": "2024-08-20", "end": "2025-08-20"}
        }


class PortfolioSummaryResponse(BaseModel):
    fund: str
    start: date
    end: date
    trading_days: int
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


class PortfolioRecord(BaseModel):
    date: date
    value: float
    return_: float
    cummulative_return: float
    dividends: float
    benchmark_return: float
    benchmark_cummulative_return: float


class PortfolioTimeSeriesResponse(BaseModel):
    fund: str
    start: date
    end: date
    records: list[PortfolioRecord]


class TradeRecord(BaseModel):
    report_date: str
    client_account_id: str
    asset_class: str
    sub_category: str
    description: str
    cusip: str
    isin: str
    symbol: str
    trade_id: str
    quantity: float
    trade_price: float
    ib_commission: float
    buy_sell: str


class PortfolioTradesResponse(BaseModel):
    fund: str
    start: date
    end: date
    records: list[TradeRecord]
