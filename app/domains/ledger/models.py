from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID
from sqlmodel import Field, SQLModel
from app.db.base import BaseUUIDModel


class AccountType(str, Enum):
    """General ledger account classifications."""
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class Account(BaseUUIDModel, table=True):
    """Database model representing a ledger account."""
    __tablename__ = "accounts"

    code: str = Field(unique=True, index=True, nullable=False)  # e.g. "1010" for Bank Cash
    name: str = Field(nullable=False)                           # e.g. "Main Operating Account"
    account_type: str = Field(nullable=False)                  # Asset, Revenue, etc.


class JournalEntry(BaseUUIDModel, table=True):
    """Database model representing a double-entry transaction header."""
    __tablename__ = "journal_entries"

    description: str = Field(nullable=False)
    reference_id: Optional[str] = Field(default=None, index=True)  # e.g. Donation UUID or Bank Ref


class JournalLine(BaseUUIDModel, table=True):
    """Database model representing individual Debit/Credit lines within an entry."""
    __tablename__ = "journal_lines"

    journal_entry_id: UUID = Field(foreign_key="journal_entries.id", index=True, nullable=False)
    account_id: UUID = Field(foreign_key="accounts.id", index=True, nullable=False)
    debit: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2, nullable=False)
    credit: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2, nullable=False)



class AccountCreate(SQLModel):
    """Request payload for creating a general ledger account."""
    code: str
    name: str
    account_type: AccountType


class AccountRead(SQLModel):
    """Response payload exposing account details."""
    id: UUID
    code: str
    name: str
    account_type: str


class JournalLineCreate(SQLModel):
    """Payload for individual debit/credit line items."""
    account_id: UUID
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")


class JournalEntryCreate(SQLModel):
    """Payload for creating a balanced double-entry transaction."""
    description: str
    reference_id: Optional[str] = None
    lines: List[JournalLineCreate]


class JournalLineRead(SQLModel):
    """Response DTO for journal lines."""
    id: UUID
    account_id: UUID
    debit: Decimal
    credit: Decimal


class JournalEntryRead(SQLModel):
    """Response DTO for general ledger journal entries."""
    id: UUID
    description: str
    reference_id: Optional[str]
    created_at: str
    lines: List[JournalLineRead]