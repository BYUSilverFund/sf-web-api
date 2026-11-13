from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.auth import cognito_auth
from app.funds import normalize_fund
from app.observability import ChatStreamingResponse, sse_iterator
from app.services.chatbot import stream_chat_events

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    fund: (
        Literal["undergrad", "quant", "brigham_capital", "grad", "quant_paper"] | None
    ) = None

    @field_validator("fund", mode="before")
    @classmethod
    def validate_fund(cls, value):
        if value is None or value in ("all_funds", "All funds", "All Funds"):
            return None
        if value == "" or (isinstance(value, str) and not value.strip()):
            raise ValueError("fund must be a supported fund or all_funds")
        return normalize_fund(value)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


@router.post("/stream", summary="Stream a chatbot response")
def stream_chat(
    request: ChatRequest,
    _claims: dict = Depends(cognito_auth),
) -> StreamingResponse:
    request_id = str(uuid4())
    events = (
        stream_chat_events(request.message, request_id, request.fund)
        if request.fund
        else stream_chat_events(request.message, request_id)
    )
    return ChatStreamingResponse(
        sse_iterator(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
