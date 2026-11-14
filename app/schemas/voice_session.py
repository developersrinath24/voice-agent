from pydantic import BaseModel, Field


class VoiceSessionResponse(BaseModel):
    """Everything the browser needs to start an agent call, and nothing secret."""

    signed_url: str = Field(description="Single-use URL for the ElevenLabs client SDK.")
    max_seconds: int = Field(description="The UI hangs up after this long.")
    remaining_calls: int = Field(description="Calls left in today's demo allowance.")
