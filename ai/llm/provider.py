"""LLM provider abstraction.

The investigation service depends on this interface, not on a specific
vendor - GroqLLMProvider below could be swapped for a Bedrock (or other)
implementation without touching any calling code.

The LLM assists investigators - it explains and summarizes evidence that
the fraud engine already produced. It never computes or changes a risk
score or a decision; that is enforced by what callers pass in and read
out of this interface, not by anything in this file.
"""
from abc import ABC, abstractmethod

import httpx


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


class GroqLLMProvider(LLMProvider):
    """Calls Groq's OpenAI-compatible chat completions API.

    Chosen over AWS Bedrock for this prototype: no AWS account/IAM/model-
    access setup required, just an API key. A single REST call via httpx
    (already a project dependency) - no new SDK needed.
    """

    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    # Groq's model catalog changes over time (older Llama model names have
    # since been retired) - verified live against /v1/models as of writing
    # this. Override via GROQ_MODEL if this one is retired too.
    DEFAULT_MODEL = "openai/gpt-oss-20b"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str) -> str:
        response = httpx.post(
            self.API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 300,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


class BedrockLLMProvider(LLMProvider):
    """Calls AWS Bedrock's Converse API - the modern, model-agnostic text
    generation call (same shape across Anthropic/Titan/Llama models on
    Bedrock, no per-model request-body format to hand-build).

    Credentials are never read or passed by this class - boto3's own
    default credential chain (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY env
    vars, ~/.aws/credentials, IAM role, etc.) resolves them. Only a region
    and a model id are needed here.

    boto3 is imported lazily inside generate() so this module stays
    importable (Mock/Groq providers keep working) even in an environment
    where boto3 isn't installed and Bedrock is simply never selected.
    """

    def __init__(self, region: str, model_id: str) -> None:
        self._region = region
        self._model_id = model_id

    def generate(self, prompt: str) -> str:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=self._region or None)
        response = client.converse(
            modelId=self._model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 300, "temperature": 0.2},
        )
        return response["output"]["message"]["content"][0]["text"].strip()
