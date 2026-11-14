"""Embeddings.

``FastEmbedder`` is our provider: local ONNX, no API key, no per-request cost.
``LangChainEmbeddings`` adapts it to LangChain's ``Embeddings`` interface so the
rest of the stack (vector store, retrievers, chains) is provider-agnostic.

Swapping to Gemini or OpenAI means writing one adapter and rebuilding the
collection — the vector size is fixed when the collection is created.
"""

from collections.abc import Sequence
from functools import lru_cache

from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


class FastEmbedder:
    """Local ONNX embeddings.

    bge models are trained with different prompts for documents and queries, so
    the two methods are deliberately separate: embedding a query through the
    document path measurably hurts recall.
    """

    name = MODEL_NAME
    dimension = EMBEDDING_DIM

    def __init__(self) -> None:
        # Weights (~50 MB) download on first use. Lazy construction keeps app
        # start-up and tests fast.
        self._model: TextEmbedding | None = None

    @property
    def model(self) -> TextEmbedding:
        if self._model is None:
            self._model = TextEmbedding(model_name=MODEL_NAME)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(value) for value in vector] for vector in self.model.embed(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self.model.query_embed(text)))
        return [float(value) for value in vector]


class LangChainEmbeddings(Embeddings):
    """Thin adapter so LangChain components can use a local model."""

    def __init__(self, provider: FastEmbedder | None = None) -> None:
        self.provider = provider or FastEmbedder()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.provider.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.provider.embed_query(text)


@lru_cache
def get_embedder() -> FastEmbedder:
    return FastEmbedder()


@lru_cache
def get_langchain_embeddings() -> LangChainEmbeddings:
    return LangChainEmbeddings(get_embedder())
