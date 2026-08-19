"""Loan application model."""
from sqlalchemy import Column, String, ForeignKey, Numeric, Enum, Index, CheckConstraint, DateTime
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class ApplicationStatus(str, enum.Enum):
    """Loan application status."""

    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class ApplicationType(str, enum.Enum):
    """Type of loan application."""

    PERSONAL = "personal"
    AUTO = "auto"
    HOME = "home"
    BUSINESS = "business"


class LoanApplication(Base, UUIDPKMixin, TimestampMixin):
    """A loan application from a customer."""

    __tablename__ = "loan_applications"

    external_application_id = Column(String(255), unique=True, nullable=False, index=True)
    customer_id = Column(
        "customer_id",
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id = Column(
        "account_id",
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True,
    )
    application_amount = Column(Numeric(15, 2), nullable=False)
    application_type = Column(String(50), nullable=False)
    status = Column(String(50), default=ApplicationStatus.SUBMITTED, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="loan_applications")
    account = relationship("Account", back_populates="loan_applications")

    __table_args__ = (
        Index("ix_loanapp_customer", "customer_id"),
        Index("ix_loanapp_account", "account_id"),
        CheckConstraint("application_amount > 0", name="ck_loanapp_amount_positive"),
    )
