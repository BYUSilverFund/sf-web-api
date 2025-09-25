from pydantic import BaseModel


class TickersList(BaseModel):
    tickers: list[str]


class Fund(BaseModel):
    fund: str
