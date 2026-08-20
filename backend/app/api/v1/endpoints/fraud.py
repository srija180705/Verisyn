"""Fraud assessment + AI explanation endpoints - thin wrappers around
app.services.fraud_assessment / app.services.ai_explanation, which
orchestrate the existing ML/rules/risk pipeline and ai/ abstraction. No
scoring or LLM-calling logic lives in this file.
"""
import json
import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.fraud import (
    AIExplanationResponse,
    FraudAssessRequest,
    FraudAssessResponse,
    ModelInfoResponse,
    RuleConfig,
    RulesConfigResponse,
)
from app.services.ai_explanation import generate_explanation
from app.services.fraud_assessment import TransactionNotFoundError, assess_transaction

sys.path.append(str(Path(__file__).resolve().parents[5]))  # repo root

from ml import risk as risk_config  # noqa: E402
from ml import rules as rules_config  # noqa: E402
from ml.model import MODELS_DIR  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fraud", tags=["fraud"])

_MODEL_METADATA_PATH = MODELS_DIR / "model_metadata.json"

# Human-readable condition per rule, built from the same named threshold
# constants ml/rules.py evaluates against - not a second copy of the
# logic, just a display string for the Rules tab.
_RULE_CONDITIONS = {
    "HIGH_TRANSACTION_VELOCITY": f"transactions_last_10m >= {rules_config.HIGH_TRANSACTION_VELOCITY_THRESHOLD}",
    "EXTREME_TRANSACTION_VELOCITY": f"transactions_last_10m >= {rules_config.EXTREME_TRANSACTION_VELOCITY_THRESHOLD}",
    "LARGE_AMOUNT": f"amount_vs_customer_avg >= {rules_config.LARGE_AMOUNT_THRESHOLD}",
    "NEW_DEVICE_LARGE_AMOUNT": f"is_new_device AND amount_vs_customer_avg >= {rules_config.NEW_DEVICE_LARGE_AMOUNT_THRESHOLD}",
    "NEW_IP_LARGE_AMOUNT": f"is_new_ip AND amount_vs_customer_avg >= {rules_config.NEW_IP_LARGE_AMOUNT_THRESHOLD}",
    "DEVICE_ACCOUNT_SHARING": f"accounts_per_device >= {rules_config.DEVICE_ACCOUNT_SHARING_THRESHOLD}",
    "IP_ACCOUNT_SHARING": f"accounts_per_ip >= {rules_config.IP_ACCOUNT_SHARING_THRESHOLD}",
    "FAILED_LOGIN_BURST": f"failed_logins_last_10m >= {rules_config.FAILED_LOGIN_BURST_THRESHOLD}",
    "LOCATION_ANOMALY": "location_anomaly is true",
}


@router.get("/rules-config", response_model=RulesConfigResponse)
def rules_config_view() -> RulesConfigResponse:
    """Read-only snapshot of the deterministic rule engine and risk
    aggregation constants, for the Rules tab. Values are read directly
    from ml/rules.py and ml/risk.py - this endpoint has no logic of its
    own beyond formatting them as JSON.
    """
    rules = [
        RuleConfig(name=name, weight=weight, condition=_RULE_CONDITIONS[name])
        for name, weight in rules_config.RULE_WEIGHTS.items()
    ]
    return RulesConfigResponse(
        rules=rules,
        max_rule_score=rules_config.MAX_RULE_SCORE,
        signal_weights={
            "ml": risk_config.ML_WEIGHT,
            "anomaly": risk_config.ANOMALY_WEIGHT,
            "rule": risk_config.RULE_WEIGHT,
        },
        risk_level_thresholds={
            "LOW_MAX": risk_config.LOW_MAX,
            "MODERATE_MAX": risk_config.MODERATE_MAX,
            "HIGH_MAX": risk_config.HIGH_MAX,
        },
        decision_by_risk_level=risk_config.DECISION_BY_RISK_LEVEL,
    )


@router.get("/model-info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    """Which model version is currently active, when it was trained, and
    how many verified feedback samples it used - read directly from
    ml/models/model_metadata.json, written only by ml/retrain.py after a
    successful retrain. No metadata file yet means the original
    (non-retrained) baseline model is still active.
    """
    if not _MODEL_METADATA_PATH.exists():
        return ModelInfoResponse(
            version=1,
            trained_at=None,
            feedback_samples_used=0,
            is_retrained=False,
        )
    metadata = json.loads(_MODEL_METADATA_PATH.read_text())
    return ModelInfoResponse(
        version=metadata["version"],
        trained_at=metadata["trained_at"],
        feedback_samples_used=metadata["feedback_samples_used"],
        is_retrained=True,
    )


@router.post("/assess", response_model=FraudAssessResponse)
def assess(
    request: FraudAssessRequest, db: Session = Depends(get_db)
) -> FraudAssessResponse:
    try:
        result = assess_transaction(db, request.transaction_id)
    except TransactionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )
    except FileNotFoundError:
        logger.error("Fraud model artifacts missing - run ml/model.py and ml/anomaly.py")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fraud model is not available",
        )
    return FraudAssessResponse(**result)


@router.post("/explain", response_model=AIExplanationResponse)
def explain(
    request: FraudAssessRequest, db: Session = Depends(get_db)
) -> AIExplanationResponse:
    """Advisory-only explanation of an already-computed assessment. Never
    recomputes or changes the score/level/decision - see
    app/services/ai_explanation.py.
    """
    try:
        result = generate_explanation(db, request.transaction_id)
    except TransactionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )
    except FileNotFoundError:
        logger.error("Fraud model artifacts missing - run ml/model.py and ml/anomaly.py")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fraud model is not available",
        )
    return AIExplanationResponse(**result)
