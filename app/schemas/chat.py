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


from app.rag.retriever import RetrievedChunk


class SourceRef(BaseModel):
    """One retrieved passage the answer was built from."""

    section: str
    source: str
    score: float

    @classmethod
    def from_chunk(cls, chunk: RetrievedChunk) -> "SourceRef":
        return cls(section=chunk.section, source=chunk.source, score=round(chunk.score, 4))


class ChatResponse(BaseModel):
    session_id: UUID
    response: str
    status: str = "success"
    message_count: int = 0
    grounded: bool = True
    sources: list[SourceRef] = Field(default_factory=list)
