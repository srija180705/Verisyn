"""Explicit, manual retraining using verified reviewer feedback.

Scope: retrains ONLY the Logistic Regression classifier (ml/model.py) -
the one supervised, label-driven signal in the pipeline. The anomaly
detector (ml/anomaly.py) is unsupervised on legitimate-only data and the
rule engine (ml/rules.py) is deterministic; neither takes a fraud label,
so neither is touched here. This keeps the rest of the scoring pipeline
independent, per this phase's safety requirement.

Ground truth is ONLY:
  1. the existing training_features.csv's fraud_label column (the
     original, human/process-verified labels the whole project has used
     since Phase 2B), and
  2. explicitly verified reviewer feedback (transaction_feedback table -
     CONFIRMED_FRAUD / CONFIRMED_GENUINE only)
The system's own predictions are never read as ground truth here.

Reuses, unchanged: ml/model.py's load_training_data/train_model/
evaluate_model/FEATURE_COLUMNS/TARGET_COLUMN (same architecture, same
LogisticRegression), and ml/features.py's get_precomputed_features/
compute_features_for_new_transaction (same feature computation used for
live /fraud/assess calls) - no scoring or feature logic is duplicated.

Safety: new artifacts are trained and evaluated in memory first. The live
model files (ml/models/logistic_regression.joblib, scaler.joblib) are
only overwritten AFTER training succeeds, and the previous files are
backed up (.bak) first. If anything raises before that point, the live
model is never touched and keeps serving requests exactly as before
(same "restart the server to pick up a new model" convention ml/model.py
already documents - this script doesn't change that).

Usage:
    python ml/retrain.py
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

import pandas as pd  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.database import engine  # noqa: E402
from app.models import Transaction, TransactionFeedback  # noqa: E402

sys.path.append(str(Path(__file__).resolve().parents[1]))

from ml.features import (  # noqa: E402
    compute_features_for_new_transaction,
    get_precomputed_features,
)
from ml.model import (  # noqa: E402
    FEATURE_COLUMNS,
    MODEL_PATH,
    MODELS_DIR,
    SCALER_PATH,
    TARGET_COLUMN,
    evaluate_model,
    load_training_data,
    temporal_train_test_split,
    train_model,
)

METADATA_PATH = MODELS_DIR / "model_metadata.json"

# Small, sensible minimum for a hackathon prototype: enough that a
# handful of clicks can't masquerade as "learning", not so large it's
# unreachable in a demo. Both classes required so the classifier actually
# has something to discriminate between.
MIN_TOTAL_FEEDBACK = 20
MIN_PER_CLASS = 3

LABEL_TO_FRAUD = {"confirmed_fraud": 1, "confirmed_genuine": 0}


class InsufficientFeedbackError(Exception):
    """Raised when there isn't enough verified feedback yet to retrain."""


def load_verified_feedback() -> list[dict]:
    """All (transaction, verdict) pairs with verified feedback, straight
    from Postgres - never derived from the system's own predictions."""
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
                TransactionFeedback.label,
            ).join(TransactionFeedback, TransactionFeedback.transaction_id == Transaction.id)
        ).all()
    return [dict(row._mapping) for row in rows]


def check_feedback_threshold(feedback_rows: list[dict]) -> None:
    total = len(feedback_rows)
    fraud_count = sum(1 for r in feedback_rows if r["label"] == "confirmed_fraud")
    genuine_count = total - fraud_count

    if total < MIN_TOTAL_FEEDBACK:
        raise InsufficientFeedbackError(
            f"Only {total} verified feedback samples available - need at "
            f"least {MIN_TOTAL_FEEDBACK} before retraining."
        )
    if fraud_count < MIN_PER_CLASS or genuine_count < MIN_PER_CLASS:
        raise InsufficientFeedbackError(
            f"Need at least {MIN_PER_CLASS} of each label - have "
            f"{fraud_count} confirmed_fraud, {genuine_count} confirmed_genuine."
        )


def feedback_rows_to_feature_rows(feedback_rows: list[dict]) -> list[dict]:
    """Feature-engineer each feedback transaction using the exact same
    functions the live assessment path uses, then attach the VERIFIED
    label (never the model's own prediction) as fraud_label.
    """
    feature_rows = []
    for row in feedback_rows:
        features = get_precomputed_features(row["id"])
        if features is None:
            features = compute_features_for_new_transaction(row)
        feature_row = {col: features[col] for col in FEATURE_COLUMNS}
        for col in ("is_new_device", "is_new_ip", "location_anomaly"):
            feature_row[col] = int(bool(feature_row[col]))
        feature_row[TARGET_COLUMN] = LABEL_TO_FRAUD[row["label"]]
        feature_rows.append(feature_row)
    return feature_rows


def run_retrain() -> dict:
    """Train + evaluate a new model in memory. Raises on any failure
    without touching the live model files. Returns metadata on success -
    caller decides whether to activate it.
    """
    feedback_rows = load_verified_feedback()
    check_feedback_threshold(feedback_rows)

    base_df = load_training_data()
    train_df, test_df = temporal_train_test_split(base_df)

    feedback_features = pd.DataFrame(feedback_rows_to_feature_rows(feedback_rows))
    augmented_train_df = pd.concat([train_df, feedback_features], ignore_index=True)

    model, scaler = train_model(augmented_train_df)
    # Evaluate on the ORIGINAL held-out test split (unseen, unchanged) so
    # the metrics are comparable to the baseline model's reported numbers.
    metrics = evaluate_model(model, scaler, test_df)

    return {
        "model": model,
        "scaler": scaler,
        "feedback_samples_used": len(feedback_rows),
        "base_training_rows": len(train_df),
        "augmented_training_rows": len(augmented_train_df),
        "metrics": {
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "roc_auc": metrics["roc_auc"],
            "pr_auc": metrics["pr_auc"],
        },
    }


def _next_version(current_metadata: dict | None) -> int:
    return (current_metadata["version"] + 1) if current_metadata else 2


def _load_current_metadata() -> dict | None:
    if not METADATA_PATH.exists():
        return None
    return json.loads(METADATA_PATH.read_text())


def activate_new_model(result: dict) -> dict:
    """Back up the currently-live model, then atomically replace it with
    the newly trained one. Only called after run_retrain() has already
    succeeded - nothing here can fail on the "old model is gone" case,
    since the backup happens first and the writes are the last step.
    """
    import joblib

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists():
        shutil.copy2(MODEL_PATH, MODEL_PATH.with_suffix(".joblib.bak"))
    if SCALER_PATH.exists():
        shutil.copy2(SCALER_PATH, SCALER_PATH.with_suffix(".joblib.bak"))

    joblib.dump(result["model"], MODEL_PATH)
    joblib.dump(result["scaler"], SCALER_PATH)

    current_metadata = _load_current_metadata()
    metadata = {
        "version": _next_version(current_metadata),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "feedback_samples_used": result["feedback_samples_used"],
        "base_training_rows": result["base_training_rows"],
        "augmented_training_rows": result["augmented_training_rows"],
        "metrics": result["metrics"],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2))
    return metadata


def main() -> None:
    print("Loading verified reviewer feedback...")
    try:
        result = run_retrain()
    except InsufficientFeedbackError as e:
        print(f"\nRetraining refused: {e}")
        print("The existing model is untouched and continues serving requests.")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001 - any training failure must not touch the live model
        print(f"\nRetraining failed: {e}")
        print("The existing model is untouched and continues serving requests.")
        sys.exit(1)

    print(
        f"Trained on {result['base_training_rows']} base rows + "
        f"{result['feedback_samples_used']} verified feedback rows "
        f"({result['augmented_training_rows']} total)."
    )
    print("Metrics on the original held-out test split:")
    for name, value in result["metrics"].items():
        print(f"  {name}: {value:.4f}")

    metadata = activate_new_model(result)
    print(f"\nActivated model version {metadata['version']} (trained_at={metadata['trained_at']}).")
    print(f"Metadata written to {METADATA_PATH}")
    print("Restart the backend server to pick up the new model (same as ml/model.py).")


if __name__ == "__main__":
    main()
