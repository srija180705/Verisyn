"""Deterministic fraud rule engine - independent of Logistic Regression and
Isolation Forest.

Evaluates the same point-in-time features already produced by
ml/features.py (ml/data/training_features.csv). Rules read feature values
only - never fraud_label - and never require data from after the
transaction being evaluated (the features themselves are already
point-in-time correct, see ml/features.py).

This file only produces triggered_rules / rule_count / rule_score. It does
NOT combine with the ML models, does NOT produce a final risk score or
decision - that is a later phase.

Usage:
    python ml/rules.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from ml.model import TARGET_COLUMN, load_training_data  # noqa: E402

# --------------------------------------------------------------------------
# Thresholds (named constants so they're easy to tune)
# --------------------------------------------------------------------------
HIGH_TRANSACTION_VELOCITY_THRESHOLD = 5
EXTREME_TRANSACTION_VELOCITY_THRESHOLD = 10
LARGE_AMOUNT_THRESHOLD = 5
NEW_DEVICE_LARGE_AMOUNT_THRESHOLD = 3
NEW_IP_LARGE_AMOUNT_THRESHOLD = 3
DEVICE_ACCOUNT_SHARING_THRESHOLD = 5
IP_ACCOUNT_SHARING_THRESHOLD = 5
FAILED_LOGIN_BURST_THRESHOLD = 3

# --------------------------------------------------------------------------
# Rule weights (added together, capped at 100)
# --------------------------------------------------------------------------
RULE_WEIGHTS = {
    "HIGH_TRANSACTION_VELOCITY": 20,
    "EXTREME_TRANSACTION_VELOCITY": 30,
    "LARGE_AMOUNT": 15,
    "NEW_DEVICE_LARGE_AMOUNT": 20,
    "NEW_IP_LARGE_AMOUNT": 15,
    "DEVICE_ACCOUNT_SHARING": 10,
    "IP_ACCOUNT_SHARING": 10,
    "FAILED_LOGIN_BURST": 15,
    "LOCATION_ANOMALY": 10,
}
MAX_RULE_SCORE = 100


def _triggered_rules(row: pd.Series) -> list[str]:
    """Which rules fire for one feature row. Reads feature values only."""
    triggered = []

    if row["transactions_last_10m"] >= HIGH_TRANSACTION_VELOCITY_THRESHOLD:
        triggered.append("HIGH_TRANSACTION_VELOCITY")
    if row["transactions_last_10m"] >= EXTREME_TRANSACTION_VELOCITY_THRESHOLD:
        triggered.append("EXTREME_TRANSACTION_VELOCITY")
    if row["amount_vs_customer_avg"] >= LARGE_AMOUNT_THRESHOLD:
        triggered.append("LARGE_AMOUNT")
    if row["is_new_device"] and row["amount_vs_customer_avg"] >= NEW_DEVICE_LARGE_AMOUNT_THRESHOLD:
        triggered.append("NEW_DEVICE_LARGE_AMOUNT")
    if row["is_new_ip"] and row["amount_vs_customer_avg"] >= NEW_IP_LARGE_AMOUNT_THRESHOLD:
        triggered.append("NEW_IP_LARGE_AMOUNT")
    if row["accounts_per_device"] >= DEVICE_ACCOUNT_SHARING_THRESHOLD:
        triggered.append("DEVICE_ACCOUNT_SHARING")
    if row["accounts_per_ip"] >= IP_ACCOUNT_SHARING_THRESHOLD:
        triggered.append("IP_ACCOUNT_SHARING")
    if row["failed_logins_last_10m"] >= FAILED_LOGIN_BURST_THRESHOLD:
        triggered.append("FAILED_LOGIN_BURST")
    if row["location_anomaly"]:
        triggered.append("LOCATION_ANOMALY")

    return triggered


def evaluate_transaction(row: pd.Series) -> dict:
    """Evaluate all rules for one transaction's feature row.

    Returns {transaction_id, triggered_rules, rule_count, rule_score}.
    Deterministic and simple: rule_score is the sum of triggered rules'
    weights, capped at MAX_RULE_SCORE.
    """
    triggered = _triggered_rules(row)
    rule_score = min(sum(RULE_WEIGHTS[name] for name in triggered), MAX_RULE_SCORE)
    return {
        "transaction_id": row["transaction_id"],
        "triggered_rules": triggered,
        "rule_count": len(triggered),
        "rule_score": rule_score,
    }


def evaluate_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Evaluate rules for every row in a features DataFrame. No fraud_label
    is read here - only feature columns."""
    results = [evaluate_transaction(row) for _, row in df.iterrows()]
    return pd.DataFrame(results)


def _print_report(df: pd.DataFrame, results: pd.DataFrame) -> None:
    total = len(results)
    print("=" * 60)
    print("FRAUD RULES - EVALUATION")
    print("=" * 60)
    print(f"total transactions evaluated: {total}")

    print("\nrule trigger rates:")
    for name in RULE_WEIGHTS:
        count = sum(1 for rules in results["triggered_rules"] if name in rules)
        print(f"  {name:<32} {count:>6} ({100 * count / total:.2f}%)")

    print(f"\naverage rule_score: {results['rule_score'].mean():.2f}")
    nonzero = (results["rule_score"] > 0).sum()
    print(f"transactions with rule_score > 0: {nonzero} ({100 * nonzero / total:.2f}%)")

    print("\n" + "=" * 60)
    print("TOP 10 HIGHEST rule_score EXAMPLES")
    print("=" * 60)
    top = results.sort_values("rule_score", ascending=False).head(10)
    for _, row in top.iterrows():
        print(
            f"  transaction_id={row['transaction_id']}  "
            f"rule_score={row['rule_score']}  "
            f"rules={row['triggered_rules']}"
        )

    if TARGET_COLUMN in df.columns:
        merged = results.merge(
            df[["transaction_id", TARGET_COLUMN]], on="transaction_id"
        )
        flagged = merged[merged["rule_score"] > 0]
        fraud_rate_flagged = flagged[TARGET_COLUMN].mean() if len(flagged) else 0.0
        overall_fraud_rate = merged[TARGET_COLUMN].mean()
        print("\n" + "=" * 60)
        print("FRAUD RATE COMPARISON (fraud_label used only for this report,")
        print("never by the rule logic above)")
        print("=" * 60)
        print(f"overall fraud rate:                     {100 * overall_fraud_rate:.2f}%")
        print(
            f"fraud rate among rule_score > 0 rows:   {100 * fraud_rate_flagged:.2f}% "
            f"({len(flagged)} rows)"
        )


def main() -> None:
    print("Loading features (existing CSV, not regenerated)...")
    df = load_training_data()

    results = evaluate_dataset(df)
    _print_report(df, results)


if __name__ == "__main__":
    main()
