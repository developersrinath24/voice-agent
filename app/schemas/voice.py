from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.chat import SourceRef


class VoiceTurnResponse(BaseModel):
    """One spoken exchange: what was heard, what was answered, and the audio."""

    session_id: UUID
    transcript: str = Field(description="What speech-to-text heard.")
    response: str = Field(description="The grounded answer, also present as audio.")
    grounded: bool = True
    sources: list[SourceRef] = Field(default_factory=list)
    audio_base64: str = Field(description="Base64 MP3 of the spoken answer.")
    audio_mime: str = "audio/mpeg"
    timings_ms: dict[str, int] = Field(
        default_factory=dict,
        description="Wall-clock milliseconds per stage: transcribe, answer, speak.",
    )
