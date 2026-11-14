"""Qdrant access: collection setup, upserts and similarity search."""

from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient, models

from app.core.config import settings
from app.rag.embeddings import get_embedder

# Cosine is the right default for normalised text embeddings: scores land in
# [-1, 1], so 0.65 means the same thing for every document.
DISTANCE = models.Distance.COSINE


@lru_cache
def get_qdrant() -> QdrantClient:
    if not settings.qdrant_configured:
        raise RuntimeError("Qdrant is not configured. Set QDRANT_URL and QDRANT_API_KEY in .env")
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        timeout=30,
    )


def ensure_collection(
    client: QdrantClient, dimension: int | None = None, *, create_indexes: bool = True
) -> bool:
    """Create the collection if missing. Returns True when it was created."""
    dimension = dimension or get_embedder().dimension
    collection = settings.QDRANT_COLLECTION

    if client.collection_exists(collection):
        info = client.get_collection(collection)
        existing = info.config.params.vectors.size  # type: ignore[union-attr]
        if existing != dimension:
            raise ValueError(
                f"Collection '{collection}' has {existing} dimensions but the embedder "
                f"produces {dimension}. Rebuild the collection with --rebuild."
            )
        return False

    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(size=dimension, distance=DISTANCE),
    )
    # Payload indexes make filtered search cheap: without one, Qdrant scans every
    # payload to resolve a category filter. They are a no-op in local mode.
    if create_indexes:
        for field_name in ("category", "source"):
            client.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
    return True


def upsert_chunks(
    client: QdrantClient, chunks: Sequence[Any], vectors: Sequence[Sequence[float]]
) -> None:
    points = [
        models.PointStruct(id=chunk.id, vector=list(vector), payload=chunk.payload())
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    if points:
        client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points, wait=True)


def delete_source(client: QdrantClient, source: str) -> None:
    """Remove every point from one source file.

    Re-ingesting a file means delete-then-insert, not insert: a section removed
    from the markdown must also disappear from the index.
    """
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(key="source", match=models.MatchValue(value=source))]
            )
        ),
        wait=True,
    )


def search(
    client: QdrantClient,
    vector: Sequence[float],
    limit: int = 5,
    category: str | None = None,
    score_threshold: float | None = None,
) -> list[models.ScoredPoint]:
    query_filter = None
    if category:
        query_filter = models.Filter(
            must=[models.FieldCondition(key="category", match=models.MatchValue(value=category))]
        )

    response = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=list(vector),
        limit=limit,
        query_filter=query_filter,
        score_threshold=score_threshold,
        with_payload=True,
    )
    return response.points


def collection_stats(client: QdrantClient) -> dict[str, Any]:
    info = client.get_collection(settings.QDRANT_COLLECTION)
    return {
        "name": settings.QDRANT_COLLECTION,
        "points": info.points_count,
        "dimension": info.config.params.vectors.size,  # type: ignore[union-attr]
        "distance": info.config.params.vectors.distance.name,  # type: ignore[union-attr]
    }
