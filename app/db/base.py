from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Returns the current time as a timezone-aware UTC datetime.

    Using datetime.now(timezone.utc) instead of the deprecated
    datetime.utcnow(), which returns a naive datetime that newer
    SQLModel/SQLAlchemy versions reject for TIMESTAMP WITH TIME ZONE columns.
    """
    return datetime.now(timezone.utc)


class BaseUUIDModel(SQLModel):

    # Primary key utilizing auto-generated UUID version 4
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )

    # Creation timestamp stored in UTC timezone
    created_at: datetime = Field(
        default_factory=utc_now,
        nullable=False
    )

    # Last update timestamp stored in UTC timezone
    updated_at: datetime = Field(
        default_factory=utc_now,
        nullable=False
    )