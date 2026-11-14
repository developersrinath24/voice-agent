"""Embedding providers.

The retrieval code only depends on the small ``EmbeddingProvider`` protocol, so
swapping local fastembed for a hosted model (Gemini, OpenAI, Voyage) means adding
one class and re-indexing — no changes to chunking, storage or search.

Whatever you choose, the vector size is baked into the Qdrant collection when it
is created. Changing provider later means changing ``dimension`` and rebuilding
the collection.
"""

from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


class EmbeddingProvider(Protocol):
    name: str
    dimension: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedder:
    """Local ONNX embeddings. No API key, no per-request cost.

    bge models are trained with different prompts for documents and queries, so
    ``embed_documents`` and ``embed_query`` are deliberately separate: feeding a
    query through the document path measurably hurts recall.
    """

    name = MODEL_NAME
    dimension = EMBEDDING_DIM

    def __init__(self) -> None:
        # The model weights (~50 MB) are downloaded on first use, then cached on
        # disk. Keeping construction lazy means importing the app stays fast.
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


@lru_cache
def get_embedder() -> FastEmbedder:
    return FastEmbedder()
