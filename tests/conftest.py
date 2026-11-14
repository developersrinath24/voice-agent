"""Shared test fixtures.

Tests never touch the network: Supabase is replaced with an in-memory fake.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import supabase_client
from app.main import app


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
def client(fake_supabase: FakeSupabase):
    app.dependency_overrides[supabase_client] = lambda: fake_supabase
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
