"""Point-in-time fraud features computed from historical transaction/event data.

Reads existing data from PostgreSQL (loaded by ml/data/generate.py +
ml/data/load.py) - does NOT regenerate or modify any data.

Design: a small amount of mutable "state" (running per-customer /
per-device / per-ip aggregates) is threaded through pure per-transaction
feature functions. Processing transactions in chronological order and
only ever reading state built from *earlier* transactions is what makes
every feature point-in-time correct - a feature for a transaction at
time T never sees a transaction or event at or after T.

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
from functools import lru_cache
from pathlib import Path
from uuid import UUID

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.core.database import engine
from app.models import Transaction, Event

WINDOW_10M = timedelta(minutes=10)
WINDOW_1H = timedelta(hours=1)
WINDOW_30D = timedelta(days=30)

FEATURE_COLUMNS = [
    "amount",
    "amount_vs_customer_avg",
    "transactions_last_10m",
    "transactions_last_1h",
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
        # device_id / ip_identity_id -> list of (occurred_at, account_id),
        # append-only in chronological order. Kept as a full history (not
        # just a set) so accounts_per_device/accounts_per_ip can be
        # windowed to "the previous 30 days" rather than all-time.
        "device_history": defaultdict(list),
        "ip_history": defaultdict(list),
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


def _distinct_accounts_since(
    history: list[tuple[datetime, object]], now: datetime, window: timedelta
) -> int:
    """Number of distinct account_ids in a (occurred_at, account_id) history
    list within [now - window, now). `history` is sorted ascending by
    occurred_at (append-only, chronological input), so this is a bisect
    followed by a scan of just the windowed tail - not the full history.
    """
    threshold = now - window
    idx = bisect.bisect_left(history, (threshold,))
    return len({account_id for _, account_id in history[idx:]})


def compute_transaction_features(
    txn: dict,
    state: dict,
    location: str | None,
    failed_login_times: list[datetime],
) -> dict:
    """Compute point-in-time features for one transaction, then update
    `state` with this transaction so later (in time) transactions see it.

    `txn` must have: customer_id, account_id, device_id, ip_identity_id,
    amount, occurred_at. `failed_login_times` is the customer's full
    timestamp history (batch mode reads it from Postgres up front;
    real-time mode could pass a live-queried slice instead) - only entries
    strictly before `occurred_at` affect the result.
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
    accounts_per_device = (
        _distinct_accounts_since(state["device_history"][device_id], occurred_at, WINDOW_30D)
        if device_id
        else 0
    )

    is_new_ip = ip_identity_id is not None and ip_identity_id not in cust["ips_seen"]
    accounts_per_ip = (
        _distinct_accounts_since(state["ip_history"][ip_identity_id], occurred_at, WINDOW_30D)
        if ip_identity_id
        else 0
    )

    time_since_last_transaction_seconds = (
        (occurred_at - cust["last_txn_time"]).total_seconds()
        if cust["last_txn_time"] is not None
        else -1.0  # sentinel: no prior transaction for this customer yet
    )

    failed_logins_last_10m = _count_since(failed_login_times, occurred_at, WINDOW_10M)

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
        state["device_history"][device_id].append((occurred_at, account_id))
    if ip_identity_id:
        cust["ips_seen"].add(ip_identity_id)
        state["ip_history"][ip_identity_id].append((occurred_at, account_id))
    if location:
        cust["location_counts"][location] += 1

    return features


# --------------------------------------------------------------------------
# Real-time single-transaction path (Phase 7B)
#
# Neither function below replays the full transaction history - that
# approach (replay everything up to the target transaction, same state
# machinery as build_training_dataset) was tried first and worked
# correctly, but was O(all transactions) per call - far too slow for a
# live /fraud/assess request. These give the API a cheap path instead:
#
#   - already-scored historical transaction -> O(1) dict lookup in the
#     precomputed training_features.csv (get_precomputed_features)
#   - a transaction not in that CSV (a genuinely new/live one) -> scoped
#     queries for just this customer's history and this device/ip's
#     30-day window, then ONE call to the existing compute_transaction_features
#     (compute_features_for_new_transaction) - no full replay, no
#     duplicated scoring logic.
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_precomputed_features_by_id(csv_path: str) -> dict[str, dict]:
    """Load training_features.csv once per process into an in-memory
    transaction_id -> feature dict. Cached (lru_cache) so repeated lookups
    across requests don't re-read the file - the CSV only changes when
    ml/features.py's batch run is re-executed, which happens out of band.
    """
    features_by_id: dict[str, dict] = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            features_by_id[row["transaction_id"]] = {
                "amount": float(row["amount"]),
                "amount_vs_customer_avg": float(row["amount_vs_customer_avg"]),
                "transactions_last_10m": int(row["transactions_last_10m"]),
                "transactions_last_1h": int(row["transactions_last_1h"]),
                "is_new_device": row["is_new_device"] == "True",
                "accounts_per_device": int(row["accounts_per_device"]),
                "is_new_ip": row["is_new_ip"] == "True",
                "accounts_per_ip": int(row["accounts_per_ip"]),
                "time_since_last_transaction_seconds": float(
                    row["time_since_last_transaction_seconds"]
                ),
                "failed_logins_last_10m": int(row["failed_logins_last_10m"]),
                "location_anomaly": row["location_anomaly"] == "True",
            }
    return features_by_id


def get_precomputed_features(transaction_id: UUID | str) -> dict | None:
    """O(1) lookup of a transaction's features from the precomputed
    ml/data/training_features.csv. Returns None if the CSV is missing or
    the transaction isn't in it (e.g. it's newer than the last batch run) -
    callers should fall back to compute_features_for_new_transaction().
    """
    csv_path = Path(__file__).parent / "data" / "training_features.csv"
    if not csv_path.exists():
        return None
    features_by_id = _load_precomputed_features_by_id(str(csv_path))
    row = features_by_id.get(str(transaction_id))
    if row is None:
        return None
    return {"transaction_id": UUID(str(transaction_id)), **row}


def _scoped_customer_state(customer_id: UUID, before: datetime) -> dict:
    """Prior state for ONE customer, built from a customer-scoped query -
    not the full transaction table. A customer's own history is small
    (tens of rows), so this is cheap regardless of total dataset size.
    """
    cust = _new_customer_state()
    with engine.connect() as conn:
        txn_rows = conn.execute(
            select(
                Transaction.amount,
                Transaction.occurred_at,
                Transaction.device_id,
                Transaction.ip_identity_id,
            )
            .where(Transaction.customer_id == customer_id, Transaction.occurred_at < before)
            .order_by(Transaction.occurred_at.asc())
        ).all()
        location_rows = conn.execute(
            select(Event.payload)
            .where(
                Event.customer_id == customer_id,
                Event.transaction_id.is_not(None),
                Event.payload.is_not(None),
                Event.occurred_at < before,
            )
            .order_by(Event.occurred_at.asc())
        ).all()

    for amount, occurred_at, device_id, ip_identity_id in txn_rows:
        cust["amount_sum"] += float(amount)
        cust["amount_count"] += 1
        cust["txn_times"].append(occurred_at)
        cust["last_txn_time"] = occurred_at
        if device_id:
            cust["devices_seen"].add(device_id)
        if ip_identity_id:
            cust["ips_seen"].add(ip_identity_id)

    for (payload,) in location_rows:
        if payload and "location" in payload:
            cust["location_counts"][payload["location"]] += 1

    return cust


def _scoped_relation_history(
    column, value, before: datetime
) -> list[tuple[datetime, UUID]]:
    """(occurred_at, account_id) pairs for ONE device_id/ip_identity_id
    within the WINDOW_30D before `before` - a bounded, indexable query
    (Transaction has indexes on device_id/ip_identity_id/occurred_at), not
    a scan of the whole transactions table.
    """
    if value is None:
        return []
    window_start = before - WINDOW_30D
    with engine.connect() as conn:
        rows = conn.execute(
            select(Transaction.occurred_at, Transaction.account_id)
            .where(
                column == value,
                Transaction.occurred_at >= window_start,
                Transaction.occurred_at < before,
            )
            .order_by(Transaction.occurred_at.asc())
        ).all()
    return [(row.occurred_at, row.account_id) for row in rows]


def compute_features_for_new_transaction(txn: dict) -> dict:
    """Point-in-time features for a transaction that is NOT (yet) in the
    precomputed training_features.csv, using only the relevant scoped
    prior history - this customer's own transactions, plus this device's
    and this IP's 30-day windows - instead of replaying all transactions.

    `txn` must have: id, customer_id, account_id, device_id,
    ip_identity_id, amount, occurred_at (same shape as load_transactions()
    rows). Reuses compute_transaction_features() so the scoring logic
    itself is identical to the batch path - only how the prior state is
    gathered differs.
    """
    customer_id = txn["customer_id"]
    occurred_at = txn["occurred_at"]
    device_id = txn["device_id"]
    ip_identity_id = txn["ip_identity_id"]

    state = new_feature_state()
    state["customers"][customer_id] = _scoped_customer_state(customer_id, occurred_at)
    if device_id:
        state["device_history"][device_id] = _scoped_relation_history(
            Transaction.device_id, device_id, occurred_at
        )
    if ip_identity_id:
        state["ip_history"][ip_identity_id] = _scoped_relation_history(
            Transaction.ip_identity_id, ip_identity_id, occurred_at
        )

    with engine.connect() as conn:
        failed_login_rows = conn.execute(
            select(Event.occurred_at)
            .where(
                Event.customer_id == customer_id,
                Event.event_type == "login.failed",
                Event.occurred_at < occurred_at,
            )
            .order_by(Event.occurred_at.asc())
        ).all()
    failed_login_times = [row[0] for row in failed_login_rows]

    # A brand-new transaction has no linked event yet at assessment time
    # (the event would be created after/alongside it in a real system).
    location = None

    features = compute_transaction_features(txn, state, location, failed_login_times)
    return {"transaction_id": txn["id"], **features}


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
