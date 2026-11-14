import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, health, search, sessions, voice
from app.core.config import settings

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
app.include_router(chat.router, tags=["Chat"])
app.include_router(sessions.router, tags=["Sessions"])
app.include_router(search.router, tags=["Search"])
app.include_router(voice.router, tags=["Voice"])


@app.get("/", tags=["Health"])
async def home() -> dict:
    return {
        "message": "Healthcare Voice AI API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
