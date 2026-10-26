from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.auth import cognito_auth
from app.services.chatbot import stream_chat_events

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

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
    return StreamingResponse(
        stream_chat_events(request.message, request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
