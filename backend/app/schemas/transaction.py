"""Request/response schemas for the transaction listing endpoint."""
import uuid
from datetime import datetime

from pydantic import BaseModel


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
