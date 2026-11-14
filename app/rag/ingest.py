"""Ingestion CLI.

    uv run python -m app.rag.ingest            # incremental: replace changed files
    uv run python -m app.rag.ingest --rebuild  # drop the collection and re-index

Embedding runs once, offline. Nothing here happens during a user request.
"""

import argparse
import logging
import time
from collections import Counter

from app.core.config import settings
from app.rag import vector_store
from app.rag.embeddings import get_embedder
from app.rag.loaders import KNOWLEDGE_BASE_DIR, document_id, load_documents

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s | %(message)s")
logger = logging.getLogger("ingest")

BATCH_SIZE = 64


def ingest(rebuild: bool = False) -> dict:
    started = time.perf_counter()

    client = vector_store.get_qdrant_client()
    collection = settings.QDRANT_COLLECTION

    if rebuild and client.collection_exists(collection):
        logger.info("dropping collection %s", collection)
        client.delete_collection(collection)

    created = vector_store.ensure_collection(client)
    logger.info(
        "%s collection %s (%d dims, %s)",
        "created" if created else "using existing",
        collection,
        get_embedder().dimension,
        vector_store.DISTANCE.name,
    )

    documents = load_documents()
    store = vector_store.get_vector_store(client)

    by_source: dict[str, list] = {}
    for document in documents:
        by_source.setdefault(document.metadata["source"], []).append(document)

    for source, source_documents in by_source.items():
        # Delete first: deterministic IDs cover edits, but not sections that were
        # removed from the file.
        vector_store.delete_source(store, source)
        for start in range(0, len(source_documents), BATCH_SIZE):
            batch = source_documents[start : start + BATCH_SIZE]
            vector_store.add_documents(store, batch, [document_id(d) for d in batch])
        logger.info("indexed %-32s %2d chunks", source, len(source_documents))

    stats = vector_store.collection_stats(client)
    elapsed = time.perf_counter() - started

    summary = {
        "files": len(by_source),
        "chunks": len(documents),
        "categories": dict(Counter(d.metadata["category"] for d in documents)),
        "collection": stats,
        "embedder": get_embedder().name,
        "seconds": round(elapsed, 2),
    }
    logger.info("done: %s chunks in %s files, %.2fs", len(documents), len(by_source), elapsed)
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
