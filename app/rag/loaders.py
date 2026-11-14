"""Load the clinic documents into LangChain ``Document`` objects.

LangChain's splitter does the mechanical work; the policy stays ours:

* one chunk per ``##`` section, because a chunk should be one answer
* YAML front matter becomes metadata, so search can filter by category and the
  API can cite a source
* the document title and section heading are prefixed onto the embedded text,
  which measurably improves matching on a corpus this small
* chunk IDs are deterministic, so re-ingesting replaces instead of duplicating
"""

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base"

HEADERS_TO_SPLIT_ON = [("##", "section")]

# Sections longer than this get split again. Our documents stay well under it;
# the guard exists so a long future page cannot become one diluted vector.
MAX_CHUNK_CHARS = 1200


def parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    """Split flat ``key: value`` front matter from the markdown body.

    Hand-rolled rather than pulling in a YAML parser for six keys. Unexpected
    lines are ignored rather than fatal, so a typo cannot block ingestion.
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


def load_documents(root: Path = KNOWLEDGE_BASE_DIR) -> list[Document]:
    """Read every knowledge base file and split it into section documents."""
    paths = sorted(path for path in root.glob("*.md") if path.name != "README.md")
    if not paths:
        raise FileNotFoundError(f"No markdown files found in {root}")

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=True,
    )

    documents: list[Document] = []
    for path in paths:
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        source = path.relative_to(root).as_posix()
        document_title = meta.get("title", path.stem)

        seen: dict[str, int] = {}
        for section_doc in splitter.split_text(body):
            section = section_doc.metadata.get("section", document_title)
            nth = seen.get(section, 0)
            seen[section] = nth + 1

            for part, piece in enumerate(_split_long(section_doc.page_content)):
                position = nth * 100 + part
                # Prefixing the heading puts the subject into the vector, not just
                # the words of the body.
                documents.append(
                    Document(
                        page_content=f"{document_title} — {section}\n\n{piece}",
                        metadata={
                            "source": source,
                            "document_title": document_title,
                            "section": section,
                            "category": meta.get("category", "uncategorised"),
                            "last_reviewed": meta.get("last_reviewed", ""),
                            "position": position,
                        },
                    )
                )
    return documents


def document_id(document: Document) -> str:
    """Deterministic ID from source, section and position.

    Same document -> same ID -> ``add`` overwrites rather than duplicates, which
    makes re-ingestion idempotent in both directions.
    """
    meta = document.metadata
    return str(
        uuid5(
            NAMESPACE_URL,
            f"{meta['source']}#{meta['section']}#{meta.get('position', 0)}",
        )
    )
