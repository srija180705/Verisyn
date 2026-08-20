"""Request/response schemas for the transaction feedback endpoint."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import FeedbackLabel


class FeedbackSubmitRequest(BaseModel):
    transaction_id: uuid.UUID
    label: FeedbackLabel
    reviewer: str | None = None


class FeedbackResponse(BaseModel):
    transaction_id: uuid.UUID
    label: FeedbackLabel
    reviewer: str | None
    reviewed_at: datetime
