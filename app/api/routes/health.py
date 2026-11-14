from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness plus a view of which integrations are configured.

    This reports configuration presence only. It does not call out to Supabase,
    Qdrant or any model provider, so it stays fast and cannot fail on a
    third-party outage.
    """
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "configured": {
            "supabase": settings.supabase_configured,
            "qdrant": settings.qdrant_configured,
            "deepseek": bool(settings.DEEPSEEK_API_KEY),
            "gemini": bool(settings.GEMINI_API_KEY),
            "elevenlabs": bool(settings.ELEVENLABS_API_KEY),
        },
    }
