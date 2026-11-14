from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore

from app.rag import vector_store


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
    def from_document(cls, document: Document, score: float) -> "RetrievedChunk":
        meta = document.metadata
        return cls(
            text=document.page_content,
            score=float(score),
            source=meta.get("source", ""),
            document_title=meta.get("document_title", ""),
            section=meta.get("section", ""),
            category=meta.get("category", ""),
            last_reviewed=meta.get("last_reviewed", ""),
        )


def retrieve(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    *,
    store: QdrantVectorStore | None = None,
    min_score: float | None = None,
) -> list[RetrievedChunk]:
    store = store or vector_store.get_vector_store()

    results = vector_store.similarity_search(
        store,
        query,
        limit=top_k,
        category=category,
        score_threshold=min_score,
    )
    return [RetrievedChunk.from_document(document, score) for document, score in results]


def format_context(chunks: Sequence[RetrievedChunk]) -> str:
    if not chunks:
        return "No relevant clinic information was found."

    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(f"[{index}] {chunk.document_title} — {chunk.section}\n{chunk.text}")
    return "\n\n".join(blocks)
