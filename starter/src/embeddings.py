"""Local, real semantic embeddings via FastEmbed/ONNX; no API or mock fallback."""
from typing import Protocol
from fastembed import TextEmbedding


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class LocalFastEmbedder:
    """FastEmbed adapter using a pinned multilingual-capable MiniLM model."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        if model_name != "sentence-transformers/all-MiniLM-L6-v2":
            raise ValueError(f"Unsupported model {model_name!r}; choose the pinned model explicitly")
        self._model = TextEmbedding(model_name=model_name)
        self.dimensions = 384

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts, batch_size=32)]

    def embed_query(self, question: str) -> list[float]:
        return next(self._model.query_embed(question)).tolist()


MyEmbedder = LocalFastEmbedder
