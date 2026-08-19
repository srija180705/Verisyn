"""LLM provider abstraction.

The investigation service (a later phase) will depend on this interface,
not on a specific vendor. This keeps the AWS Bedrock implementation
swappable and testable.

The LLM assists investigators - it explains and summarizes evidence that
the fraud engine already produced. It never computes or changes a risk
score or a decision; that is enforced by what callers pass in and read
out of this interface, not by anything in this file.
"""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Generates text completions from a prompt."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return a completion for the given prompt."""


class MockLLMProvider(LLMProvider):
    """Deterministic stand-in for a real LLM, used in tests and local dev."""

    def __init__(self, fixed_response: str = "Mock LLM response.") -> None:
        self._fixed_response = fixed_response

    def generate(self, prompt: str) -> str:
        return self._fixed_response
