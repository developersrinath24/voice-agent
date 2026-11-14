# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed

# Pinned to the uv version that produced uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/

WORKDIR /app

# Dependencies first: this layer only rebuilds when the lock file changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Bake the embedding model into the image (~50 MB). The first real request is
# then not a download, and the container works with outbound traffic restricted.
RUN mkdir -p "$FASTEMBED_CACHE_PATH" \
    && uv run python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" \
    && chmod -R a+rX "$FASTEMBED_CACHE_PATH"

COPY app ./app
COPY db ./db
COPY knowledge_base ./knowledge_base

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

# One worker on purpose: each worker loads its own copy of the ONNX embedding
# model. Concurrency comes from the thread pool that runs the sync endpoints,
# not from extra processes. --proxy-headers makes client IPs correct behind Caddy.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
