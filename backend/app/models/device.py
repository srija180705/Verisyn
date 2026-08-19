"""Device model."""
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class Device(Base, UUIDPKMixin, TimestampMixin):
    """A device (mobile phone, laptop, etc.) used by customers."""

    __tablename__ = "devices"

    device_identifier = Column(String(255), unique=True, nullable=False, index=True)
    device_type = Column(String(50), nullable=True)
    operating_system = Column(String(50), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    transactions = relationship("Transaction", back_populates="device")

    __table_args__ = (
        Index("ix_device_last_seen", "last_seen_at"),
        Index("ix_device_first_seen", "first_seen_at"),
    )
