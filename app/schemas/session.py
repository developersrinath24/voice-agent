from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    channel: str = "web"


class SessionResponse(BaseModel):
    session_id: UUID
    status: str
    channel: str = "web"
    message_count: int = 0
    created_at: datetime | None = None


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
