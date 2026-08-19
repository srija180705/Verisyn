"""Point-in-time fraud features computed from historical transaction/event data.

Reads existing data from PostgreSQL (loaded by ml/data/generate.py +
ml/data/load.py) - does NOT regenerate or modify any data.

Design: a small amount of mutable "state" (running per-customer /
per-device / per-ip aggregates) is threaded through pure per-transaction
feature functions. Processing transactions in chronological order and
only ever reading state built from *earlier* transactions is what makes
every feature point-in-time correct - a feature for a transaction at
time T never sees a transaction, event, or application at or after T.

The same `new_feature_state()` / `compute_transaction_features()` pair
works for:
  1. Batch training data generation (this file's `build_training_dataset`)
  2. Future real-time assessment (call compute_transaction_features once
     per incoming transaction, keeping `state` in memory between calls)

Ground-truth fraud labels are attached ONLY as an output column when
building the training dataset - they are never read by any feature
calculation, avoiding target leakage.
"""
import bisect
import csv
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.database import engine  # noqa: E402
from app.models import Transaction, Event, LoanApplication  # noqa: E402

WINDOW_10M = timedelta(minutes=10)
WINDOW_1H = timedelta(hours=1)

FEATURE_COLUMNS = [
    "amount",
    "amount_vs_customer_avg",
    "transactions_last_10m",
    "transactions_last_1h",
    "applications_last_10m",
    "is_new_device",
    "accounts_per_device",
    "is_new_ip",
    "accounts_per_ip",
    "time_since_last_transaction_seconds",
    "failed_logins_last_10m",
    "location_anomaly",
]


# --------------------------------------------------------------------------
# Data loading (read-only queries against the existing schema)
# --------------------------------------------------------------------------

def load_transactions() -> list[dict]:
    """All transactions, sorted ascending by occurred_at (required for
    point-in-time processing)."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                Transaction.id,
                Transaction.customer_id,
                Transaction.account_id,
                Transaction.device_id,
                Transaction.ip_identity_id,
                Transaction.amount,
                Transaction.occurred_at,
            ).order_by(Transaction.occurred_at.asc())
        ).all()
    return [dict(row._mapping) for row in rows]


def load_transaction_locations() -> dict[UUID, str]:
    """transaction_id -> location, from the linked event's payload (if any)."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(Event.transaction_id, Event.payload).where(
                Event.transaction_id.is_not(None), Event.payload.is_not(None)
            )
        ).all()
    locations: dict[UUID, str] = {}
    for txn_id, payload in rows:
        if txn_id not in locations and payload and "location" in payload:
            locations[txn_id] = payload["location"]
    return locations


def load_failed_login_times() -> dict[UUID, list[datetime]]:
    """customer_id -> sorted list of login.failed occurred_at timestamps."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(Event.customer_id, Event.occurred_at)
            .where(Event.event_type == "login.failed", Event.customer_id.is_not(None))
            .order_by(Event.customer_id, Event.occurred_at.asc())
        ).all()
    by_customer: dict[UUID, list[datetime]] = defaultdict(list)
    for customer_id, occurred_at in rows:
        by_customer[customer_id].append(occurred_at)
    return by_customer


def load_application_times() -> dict[UUID, list[datetime]]:
    """customer_id -> sorted list of loan application submitted_at timestamps."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(LoanApplication.customer_id, LoanApplication.submitted_at).order_by(
                LoanApplication.customer_id, LoanApplication.submitted_at.asc()
            )
        ).all()
    by_customer: dict[UUID, list[datetime]] = defaultdict(list)
    for customer_id, submitted_at in rows:
        by_customer[customer_id].append(submitted_at)
    return by_customer


def load_labels(csv_path: Path) -> dict[str, int]:
    """transaction_id (str) -> is_suspicious, from the Phase 2B ML-only CSV.

    Only used to attach fraud_label as an OUTPUT column - never fed into
    feature calculations.
    """
    labels: dict[str, int] = {}
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            labels[row["transaction_id"]] = int(row["is_suspicious"])
    return labels


# --------------------------------------------------------------------------
# Point-in-time feature state and computation
# --------------------------------------------------------------------------

def new_feature_state() -> dict:
    """A fresh, empty state to fold transactions into (batch start, or the
    beginning of a real-time session)."""
    return {
        "customers": {},  # customer_id -> per-customer running aggregates
        "device_accounts": defaultdict(set),  # device_id -> set(account_id)
        "ip_accounts": defaultdict(set),  # ip_identity_id -> set(account_id)
    }


def _new_customer_state() -> dict:
    return {
        "amount_sum": 0.0,
        "amount_count": 0,
        "txn_times": [],  # sorted ascending (append-only, chronological input)
        "last_txn_time": None,
        "devices_seen": set(),
        "ips_seen": set(),
        "location_counts": Counter(),
    }


def _count_since(times: list[datetime], now: datetime, window: timedelta) -> int:
    """Number of entries in a sorted list within [now - window, now)."""
    threshold = now - window
    idx = bisect.bisect_left(times, threshold)
    return len(times) - idx


def compute_transaction_features(
    txn: dict,
    state: dict,
    location: str | None,
    failed_login_times: list[datetime],
    application_times: list[datetime],
) -> dict:
    """Compute point-in-time features for one transaction, then update
    `state` with this transaction so later (in time) transactions see it.

    `txn` must have: customer_id, account_id, device_id, ip_identity_id,
    amount, occurred_at. `failed_login_times` / `application_times` are the
    customer's full timestamp history (batch mode reads them from Postgres
    up front; real-time mode could pass a live-queried slice instead) -
    only entries strictly before `occurred_at` affect the result.
    """
    customer_id = txn["customer_id"]
    occurred_at = txn["occurred_at"]
    amount = float(txn["amount"])
    device_id = txn["device_id"]
    ip_identity_id = txn["ip_identity_id"]
    account_id = txn["account_id"]

    cust = state["customers"].setdefault(customer_id, _new_customer_state())

    amount_vs_customer_avg = (
        amount / (cust["amount_sum"] / cust["amount_count"])
        if cust["amount_count"] > 0
        else 1.0
    )

    transactions_last_10m = _count_since(cust["txn_times"], occurred_at, WINDOW_10M)
    transactions_last_1h = _count_since(cust["txn_times"], occurred_at, WINDOW_1H)

    is_new_device = device_id is not None and device_id not in cust["devices_seen"]
    accounts_per_device = len(state["device_accounts"][device_id]) if device_id else 0

    is_new_ip = ip_identity_id is not None and ip_identity_id not in cust["ips_seen"]
    accounts_per_ip = len(state["ip_accounts"][ip_identity_id]) if ip_identity_id else 0

    time_since_last_transaction_seconds = (
        (occurred_at - cust["last_txn_time"]).total_seconds()
        if cust["last_txn_time"] is not None
        else -1.0  # sentinel: no prior transaction for this customer yet
    )

    failed_logins_last_10m = _count_since(failed_login_times, occurred_at, WINDOW_10M)
    applications_last_10m = _count_since(application_times, occurred_at, WINDOW_10M)

    usual_location = (
        cust["location_counts"].most_common(1)[0][0]
        if cust["location_counts"]
        else None
    )
    location_anomaly = bool(location and usual_location and location != usual_location)

    features = {
        "amount": amount,
        "amount_vs_customer_avg": round(amount_vs_customer_avg, 4),
        "transactions_last_10m": transactions_last_10m,
        "transactions_last_1h": transactions_last_1h,
        "applications_last_10m": applications_last_10m,
        "is_new_device": is_new_device,
        "accounts_per_device": accounts_per_device,
        "is_new_ip": is_new_ip,
        "accounts_per_ip": accounts_per_ip,
        "time_since_last_transaction_seconds": time_since_last_transaction_seconds,
        "failed_logins_last_10m": failed_logins_last_10m,
        "location_anomaly": location_anomaly,
    }

    # Update state AFTER computing features so this transaction only ever
    # affects transactions that come after it.
    cust["amount_sum"] += amount
    cust["amount_count"] += 1
    cust["txn_times"].append(occurred_at)
    cust["last_txn_time"] = occurred_at
    if device_id:
        cust["devices_seen"].add(device_id)
        state["device_accounts"][device_id].add(account_id)
    if ip_identity_id:
        cust["ips_seen"].add(ip_identity_id)
        state["ip_accounts"][ip_identity_id].add(account_id)
    if location:
        cust["location_counts"][location] += 1

    return features


# --------------------------------------------------------------------------
# Batch training dataset
# --------------------------------------------------------------------------

def build_training_dataset(labels_csv_path: Path | None = None) -> list[dict]:
    """Compute point-in-time features for every transaction in Postgres,
    attaching fraud_label (if a labels CSV is available) as an output-only
    column. Returns a list of row dicts: transaction_id, features..., and
    fraud_label when labels are available.
    """
    transactions = load_transactions()
    locations = load_transaction_locations()
    failed_logins_by_customer = load_failed_login_times()
    applications_by_customer = load_application_times()

    labels: dict[str, int] = {}
    if labels_csv_path and labels_csv_path.exists():
        labels = load_labels(labels_csv_path)

    state = new_feature_state()
    rows = []
    for txn in transactions:
        customer_id = txn["customer_id"]
        features = compute_transaction_features(
            txn,
            state,
            locations.get(txn["id"]),
            failed_logins_by_customer.get(customer_id, []),
            applications_by_customer.get(customer_id, []),
        )
        row = {"transaction_id": txn["id"], **features}
        if labels:
            row["fraud_label"] = labels.get(str(txn["id"]), 0)
        rows.append(row)
    return rows


def write_features_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["transaction_id", *FEATURE_COLUMNS]
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# --------------------------------------------------------------------------
# Inspection / manual validation
# --------------------------------------------------------------------------

def _print_inspection(rows: list[dict]) -> None:
    print(f"rows: {len(rows)}")
    print(f"feature columns: {FEATURE_COLUMNS}")

    print("\nsample rows:")
    for row in rows[:3]:
        print(f"  {row}")

    print("\nbasic statistics:")
    numeric_cols = [
        "amount",
        "amount_vs_customer_avg",
        "transactions_last_10m",
        "transactions_last_1h",
        "applications_last_10m",
        "accounts_per_device",
        "accounts_per_ip",
        "time_since_last_transaction_seconds",
        "failed_logins_last_10m",
    ]
    for col in numeric_cols:
        values = [row[col] for row in rows]
        print(
            f"  {col}: min={min(values):.2f} max={max(values):.2f} "
            f"mean={statistics.mean(values):.2f}"
        )

    for col in ["is_new_device", "is_new_ip", "location_anomaly"]:
        true_count = sum(1 for row in rows if row[col])
        print(f"  {col}: {true_count}/{len(rows)} true")

    if rows and "fraud_label" in rows[0]:
        fraud_count = sum(row["fraud_label"] for row in rows)
        print(f"\nfraud_label distribution: {fraud_count}/{len(rows)} suspicious")


def main() -> None:
    labels_path = Path(__file__).parent / "data" / "training_labels.csv"
    print("Building point-in-time features from PostgreSQL...")
    rows = build_training_dataset(labels_csv_path=labels_path)

    output_path = Path(__file__).parent / "data" / "training_features.csv"
    write_features_csv(rows, output_path)
    print(f"Wrote {len(rows)} feature rows to {output_path}\n")

    _print_inspection(rows)


if __name__ == "__main__":
    main()
