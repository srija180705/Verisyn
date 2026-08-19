# Fraud Intelligence Platform

Real-time AI-assisted fraud detection and prevention platform for a
digital lending ecosystem.

## Problem Being Solved

Digital lending platforms face increasingly sophisticated and evolving
fraud patterns that static, rule-only systems struggle to catch. This
platform combines rule-based checks, supervised ML, and anomaly detection
to score incoming events in real time, routes suspicious activity to
fraud analysts through a decision engine (ALLOW / STEP_UP / MANUAL_REVIEW
/ BLOCK), and gives analysts an AI-assisted, evidence-grounded explanation
during investigation.

The system is an **internal Fraud Operations and Investigation Platform**
for fraud analysts and administrators. There is no customer-facing UI in
this prototype.

Full requirements: [docs/requirements.md](./docs/requirements.md)

## High-Level Architecture

```
Incoming Event -> Validation -> Feature Engineering
   -> [Rules | Supervised ML | Anomaly Detection]
   -> Risk Aggregation -> Risk Score (0-100) -> Decision Engine
   -> ALLOW / STEP_UP / MANUAL_REVIEW / BLOCK
   -> Persist Evidence + Decision -> Investigation Case
   -> AI Investigation -> Grounded Explanation
```

The LLM never computes or changes the fraud score/decision - it only
explains evidence the fraud engine already produced. Full details:
[docs/architecture.md](./docs/architecture.md).

## Technology Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic
- **Database:** PostgreSQL, pgvector
- **ML:** pandas, NumPy, scikit-learn (Logistic Regression, Isolation Forest)
- **AI:** Provider-abstracted LLM + embeddings (AWS Bedrock-compatible), pgvector retrieval, prompt templates, guardrails
- **Infra:** Docker / docker-compose (PostgreSQL + pgvector)
- **Testing:** pytest

## Repository Structure

```
fraud-intelligence-platform/
├── frontend/          React + TypeScript + Vite UI
├── backend/           FastAPI application (API, orchestration, DB access)
│   └── app/
│       ├── api/       Versioned route definitions
│       ├── core/      Config, logging, database, error handling
│       ├── fraud/      Real-time fraud engine (later phase)
│       ├── models/    SQLAlchemy ORM models (later phase)
│       ├── repositories/  Data access layer (later phase)
│       ├── schemas/   Pydantic request/response schemas (later phase)
│       └── services/  Orchestration services (later phase)
├── ml/                Synthetic data, feature defs, training, evaluation (later phase)
├── ai/                LLM/embedding/retrieval provider abstractions + mocks
├── database/           Alembic config, migrations, pgvector init script
├── docs/              Architecture, requirements, and design documentation
├── tests/             Cross-cutting tests (currently: AI abstraction sanity checks)
├── .env.example
├── docker-compose.yml
└── README.md
```

## Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Docker Desktop (for PostgreSQL + pgvector)

## Environment Setup

```bash
cp .env.example .env
```

`.env` is git-ignored; never commit real credentials. AWS/Bedrock values
are placeholders only - nothing in this codebase calls AWS yet.

## How to Start PostgreSQL

```bash
docker compose up -d
```

This starts a `pgvector/pgvector:pg16` PostgreSQL instance on port 5432
with the `vector` extension enabled automatically
(`database/init/01-enable-pgvector.sql`). No business tables are created
yet.

## How to Start the Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate        # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Verify it's running:

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok"}
```

## How to Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`). Note: on
some Windows/Node setups Vite's dev server binds to the IPv6 loopback
address - use `http://localhost:5173`, not `http://127.0.0.1:5173`.

## How to Run Tests

Backend:

```bash
cd backend
python -m pytest -q
```

AI abstraction sanity checks (repo root):

```bash
backend/.venv/Scripts/python.exe -m pytest tests/ -q
```

## Current Implementation Status

This is **Phase 1: Project Foundation** only.

**Implemented:**
- Repository structure for all layers (frontend, backend, ml, ai, database, docs).
- Runnable FastAPI backend with `/api/v1` routing, `GET /api/v1/health`,
  environment-based config, structured logging, centralized error
  handling, and CORS for local dev.
- SQLAlchemy + Alembic database foundation (connection, session
  management, connectivity check) - no business tables.
- Docker Compose for PostgreSQL + pgvector, with the `vector` extension
  enabled.
- React + TypeScript + Vite frontend with routing, a shared layout, an
  API client foundation, and placeholder pages for Dashboard,
  Transactions, Investigations, Analytics, and Rules.
- `ml/` package structure only - no data generation, training, or
  features implemented.
- `ai/` provider abstractions (`LLMProvider`, `EmbeddingProvider`,
  `RetrievalService`) with mock implementations for future testing - no
  real Bedrock calls, RAG, or vector search implemented.
- Documentation (`docs/`) capturing the agreed architecture and design.
- `.env.example`, `.gitignore`, no hardcoded secrets.

**Explicitly NOT implemented yet (later phases):**
- Business database schema and migrations.
- Synthetic data generation, feature engineering, ML training.
- Fraud rules, anomaly detection, risk aggregation, decision engine.
- Authentication / authorization.
- RAG, pgvector retrieval, AWS Bedrock calls.
- Dashboard/analytics functionality (pages are placeholders).
- Deployment.
