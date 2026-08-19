# API Contract

## Status

Only the health endpoint is implemented today. All other routes below are
the **agreed target API surface** for later phases.

## Base Path

All business endpoints are versioned under `/api/v1`.

## Implemented

| Method | Path                  | Description                     |
|--------|-----------------------|----------------------------------|
| GET    | `/api/v1/health`      | Liveness check. Returns `{"status": "ok"}`. |

## Planned (not implemented)

| Method | Path                                | Description |
|--------|-------------------------------------|-------------|
| POST   | `/api/v1/auth/login`                | Analyst/admin authentication. |
| POST   | `/api/v1/events`                    | Ingest an incoming transaction/application event. |
| POST   | `/api/v1/fraud/assess`              | Run the fraud engine against an event and return a risk assessment. |
| GET    | `/api/v1/transactions/{id}`         | Retrieve a transaction and its details. |
| GET    | `/api/v1/assessments/{id}`          | Retrieve a fraud assessment (score, decision, evidence). |
| GET    | `/api/v1/cases`                     | List investigation cases. |
| GET    | `/api/v1/cases/{id}`                | Retrieve an investigation case. |
| POST   | `/api/v1/cases/{id}/resolve`        | Resolve an investigation case. |
| POST   | `/api/v1/ai/investigate`            | Request an AI-grounded explanation for a case. |
| GET    | `/api/v1/analytics/overview`        | Aggregate fraud/model performance metrics. |
| GET    | `/api/v1/rules`                     | List configured fraud rules/policies. |
| GET    | `/api/v1/models/active`             | Retrieve metadata on the currently active ML model version. |

Request/response schemas for these endpoints will be defined with Pydantic
models under `backend/app/schemas/` when each endpoint is implemented.
