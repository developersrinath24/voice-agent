from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionResponse(BaseModel):
    session_id: UUID
    status: str
    message_count: int = 0
    created_at: datetime | None = None


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
