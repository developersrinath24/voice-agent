from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from qdrant_client import QdrantClient

from app.rag import retriever, vector_store
from app.rag.embeddings import EmbeddingProvider, get_embedder
from app.schemas.search import SearchHit, SearchRequest, SearchResponse

router = APIRouter()

# Dependencies rather than direct calls, so tests can inject an in-memory Qdrant
# client and a deterministic fake embedder.
Embedder = Annotated[EmbeddingProvider, Depends(get_embedder)]
Qdrant = Annotated[QdrantClient, Depends(vector_store.get_qdrant)]


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, embedder: Embedder, client: Qdrant) -> SearchResponse:
    """Debug endpoint: shows exactly what retrieval returns, before any LLM.

    This is the tool to reach for when the assistant gives a wrong answer. If the
    right passage is not in these results, the problem is indexing or chunking,
    not the model.
    """
    try:
        chunks = retriever.retrieve(
            request.query,
            top_k=request.top_k,
            category=request.category,
            client=client,
            embedder=embedder,
            min_score=request.min_score,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return SearchResponse(
        query=request.query,
        count=len(chunks),
        results=[
            SearchHit(
                score=round(chunk.score, 4),
                text=chunk.text,
                source=chunk.source,
                document_title=chunk.document_title,
                section=chunk.section,
                category=chunk.category,
                last_reviewed=chunk.last_reviewed,
            )
            for chunk in chunks
        ],
    )
