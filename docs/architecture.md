# Architecture

## Guiding Principle

"Simple enough to finish, strong enough to impress, and structured well
enough to evolve toward production."

## Core System Flow

```
Incoming Event
      |
Validation
      |
Feature Engineering
      |
  +---------+---------------+---------------+
  |                         |               |
Rules              Supervised ML     Anomaly Detection
  |                         |               |
  +---------+---------------+---------------+
            |
      Risk Aggregation
            |
      Risk Score 0-100
            |
      Decision Engine
            |
 ALLOW / STEP_UP / MANUAL_REVIEW / BLOCK
            |
  Persist Evidence + Decision
            |
      Investigation Case
            |
      AI Investigation
            |
   Grounded Explanation
```

**The LLM is not the fraud decision-maker.** The fraud engine (rules +
supervised ML + anomaly detection + risk aggregation + decision engine)
makes the ALLOW/STEP_UP/MANUAL_REVIEW/BLOCK decision. The LLM only assists
investigators after the fact - explaining, summarizing, and suggesting
investigation steps grounded in evidence the fraud engine already produced.

## Component Responsibilities

### Backend (`backend/`)
Owns the HTTP API, request validation, orchestration, database access, and
(in later phases) authentication/authorization and AI service integration.
Does **not** contain ML training code.

The future real-time fraud engine lives under `backend/app/fraud/`
(feature calculation, rules, ML inference, anomaly detection, risk
aggregation, decision engine) - not implemented in this phase.

### ML (`ml/`)
Owns synthetic dataset generation, feature definitions, model training,
evaluation, and model artifacts. Training code never runs inside the
real-time API request path - the API loads an already-trained model
produced by this package.

### AI (`ai/`)
Owns the investigator-assistance layer: embeddings, pgvector retrieval,
prompt templates, guardrails, and an LLM provider abstraction (AWS
Bedrock-compatible implementation added later). Provider interfaces exist
today as abstractions with mock implementations so the rest of the system
can be built and tested against them before a real provider is wired in.

### Database (`database/`)
PostgreSQL is the primary structured data store. The `pgvector` extension
is enabled for future semantic retrieval (fraud policies, similar past
cases) used by the AI investigation layer. Alembic manages schema
migrations.

### Frontend (`frontend/`)
React + TypeScript + Vite interface for fraud analysts and administrators.
No customer-facing UI.

## Technology Stack

| Layer      | Technology |
|------------|------------|
| Frontend   | React, TypeScript, Vite, Tailwind CSS |
| Backend    | Python, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database   | PostgreSQL, pgvector |
| ML         | pandas, NumPy, scikit-learn (Logistic Regression, Isolation Forest) |
| AI         | Provider-abstracted LLM + embeddings (AWS Bedrock-compatible), pgvector retrieval, prompt templates, guardrails |
| Infra      | Docker, docker-compose (PostgreSQL + pgvector only) |
| Testing    | pytest (backend/ML) |

FastAPI is used as the equivalent of Spring Boot / an API service because
the ML layer is Python-based, keeping the fraud-scoring and API code in
one language.

## Explicit Non-Goals

Microservices, Kafka, Redis, Kubernetes, graph databases, agent
frameworks, multi-agent systems, deep learning, and any infrastructure
beyond PostgreSQL/pgvector are intentionally excluded to keep the
prototype finishable and its scope traceable to the stated requirements.

## Implementation Status

This document describes the **agreed target architecture**. See the
project README for what is actually implemented today (Phase 1:
foundation only - no fraud logic, ML training, or AI calls yet).
