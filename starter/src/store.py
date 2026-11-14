"""Persistent Chroma vector store with cosine search and metadata filtering."""
import os
import re
from pathlib import Path
from typing import Any
import chromadb
from .models import Chunk


class ChromaVectorStore:
    def __init__(self, path: str | Path, dimensions: int) -> None:
        self.path = str(path)
        self.dimensions = dimensions
        Path(self.path).mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
        self.client = chromadb.PersistentClient(path=self.path)

    def create_schema(self) -> None:
        """PersistentClient creates the SQLite-backed collection metadata lazily."""
        return None

    def _collection(self, strategy: str):
        name = "day6_" + re.sub(r"[^a-z0-9_]+", "_", strategy.lower())
        return self.client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine", "dimensions": self.dimensions})

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Replace a strategy snapshot, so reruns never retain stale/duplicate chunks."""
        if len(chunks) != len(vectors):
            raise ValueError("Chunk/vector count mismatch")
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(f"Expected {self.dimensions} dimensions, got {len(vector)}")
        collection = self._collection(strategy)
        old_ids = collection.get(include=[]).get("ids", [])
        for offset in range(0, len(old_ids), 500):
            collection.delete(ids=old_ids[offset:offset + 500])
        for offset in range(0, len(chunks), 500):
            batch = chunks[offset:offset + 500]
            collection.upsert(
                ids=[c.chunk_id for c in batch],
                embeddings=vectors[offset:offset + 500],
                documents=[c.text for c in batch],
                metadatas=[{"document_id": c.document_id, "source": c.source,
                            "page": c.page, **c.metadata} for c in batch],
            )

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Return nearest chunks; Chroma applies cosine metric and exact payload filters."""
        collection = self._collection(strategy)
        where = None
        if filters:
            clauses = [{key: value} for key, value in filters.items()]
            where = clauses[0] if len(clauses) == 1 else {"$and": clauses}
        result = collection.query(query_embeddings=[query_vector], n_results=top_k,
                                  where=where, include=["documents", "metadatas", "distances"])
        hits = []
        for i, chunk_id in enumerate(result["ids"][0]):
            distance = float(result["distances"][0][i])
            hits.append({"chunk_id": chunk_id, "text": result["documents"][0][i],
                         "score": 1.0 - distance, "metadata": result["metadatas"][0][i]})
        return hits
