"""Account model."""
from sqlalchemy import Column, String, ForeignKey, Index
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class AccountType(str, enum.Enum):
    """Account type in the lending platform."""

    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT = "credit"
    LOAN = "loan"


class AccountStatus(str, enum.Enum):
    """Account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class Account(Base, UUIDPKMixin, TimestampMixin):
    """A financial account owned by a customer."""

    __tablename__ = "accounts"

    external_account_id = Column(String(255), unique=True, nullable=False, index=True)
    customer_id = Column(
        "customer_id",
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_type = Column(String(50), nullable=False)
    status = Column(String(50), default=AccountStatus.ACTIVE, nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="accounts")
    loan_applications = relationship(
        "LoanApplication", back_populates="account", cascade="all, delete-orphan"
    )
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_account_customer", "customer_id"),)
