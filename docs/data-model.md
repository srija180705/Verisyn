# Data Model

## Status

No business schema is implemented yet. This document records the **agreed
target entities** for later phases; only database infrastructure
(connection, SQLAlchemy/Alembic foundation, pgvector extension) exists
today.

## Target Entities

- `customers`
- `accounts`
- `devices`
- `ip_identities`
- `loan_applications`
- `transactions`
- `events`
- `fraud_assessments`
- `risk_signals`
- `fraud_rules`
- `investigation_cases`
- `model_versions`
- `audit_logs`
- `fraud_policies`

Relationships, columns, and constraints for these entities will be defined
when the business schema is implemented in a controlled follow-up phase,
via Alembic migrations under `database/migrations/`.

## Vector Data

`fraud_policies` (and potentially `investigation_cases`) are expected to
carry a `pgvector` embedding column so the AI investigation layer can
retrieve semantically similar policies/past cases. The `vector` extension
is already enabled in the local database (see
`database/init/01-enable-pgvector.sql`); no vector columns exist yet.
