import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import require_api_key
from app.api.routes import chat, documents, health, llm, search, sessions, voice, voice_session
from app.core.config import settings
from app.rag.embeddings import get_embedder

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "starting %s v%s [%s] supabase=%s qdrant=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.supabase_configured,
        settings.qdrant_configured,
    )
    # Load the embedding model on boot rather than inside the first user request,
    # which otherwise pays a several-second model load.
    try:
        get_embedder().embed_query("warm up")
        logger.info("embedding model ready")
    except Exception:
        logger.exception("embedding warm-up failed; the first request will retry")

    yield
    logger.info("shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description="Voice-first RAG assistant for a GP clinic",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
# The knowledge base is public on purpose: the demo's whole claim is that you can
# read the source and check the answer yourself.
app.include_router(documents.router, tags=["Documents"])

# Health, the banner and the documents stay open so a load balancer or uptime
# check needs no secret. Everything with a database write or a model call is gated.
protected = [Depends(require_api_key)]
app.include_router(chat.router, tags=["Chat"], dependencies=protected)
app.include_router(sessions.router, tags=["Sessions"], dependencies=protected)
app.include_router(search.router, tags=["Search"], dependencies=protected)
app.include_router(voice.router, tags=["Voice"], dependencies=protected)
app.include_router(voice_session.router, tags=["Voice"], dependencies=protected)

# The realtime agent's custom LLM. Not behind API_KEY: ElevenLabs authenticates
# with AGENT_LLM_SECRET instead, and the two secrets should not be the same one.
app.include_router(llm.router, tags=["Agents"])


@app.get("/", tags=["Health"])
async def home() -> dict:
    return {
        "message": "Healthcare Voice AI API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
