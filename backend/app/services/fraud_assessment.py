"""Fraud assessment orchestration for a single transaction.

Wires together the existing fraud engine (ml/features.py, ml/model.py,
ml/anomaly.py, ml/rules.py, ml/risk.py) - no scoring/rule logic is
duplicated here, this only calls into those modules and shapes the
result. Model artifacts are loaded from disk (load_saved_model()); this
module never trains anything.
"""
import sys
from pathlib import Path
from uuid import UUID

import pandas as pd
from sqlalchemy.orm import Session

sys.path.append(str(Path(__file__).resolve().parents[3]))  # repo root

from ml.anomaly import compute_anomaly_scores  # noqa: E402
from ml.anomaly import load_saved_model as load_anomaly_model  # noqa: E402
from ml.features import compute_features_for_new_transaction, get_precomputed_features  # noqa: E402
from ml.model import FEATURE_COLUMNS  # noqa: E402
from ml.model import load_saved_model as load_lr_model  # noqa: E402
from ml.risk import DECISION_BY_RISK_LEVEL, compute_final_risk_score, risk_level_for_score  # noqa: E402
from ml.rules import evaluate_transaction as evaluate_rules_for_transaction  # noqa: E402

from app.models import Transaction

BOOLEAN_FEATURE_COLUMNS = ("is_new_device", "is_new_ip", "location_anomaly")


class TransactionNotFoundError(Exception):
    """Raised when the given transaction_id does not exist."""


def assess_transaction(db: Session, transaction_id: UUID) -> dict:
    """Run the full fraud engine for one existing transaction and return
    the combined assessment. Raises TransactionNotFoundError if the
    transaction doesn't exist.

    Two paths, neither of which replays the full transaction history:
      - historical transaction already covered by the last
        ml/features.py batch run -> O(1) CSV lookup
        (get_precomputed_features)
      - anything else (a new/live transaction) -> point-in-time features
        computed from just this customer's history and this device/ip's
        30-day window (compute_features_for_new_transaction)
    """
    txn_row = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if txn_row is None:
        raise TransactionNotFoundError(str(transaction_id))

    features = get_precomputed_features(transaction_id)
    if features is None:
        txn = {
            "id": txn_row.id,
            "customer_id": txn_row.customer_id,
            "account_id": txn_row.account_id,
            "device_id": txn_row.device_id,
            "ip_identity_id": txn_row.ip_identity_id,
            "amount": txn_row.amount,
            "occurred_at": txn_row.occurred_at,
        }
        features = compute_features_for_new_transaction(txn)

    feature_values = {col: features[col] for col in FEATURE_COLUMNS}

    # sklearn inputs need int, not bool, for the boolean feature columns -
    # same conversion ml/model.py's load_training_data() applies.
    model_input = dict(feature_values)
    for col in BOOLEAN_FEATURE_COLUMNS:
        model_input[col] = int(bool(model_input[col]))
    X = pd.DataFrame([model_input])[FEATURE_COLUMNS]

    lr_model, scaler = load_lr_model()
    ml_score = float(lr_model.predict_proba(scaler.transform(X))[:, 1][0] * 100)

    if_model, score_min, score_max = load_anomaly_model()
    anomaly_score = float(compute_anomaly_scores(if_model, X, score_min, score_max)[0])

    rules_row = {**feature_values, "transaction_id": features["transaction_id"]}
    rules_result = evaluate_rules_for_transaction(rules_row)
    rule_score = float(rules_result["rule_score"])
    triggered_rules = rules_result["triggered_rules"]

    final_risk_score = compute_final_risk_score(ml_score, anomaly_score, rule_score)
    risk_level = risk_level_for_score(final_risk_score)
    decision = DECISION_BY_RISK_LEVEL[risk_level]

    return {
        "transaction_id": features["transaction_id"],
        "ml_score": round(ml_score, 2),
        "anomaly_score": round(anomaly_score, 2),
        "rule_score": rule_score,
        "final_risk_score": final_risk_score,
        "risk_level": risk_level,
        "decision": decision,
        "triggered_rules": triggered_rules,
        "features": feature_values,
    }
