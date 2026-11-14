from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from app.agents.clinic_assistant import Answer
from app.api.deps import clinic_assistant, supabase_client
from app.core.config import settings
from app.main import app

EMBEDDING_DIM = 8


class FakeEmbeddings(Embeddings):
    """Deterministic bag-of-characters embedder.

    Identical text always gives an identical unit vector and overlapping text
    gives a higher cosine score, which is enough to exercise storage, filtering
    and ranking without downloading a model or calling an API.
    """

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for character in text.lower():
            vector[ord(character) % EMBEDDING_DIM] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.fixture
def fake_embeddings() -> FakeEmbeddings:
    return FakeEmbeddings()


@pytest.fixture
def memory_store(fake_embeddings: FakeEmbeddings) -> QdrantVectorStore:
    """Real Qdrant behaviour in-process. Same API surface as Qdrant Cloud."""
    client = QdrantClient(location=":memory:")
    client.create_collection(
        collection_name=settings.QDRANT_COLLECTION,
        vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
    )
    return QdrantVectorStore(
        client=client,
        collection_name=settings.QDRANT_COLLECTION,
        embedding=fake_embeddings,
    )


def make_document(body: str, section: str, category: str = "about") -> Document:
    return Document(
        page_content=f"Bramble Court Surgery — {section}\n\n{body}",
        metadata={
            "source": f"{category}.md",
            "document_title": "Bramble Court Surgery",
            "section": section,
            "category": category,
            "last_reviewed": "2026-11-01",
            "position": 0,
        },
    )


class FakeAssistant:
    """Stands in for the RAG chain when the test is about the HTTP layer."""

    def __init__(self, text: str = "The surgery closes at 18:30."):
        self.text = text
        self.calls: list[tuple[str, Sequence[tuple[str, str]]]] = []

    def answer(self, question: str, history: Sequence[tuple[str, str]] = ()) -> Answer:
        self.calls.append((question, history))
        return Answer(text=self.text, sources=[], grounded=True)


@pytest.fixture
def fake_assistant() -> FakeAssistant:
    return FakeAssistant()


class FakeResult:
    def __init__(self, data: list[dict], count: int | None = None):
        self.data = data
        self.count = count


class FakeTable:
    """Minimal stand-in for the parts of supabase-py this project uses."""

    def __init__(self, name: str, store: dict[str, list[dict]]):
        self.name = name
        self.store = store
        self._op: str | None = None
        self._payload: dict | None = None
        self._filters: list[tuple[str, str]] = []
        self._limit: int | None = None
        self._count = False
        self._desc = False

    # -- builder methods ----------------------------------------------------
    def insert(self, payload: dict) -> "FakeTable":
        self._op = "insert"
        self._payload = payload
        return self

    def select(self, columns: str = "*", count: str | None = None) -> "FakeTable":
        self._op = "select"
        self._count = count == "exact"
        return self

    def update(self, payload: dict) -> "FakeTable":
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, column: str, value: object) -> "FakeTable":
        self._filters.append((column, str(value)))
        return self

    def order(self, column: str, desc: bool = False) -> "FakeTable":
        self._desc = desc
        return self

    def limit(self, size: int) -> "FakeTable":
        self._limit = size
        return self

    # -- execution ----------------------------------------------------------
    def _defaults(self, row: dict) -> dict:
        now = datetime.now(UTC).isoformat()
        base = {"id": str(uuid4()), "created_at": now}
        if self.name == "sessions":
            base.update({"status": "active", "updated_at": now})
        return {**base, **row}

    def execute(self) -> FakeResult:
        rows = self.store.setdefault(self.name, [])

        if self._op == "insert":
            row = self._defaults(self._payload or {})
            rows.append(row)
            return FakeResult([dict(row)])

        matched = [r for r in rows if all(str(r.get(c)) == v for c, v in self._filters)]

        if self._op == "update":
            for row in matched:
                row.update(self._payload or {})
            return FakeResult([dict(r) for r in matched])

        total = len(matched)
        if self._desc:
            matched = list(reversed(matched))
        if self._limit is not None:
            matched = matched[: self._limit]
        return FakeResult([dict(r) for r in matched], count=total if self._count else None)


class FakeSupabase:
    def __init__(self):
        self.store: dict[str, list[dict]] = {"sessions": [], "messages": []}

    def table(self, name: str) -> FakeTable:
        return FakeTable(name, self.store)


@pytest.fixture
def fake_supabase() -> FakeSupabase:
    return FakeSupabase()


@pytest.fixture
def client(fake_supabase: FakeSupabase, fake_assistant: FakeAssistant):
    app.dependency_overrides[supabase_client] = lambda: fake_supabase
    app.dependency_overrides[clinic_assistant] = lambda: fake_assistant
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
