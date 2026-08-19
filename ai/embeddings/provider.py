"""Embedding provider abstraction.

Used by the retrieval layer (a later phase) to convert text into vectors
stored in / queried against pgvector. Kept separate from the LLM provider
since embedding and generation are often different models or services.
"""
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Converts text into a fixed-size numeric vector."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for the given text."""


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic stand-in for a real embedding model, used in tests."""

    def __init__(self, dimensions: int = 8) -> None:
        self._dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        # Deterministic pseudo-embedding derived from text length/content,
        # sufficient for exercising retrieval plumbing without a real model.
        seed = sum(ord(char) for char in text) or 1
        return [((seed * (i + 1)) % 97) / 97 for i in range(self._dimensions)]
