"""Chat model construction: DeepSeek primary, Gemini fallback.

DeepSeek exposes an OpenAI-compatible API, so ``ChatOpenAI`` with a different
base URL avoids a bespoke client. ``with_fallbacks`` is the whole reason to build
this on LangChain: if the primary provider times out, returns 5xx, or rate-limits,
the same chain retries on the next model without any hand-written error handling.
"""

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from app.core.config import settings

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 2


class LLMNotConfigured(RuntimeError):
    pass


def build_llm() -> Runnable:
    """Return the configured chat model, with fallbacks when more than one exists.

    Imports are local so that a missing optional provider package cannot stop the
    app from starting, and so the Google SDK's import-time warnings stay out of
    normal start-up logs.
    """
    models: list[BaseChatModel] = []

    if settings.DEEPSEEK_API_KEY:
        from langchain_openai import ChatOpenAI

        models.append(
            ChatOpenAI(
                model=settings.DEEPSEEK_MODEL,
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                temperature=0.2,
                timeout=REQUEST_TIMEOUT,
                max_retries=MAX_RETRIES,
            )
        )

    if settings.GEMINI_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI

        models.append(
            ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.2,
                timeout=REQUEST_TIMEOUT,
                max_retries=MAX_RETRIES,
            )
        )

    if not models:
        raise LLMNotConfigured(
            "No language model configured. Set DEEPSEEK_API_KEY and/or GEMINI_API_KEY in .env"
        )

    primary, *fallbacks = models
    return primary.with_fallbacks(fallbacks) if fallbacks else primary


@lru_cache
def get_llm() -> Runnable:
    return build_llm()
