from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID
from sqlmodel import Field, SQLModel
from app.db.base import BaseUUIDModel


class CampaignStatus(str, Enum):
    """Enumeration of active lifecycle states for fundraising campaigns."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PledgeStatus(str, Enum):
    # Enumeration of states for member financial pledges.
    PENDING = "PENDING"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"

class Campaign(BaseUUIDModel, table=True):
    # Database entity representing a fundraising campaign.
    __tablename__ = "campaigns"

    creator_id: UUID = Field(foreign_key="users.id", index=True, nullable=False)
    title: str = Field(index=True, nullable=False)
    goal_amount: Decimal = Field(max_digits=12, decimal_places=2, nullable=False)
    raised_amount: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2, nullable=False)
    status: str = Field(default=CampaignStatus.OPEN.value, index=True, nullable=False)


class Pledge(BaseUUIDModel, table=True):
    # Database entity representing a user's pledge towards a campaign.
    __tablename__ = "pledges"

    member_id: UUID = Field(foreign_key="members.id", index=True, nullable=False)
    campaign_id: UUID = Field(foreign_key="campaigns.id", index=True, nullable=False)
    amount: Decimal = Field(max_digits=12, decimal_places=2, nullable=False)
    status: str = Field(default=PledgeStatus.PENDING.value, nullable=False)



class CampaignCreate(SQLModel):
    # Request DTO payload for initializing a campaign.
    title: str
    goal_amount: Decimal


class CampaignRead(SQLModel):
    # Response DTO for exposing campaign details.
    id: UUID
    creator_id: UUID
    title: str
    goal_amount: Decimal
    raised_amount: Decimal
    status: str
    created_at: str


class PledgeCreate(SQLModel):
    # Request DTO payload for registering a funding pledge.
    campaign_id: UUID
    amount: Decimal


class PledgeRead(SQLModel):
    # Response DTO for exposing pledge records.
    id: UUID
    member_id: UUID
    campaign_id: UUID
    amount: Decimal
    status: str
    created_at: str    
