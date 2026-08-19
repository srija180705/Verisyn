"""Sanity checks that the AI provider abstractions/mocks are usable.
Real provider implementations are covered in a later phase.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from ai.embeddings.provider import MockEmbeddingProvider
from ai.llm.provider import MockLLMProvider
from ai.retrieval.service import MockRetrievalService


def test_mock_llm_provider_returns_text() -> None:
    provider = MockLLMProvider(fixed_response="hello")
    assert provider.generate("any prompt") == "hello"


def test_mock_embedding_provider_returns_expected_dimensions() -> None:
    provider = MockEmbeddingProvider(dimensions=4)
    vector = provider.embed("some text")
    assert len(vector) == 4
    assert all(isinstance(value, float) for value in vector)


def test_mock_retrieval_service_returns_no_results() -> None:
    service = MockRetrievalService()
    assert service.search("query") == []
