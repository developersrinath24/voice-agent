from fastapi import APIRouter, HTTPException

from app.rag.catalog import load_catalog
from app.schemas.documents import DocumentResponse, SectionResponse

router = APIRouter()


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents() -> list[DocumentResponse]:
    """The knowledge base, section by section, for the demo's reading pane.

    Read from the same files ingestion reads, so a viewer can compare an answer
    against the text it was drawn from. Deliberately unauthenticated: it is
    read-only, fictional, and the whole point of the demo.
    """
    try:
        catalog = load_catalog()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return [
        DocumentResponse(
            source=entry.source,
            title=entry.title,
            category=entry.category,
            last_reviewed=entry.last_reviewed,
            sections=[
                SectionResponse(section=section.section, content=section.content)
                for section in entry.sections
            ],
            chunk_count=entry.chunk_count,
        )
        for entry in catalog
    ]
