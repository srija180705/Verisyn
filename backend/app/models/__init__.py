"""ORM models for the Fraud Intelligence Platform.

All models must be imported here so Alembic's autogenerate discovers them
via Base.metadata.
"""
from app.models.base import TimestampMixin, UUIDPKMixin  # noqa: F401
from app.models.customer import Customer, CustomerStatus  # noqa: F401
from app.models.account import Account, AccountType, AccountStatus  # noqa: F401
from app.models.loan_application import (  # noqa: F401
    LoanApplication,
    ApplicationStatus,
    ApplicationType,
)
from app.models.device import Device  # noqa: F401
from app.models.ip_identity import IPIdentity  # noqa: F401
from app.models.transaction import (  # noqa: F401
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.models.event import Event  # noqa: F401
from app.models.feedback import TransactionFeedback, FeedbackLabel  # noqa: F401

__all__ = [
    "TimestampMixin",
    "UUIDPKMixin",
    "Customer",
    "CustomerStatus",
    "Account",
    "AccountType",
    "AccountStatus",
    "LoanApplication",
    "ApplicationStatus",
    "ApplicationType",
    "Device",
    "IPIdentity",
    "Transaction",
    "TransactionStatus",
    "TransactionType",
    "Event",
    "TransactionFeedback",
    "FeedbackLabel",
]
