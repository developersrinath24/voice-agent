from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from langchain_qdrant import QdrantVectorStore

from app.rag import retriever, vector_store
from app.schemas.search import SearchHit, SearchRequest, SearchResponse

router = APIRouter()

# A dependency rather than a direct call, so tests can inject an in-memory store
# and a fake embedder.
VectorStore = Annotated[QdrantVectorStore, Depends(vector_store.get_store)]


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest, store: VectorStore) -> SearchResponse:
    """Debug endpoint: what retrieval returns, before any LLM is involved.

    Reach for this when the assistant gives a wrong answer. If the right passage
    is not in these results, the problem is indexing or chunking, not the model.
    """
    try:
        chunks = retriever.retrieve(
            request.query,
            top_k=request.top_k,
            category=request.category,
            store=store,
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
