"""Risk aggregation + decision - combines the three existing, independent
signals (Logistic Regression, Isolation Forest, rule engine) into one
final_risk_score, risk_level, and decision. Does not modify or retrain
any of them differently than their own scripts already do.

fraud_label is never read by the scoring logic below - it is only
attached afterward, for the evaluation section, exactly like every prior
phase in this project.

Evaluated on the same chronological 80/20 test split used throughout
(ml/model.py's temporal_train_test_split) rather than the full CSV, so the
reported fraud rates reflect out-of-sample performance, consistent with
every earlier phase's evaluation methodology.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

sys.path.append(str(Path(__file__).resolve().parents[1]))

from ml.model import (  # noqa: E402
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    load_training_data,
    temporal_train_test_split,
    train_model,
)
from ml.anomaly import compute_anomaly_scores, train_anomaly_model  # noqa: E402
from ml.rules import evaluate_dataset as evaluate_rules  # noqa: E402

# --------------------------------------------------------------------------
# Signal weights (must sum to 1.0 / 100%)
# --------------------------------------------------------------------------
ML_WEIGHT = 0.70
ANOMALY_WEIGHT = 0.20
RULE_WEIGHT = 0.10

# --------------------------------------------------------------------------
# Risk level thresholds (inclusive upper bounds), named so they're easy to tune
# --------------------------------------------------------------------------
LOW_MAX = 29
MODERATE_MAX = 59
HIGH_MAX = 79
# CRITICAL is anything above HIGH_MAX, up to 100

DECISION_BY_RISK_LEVEL = {
    "LOW": "ALLOW",
    "MODERATE": "STEP_UP",
    "HIGH": "MANUAL_REVIEW",
    "CRITICAL": "BLOCK",
}


def risk_level_for_score(score: float) -> str:
    if score <= LOW_MAX:
        return "LOW"
    if score <= MODERATE_MAX:
        return "MODERATE"
    if score <= HIGH_MAX:
        return "HIGH"
    return "CRITICAL"


def compute_final_risk_score(
    ml_score: float, anomaly_score: float, rule_score: float
) -> float:
    """Weighted blend of the three 0-100 signals, rounded to 2 decimals
    and clamped to [0, 100]."""
    raw = ML_WEIGHT * ml_score + ANOMALY_WEIGHT * anomaly_score + RULE_WEIGHT * rule_score
    return round(min(max(raw, 0.0), 100.0), 2)


def run_pipeline() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train the three signals on the standard train split, then score the
    test split and combine into a risk table. Returns (test_df, risk_df) -
    risk_df has no fraud_label; it is joined back only for evaluation.
    """
    df = load_training_data()
    train_df, test_df = temporal_train_test_split(df)

    lr_model, scaler = train_model(train_df)
    if_model, score_min, score_max = train_anomaly_model(train_df)

    X_test = test_df[FEATURE_COLUMNS]
    ml_scores = lr_model.predict_proba(scaler.transform(X_test))[:, 1] * 100
    anomaly_scores = compute_anomaly_scores(if_model, X_test, score_min, score_max)

    rules_result = evaluate_rules(test_df)  # transaction_id, triggered_rules, rule_count, rule_score

    risk_df = test_df[["transaction_id"]].reset_index(drop=True).copy()
    risk_df["ml_score"] = np.round(ml_scores, 2)
    risk_df["anomaly_score"] = np.round(anomaly_scores, 2)
    risk_df = risk_df.merge(
        rules_result[["transaction_id", "rule_score", "triggered_rules"]],
        on="transaction_id",
    )
    risk_df["final_risk_score"] = [
        compute_final_risk_score(row.ml_score, row.anomaly_score, row.rule_score)
        for row in risk_df.itertuples()
    ]
    risk_df["risk_level"] = risk_df["final_risk_score"].apply(risk_level_for_score)
    risk_df["decision"] = risk_df["risk_level"].map(DECISION_BY_RISK_LEVEL)

    risk_df = risk_df[
        [
            "transaction_id",
            "ml_score",
            "anomaly_score",
            "rule_score",
            "final_risk_score",
            "risk_level",
            "decision",
            "triggered_rules",
        ]
    ]
    return test_df, risk_df


def _print_report(test_df: pd.DataFrame, risk_df: pd.DataFrame) -> None:
    merged = risk_df.merge(
        test_df[["transaction_id", TARGET_COLUMN]], on="transaction_id"
    )

    print("=" * 60)
    print("RISK AGGREGATION - PIPELINE SUMMARY")
    print("=" * 60)
    print(f"transactions evaluated (test period): {len(risk_df)}")
    print(f"average final_risk_score: {risk_df['final_risk_score'].mean():.2f}")

    print("\nrisk level distribution:")
    for level in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
        count = (risk_df["risk_level"] == level).sum()
        print(f"  {level:<10} {count:>6} ({100 * count / len(risk_df):.2f}%)")

    print("\ndecision distribution:")
    for decision in ["ALLOW", "STEP_UP", "MANUAL_REVIEW", "BLOCK"]:
        count = (risk_df["decision"] == decision).sum()
        print(f"  {decision:<16} {count:>6} ({100 * count / len(risk_df):.2f}%)")

    print("\n" + "=" * 60)
    print("FRAUD RATE BY RISK LEVEL (fraud_label used only for evaluation)")
    print("=" * 60)
    for level in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
        subset = merged[merged["risk_level"] == level]
        rate = subset[TARGET_COLUMN].mean() if len(subset) else 0.0
        print(f"  {level:<10} n={len(subset):>5}  fraud_rate={100 * rate:.2f}%")

    print("\nfraud rate by decision:")
    for decision in ["ALLOW", "STEP_UP", "MANUAL_REVIEW", "BLOCK"]:
        subset = merged[merged["decision"] == decision]
        rate = subset[TARGET_COLUMN].mean() if len(subset) else 0.0
        print(f"  {decision:<16} n={len(subset):>5}  fraud_rate={100 * rate:.2f}%")

    print("\n" + "=" * 60)
    print("CONFUSION MATRIX: BLOCK vs non-BLOCK")
    print("=" * 60)
    predicted_block = (merged["decision"] == "BLOCK").astype(int)
    cm = confusion_matrix(merged[TARGET_COLUMN], predicted_block)
    print("                    predicted_non_block  predicted_block")
    print(f"actual_normal       {cm[0][0]:>19}  {cm[0][1]:>15}")
    print(f"actual_fraud        {cm[1][0]:>19}  {cm[1][1]:>15}")

    print("\n" + "=" * 60)
    print("EXAMPLE TRANSACTIONS")
    print("=" * 60)
    examples = merged.sort_values("final_risk_score", ascending=False).head(10)
    for _, row in examples.iterrows():
        print(
            f"  txn={row['transaction_id']}  "
            f"ml={row['ml_score']:.1f} anomaly={row['anomaly_score']:.1f} "
            f"rule={row['rule_score']:.1f} -> final={row['final_risk_score']:.1f} "
            f"[{row['risk_level']}] -> {row['decision']}  "
            f"(actual_fraud={bool(row[TARGET_COLUMN])})"
        )


def main() -> None:
    assert abs(ML_WEIGHT + ANOMALY_WEIGHT + RULE_WEIGHT - 1.0) < 1e-9, "weights must sum to 1.0"

    print("Training signals on the standard chronological train split...")
    test_df, risk_df = run_pipeline()

    _print_report(test_df, risk_df)


if __name__ == "__main__":
    main()
