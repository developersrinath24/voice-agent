"""Tests for loading, indexing and retrieval.

Nothing here downloads a model or touches Qdrant Cloud: embeddings are a
deterministic fake and the vector store is Qdrant's in-memory mode, which runs
the same query engine as production.
"""

from uuid import UUID

from app.rag import vector_store
from app.rag.loaders import document_id, load_documents, parse_front_matter
from app.rag.retriever import format_context, retrieve
from tests.conftest import make_document


def _index(store, documents):
    vector_store.add_documents(store, documents, [document_id(d) for d in documents])


# ---------------------------------------------------------------------------
# loading and chunking
# ---------------------------------------------------------------------------


def test_parse_front_matter():
    meta, body = parse_front_matter(
        "---\ntitle: Appointments\ncategory: appointments\n---\n\n# Hi\n"
    )
    assert meta == {"title": "Appointments", "category": "appointments"}
    assert body.lstrip().startswith("# Hi")


def test_parse_without_front_matter_returns_body_only():
    meta, body = parse_front_matter("# Just a heading\n\ntext")
    assert meta == {}
    assert body.startswith("# Just a heading")


def test_knowledge_base_produces_documents():
    documents = load_documents()
    assert len(documents) >= 60
    categories = {d.metadata["category"] for d in documents}
    assert {"appointments", "prescriptions", "urgent-care"} <= categories
    assert all(d.page_content.strip() for d in documents)
    assert all(d.metadata["last_reviewed"] for d in documents)


def test_document_ids_are_unique_valid_and_stable():
    first = load_documents()
    second = load_documents()
    ids = [document_id(d) for d in first]

    assert len(ids) == len(set(ids))
    assert ids == [document_id(d) for d in second], "re-ingestion must be idempotent"
    UUID(ids[0])  # Qdrant requires a UUID or integer point ID


def test_chunks_carry_heading_context():
    documents = load_documents()
    hours = next(d for d in documents if d.metadata["section"] == "Opening hours")
    assert hours.page_content.startswith("About Bramble Court Surgery — Opening hours")
    assert hours.metadata["category"] == "about"


def test_readme_is_not_indexed():
    assert "README.md" not in {d.metadata["source"] for d in load_documents()}


# ---------------------------------------------------------------------------
# retrieval
# ---------------------------------------------------------------------------


def test_retrieval_ranks_the_exact_match_first(memory_store):
    documents = [
        make_document("The surgery closes at 18:30 on weekdays", "Opening hours"),
        make_document(
            "Repeat prescriptions take two working days", "How long it takes", "prescriptions"
        ),
        make_document("Call 999 for chest pain", "Emergencies", "urgent-care"),
    ]
    _index(memory_store, documents)

    hits = retrieve(
        "Repeat prescriptions take two working days",
        top_k=1,
        store=memory_store,
    )

    assert [hit.section for hit in hits] == ["How long it takes"]
    # Not 1.0: the stored text carries a document/section prefix the query lacks.
    assert hits[0].score > 0.95
    assert hits[0].category == "prescriptions"


def test_retrieval_filters_by_category(memory_store):
    _index(
        memory_store,
        [
            make_document("battery charging station policy", "Parking", "about"),
            make_document("battery charging station policy", "Fees", "fees"),
        ],
    )

    hits = retrieve("battery charging station policy", top_k=5, category="fees", store=memory_store)

    assert len(hits) == 1
    assert hits[0].category == "fees"


def test_min_score_drops_irrelevant_matches(memory_store):
    _index(memory_store, [make_document("The surgery has 14 parking spaces", "Parking")])

    assert retrieve("zzzz qqqq", top_k=5, store=memory_store, min_score=0.95) == []


def test_format_context_numbers_sources(memory_store):
    _index(
        memory_store,
        [
            make_document("The surgery closes at 18:30", "Opening hours"),
            make_document(
                "Prescriptions take two working days", "How long it takes", "prescriptions"
            ),
        ],
    )

    chunks = retrieve("closes", top_k=2, store=memory_store)

    assert format_context(chunks).startswith("[1] Bramble Court Surgery — ")
    assert format_context([]) == "No relevant clinic information was found."


def test_delete_source_removes_only_that_file(memory_store):
    _index(
        memory_store,
        [
            make_document("hours", "Opening hours", "about"),
            make_document("fees", "Current fees", "fees"),
        ],
    )
    vector_store.delete_source(memory_store, "about.md")

    assert {
        doc.metadata["source"]
        for doc, _ in vector_store.similarity_search(memory_store, "hours", 10)
    } == {"fees.md"}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_search_endpoint_returns_hits(client, memory_store):
    from app.main import app

    _index(memory_store, [make_document("The surgery closes at 18:30", "Opening hours")])
    app.dependency_overrides[vector_store.get_store] = lambda: memory_store

    response = client.post("/search", json={"query": "The surgery closes at 18:30", "top_k": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["section"] == "Opening hours"
    assert body["results"][0]["source"] == "about.md"


def test_search_endpoint_validates_input(client):
    assert client.post("/search", json={"query": "hi", "top_k": 0}).status_code == 422
    assert client.post("/search", json={"query": ""}).status_code == 422
