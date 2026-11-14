"""Retrieval: question in, ranked clinic passages out."""

from collections.abc import Sequence
from dataclasses import dataclass

from qdrant_client import QdrantClient

from app.rag import vector_store
from app.rag.embeddings import EmbeddingProvider, get_embedder


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    score: float
    source: str
    document_title: str
    section: str
    category: str
    last_reviewed: str

    @classmethod
    def from_scored_point(cls, point) -> "RetrievedChunk":
        payload = point.payload or {}
        return cls(
            text=payload.get("text", ""),
            score=float(point.score),
            source=payload.get("source", ""),
            document_title=payload.get("document_title", ""),
            section=payload.get("section", ""),
            category=payload.get("category", ""),
            last_reviewed=payload.get("last_reviewed", ""),
        )


def retrieve(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    *,
    client: QdrantClient | None = None,
    embedder: EmbeddingProvider | None = None,
    min_score: float | None = None,
) -> list[RetrievedChunk]:
    """Embed the query and return the closest chunks.

    ``min_score`` is a relevance floor. Without one, Qdrant always returns
    ``top_k`` results, even when the best match is unrelated — the classic cause
    of a RAG bot confidently answering a question the knowledge base never
    covers.
    """
    client = client or vector_store.get_qdrant()
    embedder = embedder or get_embedder()

    vector = embedder.embed_query(query)
    points = vector_store.search(
        client,
        vector,
        limit=top_k,
        category=category,
        score_threshold=min_score,
    )
    return [RetrievedChunk.from_scored_point(point) for point in points]


def format_context(chunks: Sequence[RetrievedChunk]) -> str:
    """Render retrieved chunks for a prompt: numbered, with a source line each."""
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(f"[{index}] {chunk.document_title} — {chunk.section}\n{chunk.text}")
    return "\n\n".join(blocks)
