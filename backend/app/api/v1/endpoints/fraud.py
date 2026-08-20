"""Fraud assessment + AI explanation endpoints - thin wrappers around
app.services.fraud_assessment / app.services.ai_explanation, which
orchestrate the existing ML/rules/risk pipeline and ai/ abstraction. No
scoring or LLM-calling logic lives in this file.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.fraud import AIExplanationResponse, FraudAssessRequest, FraudAssessResponse
from app.services.ai_explanation import generate_explanation
from app.services.fraud_assessment import TransactionNotFoundError, assess_transaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fraud", tags=["fraud"])


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
