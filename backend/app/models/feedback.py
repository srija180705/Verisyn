"""Transaction feedback model - a reviewer's verified verdict on an
already-assessed transaction. Purely a label store: it never feeds back
into scoring on its own (see app/services/fraud_assessment.py, which is
unmodified) - only ml/retrain.py, run manually, reads from this table.
"""
import enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class FeedbackLabel(str, enum.Enum):
    """A reviewer's verified verdict - the only ground truth retraining is
    allowed to use, never the system's own prediction."""

    CONFIRMED_FRAUD = "confirmed_fraud"
    CONFIRMED_GENUINE = "confirmed_genuine"


class TransactionFeedback(Base, UUIDPKMixin, TimestampMixin):
    """One reviewer verdict per transaction. `transaction_id` is unique -
    a second submission updates the existing row (see
    app/api/v1/endpoints/feedback.py) rather than creating a duplicate,
    so a transaction never carries conflicting feedback.
    """

    __tablename__ = "transaction_feedback"

    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    label = Column(String(50), nullable=False)
    reviewer = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=False)

    transaction = relationship("Transaction")

    __table_args__ = (Index("ix_feedback_transaction", "transaction_id"),)
