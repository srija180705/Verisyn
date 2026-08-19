"""Event model."""
from sqlalchemy import Column, String, ForeignKey, DateTime, Index, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class Event(Base, UUIDPKMixin, TimestampMixin):
    """An event in the lending platform (transaction, application, etc.)."""

    __tablename__ = "events"

    external_event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    customer_id = Column(
        "customer_id",
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    account_id = Column(
        "account_id",
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    transaction_id = Column(
        "transaction_id",
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSON, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="events")
    account = relationship("Account", back_populates="events")
    transaction = relationship("Transaction", back_populates="events")

    __table_args__ = (
        Index("ix_event_customer", "customer_id"),
        Index("ix_event_account", "account_id"),
        Index("ix_event_transaction", "transaction_id"),
        Index("ix_event_type", "event_type"),
        Index("ix_event_occurred", "occurred_at"),
    )
