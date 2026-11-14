from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Healthcare Voice AI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    # When set, every paid endpoint requires an X-API-Key header. Leave empty for
    # local development; set it before exposing the API to the internet.
    API_KEY: str = ""

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # Qdrant
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "clinic_knowledge"

    # LLM
    # Call order. Providers listed without an API key are skipped automatically.
    LLM_ORDER: str = "gemini,deepseek"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-flash"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # Voice (ElevenLabs)
    ELEVENLABS_API_KEY: str = ""
    # Agent created in the ElevenLabs dashboard for realtime calls. Its custom
    # LLM points at POST /v1/chat/completions on this API.
    ELEVENLABS_AGENT_ID: str = ""
    # Shared secret ElevenLabs sends on every custom-LLM request. Deliberately
    # separate from API_KEY: ElevenLabs must know this one, and it opens only
    # the agent endpoint, not /chat or /search.
    AGENT_LLM_SECRET: str = ""
    # A call spends credits for as long as it is open and the demo is public,
    # so both the length and the daily number are capped in the backend.
    VOICE_MAX_CALL_SECONDS: int = 90
    VOICE_DAILY_CALL_LIMIT: int = 10
    # Scribe v3 does recorded speech-to-text. Flash v2.5 is the low-latency TTS
    # model; eleven_v4_turbo is more expressive at a higher price.
    ELEVENLABS_STT_MODEL: str = "scribe_v3"
    ELEVENLABS_TTS_MODEL: str = "eleven_flash_v2_5"
    # Bella — a calm premade voice, suited to a receptionist. Premade voices work
    # on the free tier; most of the voice library (Rachel included) is paid-only
    # through the API and returns 402 on a free key. Any voice on your account
    # works here — copy the id from the ElevenLabs dashboard.
    ELEVENLABS_VOICE_ID: str = "EXAVITQu4vr4xnSDxMaL"
    # Stay under the 25 MB request body limit set in the Caddy configs.
    VOICE_MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024

    # Retrieval
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_MIN_SCORE: float = 0.5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_KEY)

    @property
    def qdrant_configured(self) -> bool:
        return bool(self.QDRANT_URL and self.QDRANT_API_KEY)

    @property
    def elevenlabs_configured(self) -> bool:
        return bool(self.ELEVENLABS_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
