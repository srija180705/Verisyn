"""Retrieval service abstraction.

Will back the "retrieved fraud policies" step of the AI investigation
flow (see docs/ai-design.md) with a pgvector similarity search. No
vector search is implemented yet - only the interface and a mock used
for future testing.
"""
from abc import ABC, abstractmethod


class RetrievedDocument:
    """A single retrieval result: source text plus a similarity score."""

    def __init__(self, content: str, score: float) -> None:
        self.content = content
        self.score = score


class RetrievalService(ABC):
    """Finds documents relevant to a query (e.g. fraud policies, past cases)."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RetrievedDocument]:
        """Return up to top_k documents most relevant to the query."""


class MockRetrievalService(RetrievalService):
    """Returns no results. Used in tests and local dev before pgvector
    retrieval is implemented."""

    def search(self, query: str, top_k: int = 5) -> list[RetrievedDocument]:
        return []
