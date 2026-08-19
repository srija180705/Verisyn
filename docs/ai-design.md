# AI Design

## Status

No LLM calls, retrieval, or RAG are implemented yet. Only provider
abstractions and mock implementations exist today (`ai/llm/provider.py`,
`ai/embeddings/provider.py`, `ai/retrieval/service.py`).

## Role of the LLM

The LLM is an **investigator assistant**, not a decision-maker. The fraud
engine (rules + supervised ML + anomaly detection + risk aggregation +
decision engine) is solely responsible for the risk score and the
ALLOW/STEP_UP/MANUAL_REVIEW/BLOCK decision.

**The LLM may:**
- Explain a fraud decision in plain language.
- Summarize an investigation.
- Suggest investigation steps based on the evidence provided to it.

**The LLM must not:**
- Calculate the fraud score.
- Change the fraud score.
- Change the decision.
- Invent evidence.
- Invent policies.
- Make autonomous financial decisions.

These constraints will be enforced by guardrails (`ai/guardrails/`) around
the investigation service in a later phase - the LLM is only ever given
evidence the fraud engine already produced and is never allowed to write
back to the score or decision.

## Target Investigation Flow

```
Fraud Evidence
      +
Risk Signals
      +
Triggered Rules
      +
Retrieved Fraud Policies
      +
Analyst Question
      |
Context Builder
      |
     LLM
      |
Grounded Investigation Explanation
```

"Retrieved Fraud Policies" comes from a pgvector similarity search over
policy documents (and potentially past cases), via the retrieval service
abstraction.

## Provider Abstractions (implemented in this phase)

- `LLMProvider` (`ai/llm/provider.py`) - `generate(prompt) -> str`.
  `MockLLMProvider` returns a fixed response for local dev/tests.
- `EmbeddingProvider` (`ai/embeddings/provider.py`) - `embed(text) -> list[float]`.
  `MockEmbeddingProvider` returns a deterministic pseudo-embedding.
- `RetrievalService` (`ai/retrieval/service.py`) - `search(query, top_k) -> list[RetrievedDocument]`.
  `MockRetrievalService` returns no results.

These interfaces let the future investigation service (`backend/app/services/`)
be built and tested against mocks before an AWS Bedrock-backed
implementation is wired in.

## Explicitly Out of Scope (this phase and near-term)

- Actual AWS Bedrock calls.
- RAG implementation.
- pgvector-backed vector search.
- Autonomous agents or multi-agent frameworks.
