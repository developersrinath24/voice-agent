from uuid import UUID

from pydantic import BaseModel


class VoiceTurnResponse(BaseModel):
    session_id: UUID
    transcript: str
    response: str
    audio_url: str | None = None
    status: str = "success"
