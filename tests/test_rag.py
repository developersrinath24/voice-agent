"""Tests for chunking, indexing and retrieval.

Nothing here downloads a model or touches Qdrant Cloud: the embedder is a
deterministic fake and the vector store is Qdrant's in-memory mode, which runs
the same query engine as production.
"""

from uuid import UUID, uuid4

from app.rag import vector_store
from app.rag.chunking import Chunk, load_chunks, parse_document, split_sections
from app.rag.retriever import format_context, retrieve

# ---------------------------------------------------------------------------
# chunking
# ---------------------------------------------------------------------------


def test_parse_document_splits_front_matter():
    meta, body = parse_document("---\ntitle: Appointments\ncategory: appointments\n---\n\n# Hi\n")
    assert meta == {"title": "Appointments", "category": "appointments"}
    assert body.lstrip().startswith("# Hi")


def test_parse_document_without_front_matter_returns_body_only():
    meta, body = parse_document("# Just a heading\n\ntext")
    assert meta == {}
    assert body.startswith("# Just a heading")


def test_split_sections_uses_h2_boundaries():
    sections = list(split_sections("# Doc\n\n## First\nalpha\n\n## Second\nbeta\n"))
    assert sections == [("First", "alpha"), ("Second", "beta")]


def test_knowledge_base_produces_chunks():
    chunks = load_chunks()
    assert len(chunks) >= 60
    assert {chunk.category for chunk in chunks} >= {"appointments", "prescriptions", "urgent-care"}
    assert all(chunk.text.strip() for chunk in chunks)
    assert all(chunk.last_reviewed for chunk in chunks)


def test_chunk_ids_are_valid_and_unique():
    chunks = load_chunks()
    ids = [chunk.id for chunk in chunks]
    assert len(ids) == len(set(ids))
    for chunk_id in ids[:5]:
        UUID(chunk_id)  # raises if not a UUID, which Qdrant requires


def test_reloading_produces_identical_ids():
    """Deterministic IDs are what make re-ingestion idempotent."""
    first = load_chunks()
    second = load_chunks()
    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]


def test_chunks_carry_section_context():
    chunks = load_chunks()
    hours = next(chunk for chunk in chunks if chunk.section == "Opening hours")
    assert hours.document_title == "About Bramble Court Surgery"
    assert hours.text.startswith("About Bramble Court Surgery — Opening hours")


def test_readme_is_not_indexed():
    sources = {chunk.source for chunk in load_chunks()}
    assert "README.md" not in sources


# ---------------------------------------------------------------------------
# retrieval
# ---------------------------------------------------------------------------


def _chunk(text: str, section: str, category: str) -> Chunk:
    return Chunk(
        id=str(uuid4()),
        text=text,
        source=f"{category}.md",
        document_title="Bramble Court Surgery",
        section=section,
        category=category,
        last_reviewed="2026-11-01",
    )


def _index(store, chunks, embedder):
    vector_store.ensure_collection(store, embedder.dimension, create_indexes=False)
    for chunk in chunks:
        vector_store.upsert_chunks(store, [chunk], embedder.embed_documents([chunk.text]))


def test_retrieval_returns_the_matching_chunk(memory_qdrant, fake_embedder):
    chunks = [
        _chunk("The surgery closes at 18:30 on weekdays", "Opening hours", "about"),
        _chunk("Repeat prescriptions take two working days", "How long it takes", "prescriptions"),
        _chunk("Call 999 for chest pain", "Emergencies", "urgent-care"),
    ]
    _index(memory_qdrant, chunks, fake_embedder)

    hits = retrieve(
        "Repeat prescriptions take two working days",
        top_k=1,
        client=memory_qdrant,
        embedder=fake_embedder,
    )

    assert [hit.section for hit in hits] == ["How long it takes"]
    assert hits[0].score > 0.99
    assert hits[0].category == "prescriptions"


def test_retrieval_can_filter_by_category(memory_qdrant, fake_embedder):
    chunks = [
        _chunk("battery charging station policy", "Parking", "about"),
        _chunk("battery charging station policy", "Fees", "fees"),
    ]
    _index(memory_qdrant, chunks, fake_embedder)

    hits = retrieve(
        "battery charging station policy",
        top_k=5,
        category="fees",
        client=memory_qdrant,
        embedder=fake_embedder,
    )

    assert len(hits) == 1
    assert hits[0].category == "fees"


def test_min_score_drops_irrelevant_matches(memory_qdrant, fake_embedder):
    _index(
        memory_qdrant,
        [_chunk("The surgery has 14 parking spaces", "Parking", "about")],
        fake_embedder,
    )

    hits = retrieve(
        "zzzz qqqq",
        top_k=5,
        client=memory_qdrant,
        embedder=fake_embedder,
        min_score=0.95,
    )

    assert hits == []


def test_format_context_numbers_sources(memory_qdrant, fake_embedder):
    chunks = [
        _chunk("The surgery closes at 18:30", "Opening hours", "about"),
        _chunk("Repeat prescriptions take two working days", "How long it takes", "prescriptions"),
    ]
    _index(memory_qdrant, chunks, fake_embedder)

    context = format_context(
        retrieve("closes", top_k=2, client=memory_qdrant, embedder=fake_embedder)
    )

    assert context.startswith("[1] Bramble Court Surgery — ")
    assert "\n[2] Bramble Court Surgery — " in context


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_search_endpoint_returns_hits(client, memory_qdrant, fake_embedder):
    from app.main import app
    from app.rag.embeddings import get_embedder

    _index(
        memory_qdrant,
        [_chunk("The surgery closes at 18:30", "Opening hours", "about")],
        fake_embedder,
    )
    app.dependency_overrides[vector_store.get_qdrant] = lambda: memory_qdrant
    app.dependency_overrides[get_embedder] = lambda: fake_embedder

    response = client.post("/search", json={"query": "The surgery closes at 18:30", "top_k": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["section"] == "Opening hours"
    assert body["results"][0]["source"] == "about.md"


def test_search_endpoint_validates_top_k(client):
    assert client.post("/search", json={"query": "hi", "top_k": 0}).status_code == 422
    assert client.post("/search", json={"query": ""}).status_code == 422
