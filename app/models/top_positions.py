from datetime import date

from pydantic import BaseModel, ConfigDict


class TopPositionsRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fund": "grad",
            }
        }
    )

    fund: str


class TopPositionsRecord(BaseModel):
    ticker: str
    value: float


class TopPositionsResponse(BaseModel):
    date: date
    fund: str
    records: list[TopPositionsRecord]
