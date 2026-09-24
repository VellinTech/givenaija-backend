from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID
from sqlmodel import Field, SQLModel
from app.db.base import BaseUUIDModel


def utc_now() -> datetime:
    """Timezone-aware UTC now(); matches the helper in app/db/base.py."""
    return datetime.now(timezone.utc)


class DonationStatus(str, Enum):
    """Lifecycle states for monetary donations."""
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class Donation(BaseUUIDModel, table=True):
    """Database entity representing monetary contributions."""
    __tablename__ = "donations"

    member_id: UUID = Field(foreign_key="members.id", index=True, nullable=False)
    campaign_id: UUID = Field(foreign_key="campaigns.id", index=True, nullable=False)
    amount: Decimal = Field(max_digits=12, decimal_places=2, nullable=False)
    bank_ref: str = Field(unique=True, index=True, nullable=False)
    status: str = Field(default=DonationStatus.PENDING.value, index=True, nullable=False)
    journal_entry_id: Optional[UUID] = Field(default=None, nullable=True)


class Receipt(BaseUUIDModel, table=True):
    """Database entity representing auto-generated proof-of-payment receipts."""
    __tablename__ = "receipts"

    donation_id: UUID = Field(foreign_key="donations.id", unique=True, index=True, nullable=False)
    receipt_number: str = Field(unique=True, index=True, nullable=False)
    issued_at: datetime = Field(default_factory=utc_now, nullable=False)


class IdempotencyKey(SQLModel, table=True):
    """Database entity tracking idempotent HTTP requests to prevent duplicate side-effects."""
    __tablename__ = "idempotency_keys"

    key: str = Field(primary_key=True, index=True, nullable=False)
    endpoint: str = Field(nullable=False)
    body_hash: str = Field(nullable=False)
    response_json: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)




class DonationCreate(SQLModel):
    """Request DTO payload for recording a donation."""
    campaign_id: UUID
    amount: Decimal
    bank_ref: str


class DonationRead(SQLModel):
    """Response DTO for exposing donation details."""
    id: UUID
    member_id: UUID
    campaign_id: UUID
    amount: Decimal
    bank_ref: str
    status: str
    created_at: str


class ReceiptRead(SQLModel):
    """Response DTO for exposing receipt credentials."""
    id: UUID
    donation_id: UUID
    receipt_number: str
    issued_at: str


class FinancialStatement(SQLModel):
    """Aggregated financial summary DTO for reporting."""
    total_donations_count: int
    total_revenue_raised: Decimal
    successful_donations_count: int
    failed_donations_count: int
    generated_at: str