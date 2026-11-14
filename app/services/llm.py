"""Chat model construction and provider ordering.

DeepSeek exposes an OpenAI-compatible API, so ``ChatOpenAI`` with a different
base URL avoids a bespoke client. ``with_fallbacks`` is the whole reason to build
this on LangChain: if the primary provider times out, returns 5xx, or refuses a
request for billing reasons, the same chain continues on the next model with no
hand-written error handling.

Order comes from ``LLM_ORDER`` so the working provider can change without a code
change. If a provider is listed but has no API key, it is skipped rather than
left to fail on every request.
"""

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from app.core.config import settings

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
REQUEST_TIMEOUT = 45
MAX_RETRIES = 2
KNOWN_PROVIDERS = ("deepseek", "gemini")


class LLMNotConfigured(RuntimeError):
    pass


def configured_providers() -> list[str]:
    """Provider names in call order, limited to those with an API key."""
    has_key = {
        "deepseek": bool(settings.DEEPSEEK_API_KEY),
        "gemini": bool(settings.GEMINI_API_KEY),
    }

    requested = [name.strip().lower() for name in settings.LLM_ORDER.split(",") if name.strip()]
    ordered = [name for name in requested if has_key.get(name)]
    # Anything configured but not mentioned in LLM_ORDER still gets used, after
    # the explicitly ordered providers, rather than being silently ignored.
    ordered += [name for name in KNOWN_PROVIDERS if has_key[name] and name not in ordered]
    return ordered


def _build(name: str) -> BaseChatModel:
    if name == "deepseek":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.2,
            timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES,
        )

    if name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # "lite" models use fixed sampling, so passing temperature only produces
        # a warning on every call.
        sampling = {} if "lite" in settings.GEMINI_MODEL else {"temperature": 0.2}

        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES,
            **sampling,
        )

    raise ValueError(f"Unknown LLM provider: {name}")


def build_llm() -> Runnable:
    providers = configured_providers()
    if not providers:
        raise LLMNotConfigured(
            "No language model configured. Set DEEPSEEK_API_KEY and/or GEMINI_API_KEY in .env"
        )

    # Imports are local so a missing optional provider package cannot stop the app
    # from starting, and so the Google SDK's import-time warnings stay out of
    # normal start-up logs.
    models = [_build(name) for name in providers]
    primary, *fallbacks = models
    return primary.with_fallbacks(fallbacks) if fallbacks else primary


@lru_cache
def get_llm() -> Runnable:
    return build_llm()
