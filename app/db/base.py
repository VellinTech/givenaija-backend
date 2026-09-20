

from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel


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
        default_factory=datetime.utcnow,
        nullable=False
    )

    # Last update timestamp stored in UTC timezone
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False
    )