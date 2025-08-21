from pydantic import BaseModel
from datetime import date

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