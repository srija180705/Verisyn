"""Reviewer feedback endpoints - stores a verified CONFIRMED_FRAUD /
CONFIRMED_GENUINE verdict for a transaction. This is a label store only:
submitting feedback never touches the existing fraud assessment
(app.services.fraud_assessment.assess_transaction is not called here, and
no score/level/decision field is written by this file). Labelled feedback
is only ever consumed by ml/retrain.py, run manually.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Transaction, TransactionFeedback
from app.schemas.feedback import FeedbackResponse, FeedbackSubmitRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse)
def submit_feedback(
    payload: FeedbackSubmitRequest, db: Session = Depends(get_db)
) -> FeedbackResponse:
    """Create or update the verdict for a transaction. `transaction_id` is
    unique on transaction_feedback, so a second submission for the same
    transaction updates the existing row (e.g. a reviewer correcting
    themselves) rather than creating conflicting duplicate feedback.
    """
    txn_exists = db.query(Transaction.id).filter(Transaction.id == payload.transaction_id).first()
    if txn_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    existing = (
        db.query(TransactionFeedback)
        .filter(TransactionFeedback.transaction_id == payload.transaction_id)
        .first()
    )
    now = datetime.now(timezone.utc)

    if existing:
        existing.label = payload.label.value
        existing.reviewer = payload.reviewer
        existing.reviewed_at = now
        feedback = existing
    else:
        feedback = TransactionFeedback(
            transaction_id=payload.transaction_id,
            label=payload.label.value,
            reviewer=payload.reviewer,
            reviewed_at=now,
        )
        db.add(feedback)

    db.commit()
    db.refresh(feedback)
    return FeedbackResponse(
        transaction_id=feedback.transaction_id,
        label=feedback.label,
        reviewer=feedback.reviewer,
        reviewed_at=feedback.reviewed_at,
    )


@router.get("/{transaction_id}", response_model=FeedbackResponse)
def get_feedback(transaction_id: str, db: Session = Depends(get_db)) -> FeedbackResponse:
    """The current verdict for one transaction, if any - lets the
    investigation panel show whether it's already been reviewed."""
    feedback = (
        db.query(TransactionFeedback)
        .filter(TransactionFeedback.transaction_id == transaction_id)
        .first()
    )
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No feedback yet")
    return FeedbackResponse(
        transaction_id=feedback.transaction_id,
        label=feedback.label,
        reviewer=feedback.reviewer,
        reviewed_at=feedback.reviewed_at,
    )
