"""Customer model."""
from sqlalchemy import Column, String, Date, Enum, Index, UniqueConstraint
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class CustomerStatus(str, enum.Enum):
    """Customer account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Customer(Base, UUIDPKMixin, TimestampMixin):
    """A customer in the lending platform."""

    __tablename__ = "customers"

    external_customer_id = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    status = Column(String(50), default=CustomerStatus.ACTIVE, nullable=False)

    # Relationships
    accounts = relationship("Account", back_populates="customer", cascade="all, delete-orphan")
    loan_applications = relationship(
        "LoanApplication", back_populates="customer", cascade="all, delete-orphan"
    )
    transactions = relationship("Transaction", back_populates="customer", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_customer_email", "email"),)
