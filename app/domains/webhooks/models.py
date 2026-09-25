from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProcessedEvent(SQLModel, table=True):
    """Tracks payment webhook events so provider retries are safe."""

    __tablename__ = "processed_events"

    event_id: str = Field(primary_key=True, nullable=False, index=True)
    event_type: str = Field(nullable=False)
    reference: str = Field(nullable=False, index=True)
    processed_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
    )