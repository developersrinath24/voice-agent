"""Turn markdown files into retrieval-sized chunks.

Two ideas decide retrieval quality more than the model choice:

1. **Chunk boundaries.** A chunk should be one answer. Splitting on ``##``
   headings means "Repeat prescriptions take two working days" arrives together
   with the heading that gives it meaning, instead of being cut in half by a
   fixed character count.
2. **Stable IDs.** The ID is derived from file path + section heading + position,
   so re-ingesting an edited file overwrites its chunks instead of duplicating
   them. Delete a section and its vectors go with it.

Every chunk carries its metadata, which is what lets the API return citations
and lets search filter by category.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base"

# Sections longer than this are split at paragraph boundaries. Our documents stay
# well under it; the guard exists so a long future page cannot produce one giant
# vector that dilutes its own embedding.
MAX_CHUNK_CHARS = 1200


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source: str
    document_title: str
    section: str
    category: str
    last_reviewed: str
    position: int = 0

    def payload(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "document_title": self.document_title,
            "section": self.section,
            "category": self.category,
            "last_reviewed": self.last_reviewed,
            "position": self.position,
        }


def parse_document(raw: str) -> tuple[dict[str, str], str]:
    """Split YAML front matter from the markdown body.

    Hand-rolled on purpose: the front matter here is flat ``key: value`` pairs,
    and a full YAML dependency for six keys is not worth it. Anything unexpected
    is ignored rather than fatal, so a typo cannot block ingestion.
    """
    if not raw.startswith("---"):
        return {}, raw

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw

    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip():
            meta[key.strip()] = value.strip().strip("\"'")

    return meta, parts[2].lstrip("\n")


def split_sections(body: str) -> Iterator[tuple[str, str]]:
    """Yield (heading, text) pairs, one per ``##`` section."""
    document_title = ""
    heading = ""
    buffer: list[str] = []

    for line in body.splitlines():
        if line.startswith("## "):
            if heading and "".join(buffer).strip():
                yield heading, "\n".join(buffer).strip()
            heading = line[3:].strip()
            buffer = []
        elif line.startswith("# ") and not document_title:
            document_title = line[2:].strip()
        elif heading:
            buffer.append(line)
        elif line.strip():
            # Text before the first ## heading: treat the document title as the
            # section so nothing is silently dropped.
            heading = document_title or "Overview"
            buffer.append(line)

    if heading and "".join(buffer).strip():
        yield heading, "\n".join(buffer).strip()


def _split_long(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            parts.append(current)
        current = paragraph
    if current:
        parts.append(current)
    return parts


def build_chunks(path: Path, root: Path) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_document(raw)

    source = path.relative_to(root).as_posix()
    document_title = meta.get("title", path.stem)
    category = meta.get("category", "uncategorised")
    last_reviewed = meta.get("last_reviewed", "")

    chunks: list[Chunk] = []
    for heading, text in split_sections(body):
        for index, piece in enumerate(_split_long(text)):
            # Prefix the section heading so the vector encodes what the text is
            # about, not just the words inside it.
            embedded_text = f"{document_title} — {heading}\n\n{piece}"
            chunks.append(
                Chunk(
                    id=str(uuid5(NAMESPACE_URL, f"{source}#{heading}#{index}")),
                    text=embedded_text,
                    source=source,
                    document_title=document_title,
                    section=heading,
                    category=category,
                    last_reviewed=last_reviewed,
                    position=index,
                )
            )
    return chunks


def load_chunks(root: Path = KNOWLEDGE_BASE_DIR) -> list[Chunk]:
    paths = sorted(path for path in root.glob("*.md") if path.name != "README.md")
    if not paths:
        raise FileNotFoundError(f"No markdown files found in {root}")

    chunks: list[Chunk] = []
    for path in paths:
        chunks.extend(build_chunks(path, root))
    return chunks
