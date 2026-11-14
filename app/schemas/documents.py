from pydantic import BaseModel, Field


class SectionResponse(BaseModel):
    section: str
    content: str


class DocumentResponse(BaseModel):
    """One knowledge base file, with the sections that were embedded."""

    source: str = Field(description="File name inside knowledge_base/.")
    title: str
    category: str
    last_reviewed: str = ""
    sections: list[SectionResponse] = Field(default_factory=list)
    chunk_count: int = Field(default=0, description="Vectors this file produced.")
