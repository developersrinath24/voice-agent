from functools import lru_cache
from typing import Any

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from app.core.config import settings
from app.rag.embeddings import get_embedder, get_langchain_embeddings

DISTANCE = models.Distance.COSINE

# LangChain stores this shape by default: page content under one key, metadata
# under another. Filters therefore need the ``metadata.`` prefix.
METADATA_PREFIX = "metadata"


@lru_cache
def get_qdrant_client() -> QdrantClient:
    if not settings.qdrant_configured:
        raise RuntimeError("Qdrant is not configured. Set QDRANT_URL and QDRANT_API_KEY in .env")
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=30)


def ensure_collection(client: QdrantClient, dimension: int | None = None) -> bool:

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
    # Payload indexes make filtered search cheap: without one Qdrant scans every
    # payload to resolve a category filter. No-ops in local mode.
    for field_name in (f"{METADATA_PREFIX}.category", f"{METADATA_PREFIX}.source"):
        client.create_payload_index(
            collection_name=collection,
            field_name=field_name,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    return True


def get_vector_store(client: QdrantClient | None = None) -> QdrantVectorStore:
    client = client or get_qdrant_client()
    ensure_collection(client)
    return QdrantVectorStore(
        client=client,
        collection_name=settings.QDRANT_COLLECTION,
        embedding=get_langchain_embeddings(),
    )


def get_store() -> QdrantVectorStore:
    return get_vector_store()


def add_documents(store: QdrantVectorStore, documents: list[Document], ids: list[str]) -> None:
    if documents:
        store.add_documents(documents, ids=ids)


def delete_source(store: QdrantVectorStore, source: str) -> None:
    store.client.delete(
        collection_name=store.collection_name,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key=f"{METADATA_PREFIX}.source",
                        match=models.MatchValue(value=source),
                    )
                ]
            )
        ),
        wait=True,
    )


def build_filter(category: str | None) -> models.Filter | None:
    if not category:
        return None
    return models.Filter(
        must=[
            models.FieldCondition(
                key=f"{METADATA_PREFIX}.category",
                match=models.MatchValue(value=category),
            )
        ]
    )


def similarity_search(
    store: QdrantVectorStore,
    query: str,
    limit: int = 5,
    category: str | None = None,
    score_threshold: float | None = None,
) -> list[tuple[Document, float]]:
    return store.similarity_search_with_score(
        query,
        k=limit,
        filter=build_filter(category),  # type: ignore[arg-type]
        score_threshold=score_threshold,
    )


def collection_stats(client: QdrantClient | None = None) -> dict[str, Any]:
    client = client or get_qdrant_client()
    info = client.get_collection(settings.QDRANT_COLLECTION)
    vectors = info.config.params.vectors
    return {
        "name": settings.QDRANT_COLLECTION,
        "points": info.points_count,
        "dimension": getattr(vectors, "size", None),
        "distance": getattr(getattr(vectors, "distance", None), "name", None),
    }
