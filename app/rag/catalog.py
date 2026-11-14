"""The knowledge base as a reader sees it.

The retriever works in chunks; a person reading the demo wants whole sections in
document order. Both come from the same loader, so what the page shows is what
was indexed — minus the ``Title — Section`` prefix that exists only to give the
vector some subject matter.
"""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document

from app.rag.loaders import KNOWLEDGE_BASE_DIR, load_documents


@dataclass(frozen=True)
class Section:
    section: str
    content: str


@dataclass(frozen=True)
class DocumentEntry:
    source: str
    title: str
    category: str
    last_reviewed: str
    sections: list[Section]
    chunk_count: int


def _body(document: Document) -> str:
    meta = document.metadata
    prefix = f"{meta['document_title']} — {meta['section']}\n\n"
    return document.page_content.removeprefix(prefix)


def _group_by_section(documents: list[Document]) -> list[list[Document]]:
    """Chunks belonging to one heading, in order.

    ``position`` encodes the heading occurrence and the part number as
    ``occurrence * 100 + part``, so dividing by 100 separates two headings that
    share a name while still joining a section that had to be split.
    """
    groups: dict[tuple[str, str, int], list[Document]] = {}
    for document in documents:
        meta = document.metadata
        key = (meta["source"], meta["section"], int(meta.get("position", 0)) // 100)
        groups.setdefault(key, []).append(document)
    return list(groups.values())


def load_catalog(root: Path = KNOWLEDGE_BASE_DIR) -> list[DocumentEntry]:
    documents = load_documents(root)
    counts = Counter(document.metadata["source"] for document in documents)

    sections_by_source: dict[str, list[Section]] = {}
    meta_by_source: dict[str, dict] = {}

    for group in _group_by_section(documents):
        meta = group[0].metadata
        source = meta["source"]
        meta_by_source.setdefault(source, meta)
        sections_by_source.setdefault(source, []).append(
            Section(
                section=meta["section"],
                content="\n\n".join(_body(document) for document in group),
            )
        )

    entries: list[DocumentEntry] = []
    for source, sections in sections_by_source.items():
        meta = meta_by_source[source]
        entries.append(
            DocumentEntry(
                source=source,
                title=meta["document_title"],
                category=meta["category"],
                last_reviewed=meta.get("last_reviewed", ""),
                sections=sections,
                chunk_count=counts[source],
            )
        )
    return entries
