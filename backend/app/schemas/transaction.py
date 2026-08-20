"""Request/response schemas for the transaction listing and ingestion
endpoints.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import TransactionType
from app.schemas.fraud import FraudAssessResponse


class TransactionSummary(BaseModel):
    id: uuid.UUID
    external_transaction_id: str
    amount: float
    currency: str
    transaction_type: str
    status: str
    occurred_at: datetime
    customer_external_id: str
    customer_name: str
    account_external_id: str
    account_type: str


class TransactionListResponse(BaseModel):
    total: int
    items: list[TransactionSummary]


class TransactionCreateRequest(BaseModel):
    """A new transaction entering the system. device_identifier/ip_address
    are optional - most fraud signals still work without them, they just
    mean is_new_device/is_new_ip-style features fall back to their default.
    """

    external_transaction_id: str = Field(min_length=1)
    external_account_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    transaction_type: TransactionType
    occurred_at: datetime | None = None
    device_identifier: str | None = None
    ip_address: str | None = None


class TransactionCreateResponse(BaseModel):
    """The stored transaction plus its immediate fraud assessment - the
    assessment is produced by the existing pipeline (assess_transaction),
    never recomputed or duplicated here.
    """

    transaction: TransactionSummary
    assessment: FraudAssessResponse
