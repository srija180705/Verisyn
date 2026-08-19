"""Loads a GeneratedDataset into PostgreSQL using the existing SQLAlchemy
engine/models from the backend app - no new database tooling.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import insert  # noqa: E402

from app.core.database import engine  # noqa: E402
from app.models import (  # noqa: E402
    Customer,
    Device,
    IPIdentity,
    Account,
    LoanApplication,
    Transaction,
    Event,
)

BATCH_SIZE = 2000


def _bulk_insert(connection, table, rows: list[dict]) -> None:
    if not rows:
        return
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        connection.execute(insert(table), batch)


def load_into_database(dataset) -> None:
    """Insert all entities from a GeneratedDataset, respecting FK order."""
    with engine.begin() as connection:
        _bulk_insert(connection, Customer.__table__, dataset.customers)
        _bulk_insert(connection, Device.__table__, dataset.devices)
        _bulk_insert(connection, IPIdentity.__table__, dataset.ip_identities)
        _bulk_insert(connection, Account.__table__, dataset.accounts)
        _bulk_insert(connection, LoanApplication.__table__, dataset.loan_applications)
        _bulk_insert(connection, Transaction.__table__, dataset.transactions)
        _bulk_insert(connection, Event.__table__, dataset.events)


if __name__ == "__main__":
    # Convenience: `python ml/data/load.py` regenerates with defaults and loads.
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from ml.data.generate import GenerationConfig, generate_dataset

    dataset = generate_dataset(GenerationConfig())
    load_into_database(dataset)
    print("Load complete.")