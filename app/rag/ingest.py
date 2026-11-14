"""Ingestion CLI.

    uv run python -m app.rag.ingest            # incremental: replace changed files
    uv run python -m app.rag.ingest --rebuild  # drop the collection and re-index

Embedding happens once, offline. Nothing here runs during a user request.
"""

import argparse
import logging
import time
from collections import Counter

from app.core.config import settings
from app.rag import vector_store
from app.rag.chunking import KNOWLEDGE_BASE_DIR, Chunk, load_chunks
from app.rag.embeddings import get_embedder

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s | %(message)s")
logger = logging.getLogger("ingest")

BATCH_SIZE = 64


def ingest(rebuild: bool = False) -> dict:
    started = time.perf_counter()

    embedder = get_embedder()
    client = vector_store.get_qdrant()

    if rebuild and client.collection_exists(settings.QDRANT_COLLECTION):
        logger.info("dropping collection %s", settings.QDRANT_COLLECTION)
        client.delete_collection(settings.QDRANT_COLLECTION)

    created = vector_store.ensure_collection(client, embedder.dimension)
    logger.info(
        "%s collection %s (%d dims)",
        "created" if created else "using existing",
        settings.QDRANT_COLLECTION,
        embedder.dimension,
    )

    chunks: list[Chunk] = load_chunks()
    by_source: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        by_source.setdefault(chunk.source, []).append(chunk)

    for source, source_chunks in by_source.items():
        vector_store.delete_source(client, source)
        for start in range(0, len(source_chunks), BATCH_SIZE):
            batch = source_chunks[start : start + BATCH_SIZE]
            vectors = embedder.embed_documents([chunk.text for chunk in batch])
            vector_store.upsert_chunks(client, batch, vectors)
        logger.info("indexed %-32s %2d chunks", source, len(source_chunks))

    stats = vector_store.collection_stats(client)
    elapsed = time.perf_counter() - started

    summary = {
        "files": len(by_source),
        "chunks": len(chunks),
        "categories": dict(Counter(chunk.category for chunk in chunks)),
        "collection": stats,
        "seconds": round(elapsed, 2),
        "embedder": embedder.name,
    }
    logger.info("done: %s chunks in %s files, %.2fs", len(chunks), len(by_source), elapsed)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Index the clinic knowledge base into Qdrant.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="drop the collection first (needed if the embedder or dimension changed)",
    )
    args = parser.parse_args()

    logger.info("knowledge base: %s", KNOWLEDGE_BASE_DIR)
    ingest(rebuild=args.rebuild)


if __name__ == "__main__":
    main()
