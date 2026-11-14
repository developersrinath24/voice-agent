"""The knowledge base endpoint exists so the demo can show its own sources."""

from app.core.config import settings


def test_documents_lists_every_file(client):
    response = client.get("/documents")
    assert response.status_code == 200

    body = response.json()
    assert len(body) == 10, "one entry per markdown file, README excluded"
    assert {"01-about-the-practice.md", "04-prescriptions.md"} <= {
        document["source"] for document in body
    }


def test_documents_total_matches_the_indexed_chunk_count(client):
    body = client.get("/documents").json()
    assert sum(document["chunk_count"] for document in body) == 78


def test_every_document_has_sections_with_content(client):
    for document in client.get("/documents").json():
        assert document["title"]
        assert document["sections"], f"{document['source']} has no sections"
        for section in document["sections"]:
            assert section["section"]
            assert section["content"].strip()


def test_section_content_excludes_the_embedding_prefix(client):
    """The ``Title — Section`` prefix is for the vector, not for the reader."""
    for document in client.get("/documents").json():
        for section in document["sections"]:
            assert not section["content"].startswith(f"{document['title']} — ")


def test_documents_are_public_even_with_an_api_key_set(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    assert client.get("/documents").status_code == 200
