from pydantic import BaseModel


class CovarianceMatrixRequest(BaseModel):
    tickers: list[str]
