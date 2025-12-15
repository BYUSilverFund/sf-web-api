from datetime import date

from pydantic import BaseModel


class TopPositionsRequest(BaseModel):
    fund: str

    class Config:
        json_schema_extra = {
            "example": {
                "fund": "grad",
            }
        }


class TopPositionsRecord(BaseModel):
    ticker: str
    value: float


class TopPositionsResponse(BaseModel):
    date: date
    fund: str
    records: list[TopPositionsRecord]
