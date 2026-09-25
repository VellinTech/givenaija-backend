"""create ledger tables (accounts, journal_entries, journal_lines)

The ledger domain's SQLModel classes existed in code but were never
included in any migration -- these tables don't exist in the database yet.
Without this, every donation 500s the moment it tries to post a journal
entry (get_or_create_cash_account / post_journal_entry hit a table that
isn't there).

Revision ID: 9f4b2c8a1d6e
Revises: 5e298f2d1a2b
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "9f4b2c8a1d6e"
down_revision = "5e298f2d1a2b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_accounts_id"), "accounts", ["id"])
    op.create_index(op.f("ix_accounts_code"), "accounts", ["code"])

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("reference_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_journal_entries_id"), "journal_entries", ["id"])
    op.create_index(op.f("ix_journal_entries_reference_id"), "journal_entries", ["reference_id"])

    op.create_table(
        "journal_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("journal_entry_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("debit", sa.Numeric(12, 2), nullable=False),
        sa.Column("credit", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_journal_lines_id"), "journal_lines", ["id"])
    op.create_index(op.f("ix_journal_lines_journal_entry_id"), "journal_lines", ["journal_entry_id"])
    op.create_index(op.f("ix_journal_lines_account_id"), "journal_lines", ["account_id"])

    # donations.journal_entry_id existed from the very first migration but
    # had no FK constraint yet, since journal_entries didn't exist. Add it
    # now that the table finally does.
    op.create_foreign_key(
        "fk_donations_journal_entry_id",
        "donations", "journal_entries",
        ["journal_entry_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_donations_journal_entry_id", "donations", type_="foreignkey")
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    op.drop_table("accounts")