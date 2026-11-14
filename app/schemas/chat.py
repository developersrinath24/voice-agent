from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=4000,
        description="Message sent by the client.",
    )
    session_id: UUID | None = Field(
        default=None,
        description="Existing session to continue. Omit to start a new one.",
    )


class ChatResponse(BaseModel):
    session_id: UUID
    response: str
    status: str = "success"
    message_count: int = 0
