"""add processed webhook events

Revision ID: 48bb71ac6084
Revises: a7c9e4f2b1d3
Create Date: 2026-09-25 06:22:48.894341

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "48bb71ac6084"
down_revision: Union[str, Sequence[str], None] = "a7c9e4f2b1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the processed webhook events table."""

    op.create_table(
        "processed_events",
        sa.Column(
            "event_id",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        ),
        sa.Column(
            "reference",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sqlmodel.sql.sqltypes.UTCDateTime(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )

    op.create_index(
        op.f("ix_processed_events_event_id"),
        "processed_events",
        ["event_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_processed_events_reference"),
        "processed_events",
        ["reference"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the processed webhook events table."""

    op.drop_index(
        op.f("ix_processed_events_reference"),
        table_name="processed_events",
    )

    op.drop_index(
        op.f("ix_processed_events_event_id"),
        table_name="processed_events",
    )

    op.drop_table("processed_events")