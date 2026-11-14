from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000, description="Natural language query.")
    top_k: int = Field(default=5, ge=1, le=20, description="How many chunks to return.")
    category: str | None = Field(
        default=None,
        description="Restrict to one knowledge base category, e.g. 'appointments'.",
    )
    min_score: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Relevance floor. Results below this cosine score are dropped.",
    )


class SearchHit(BaseModel):
    score: float
    text: str
    source: str
    document_title: str
    section: str
    category: str
    last_reviewed: str


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[SearchHit]
