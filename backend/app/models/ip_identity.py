"""IP identity model."""
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class IPIdentity(Base, UUIDPKMixin, TimestampMixin):
    """An IP address and its associated metadata."""

    __tablename__ = "ip_identities"

    ip_address = Column(INET, unique=True, nullable=False, index=True)
    ip_version = Column(String(10), nullable=False)  # "v4" or "v6"
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    transactions = relationship("Transaction", back_populates="ip_identity")

    __table_args__ = (
        Index("ix_ipidentity_last_seen", "last_seen_at"),
        Index("ix_ipidentity_first_seen", "first_seen_at"),
    )
