"""Transaction model."""
from sqlalchemy import Column, String, ForeignKey, Numeric, DateTime, Index, CheckConstraint
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class TransactionStatus(str, enum.Enum):
    """Transaction status."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"


class TransactionType(str, enum.Enum):
    """Type of transaction."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    PAYMENT = "payment"
    REFUND = "refund"


class Transaction(Base, UUIDPKMixin, TimestampMixin):
    """A financial transaction."""

    __tablename__ = "transactions"

    external_transaction_id = Column(String(255), unique=True, nullable=False, index=True)
    customer_id = Column(
        "customer_id",
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id = Column(
        "account_id",
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_id = Column(
        "device_id",
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_identity_id = Column(
        "ip_identity_id",
        ForeignKey("ip_identities.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    transaction_type = Column(String(50), nullable=False)
    status = Column(String(50), default=TransactionStatus.PENDING, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    device = relationship("Device", back_populates="transactions")
    ip_identity = relationship("IPIdentity", back_populates="transactions")
    events = relationship("Event", back_populates="transaction", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_transaction_customer", "customer_id"),
        Index("ix_transaction_account", "account_id"),
        Index("ix_transaction_device", "device_id"),
        Index("ix_transaction_ip", "ip_identity_id"),
        Index("ix_transaction_occurred", "occurred_at"),
        CheckConstraint("amount > 0", name="ck_transaction_amount_positive"),
    )
