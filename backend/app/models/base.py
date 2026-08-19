"""Base model utilities for common columns and types."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid as uuid_lib


class TimestampMixin:
    """Adds created_at and updated_at columns to all models."""

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class UUIDPKMixin:
    """Adds a UUID primary key column."""

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_lib.uuid4,
        nullable=False,
    )
