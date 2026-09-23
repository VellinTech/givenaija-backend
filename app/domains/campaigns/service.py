"""
Campaigns Domain Business Logic.

Handles campaign creation, paginated queries, status changes, pledge processing,
audit trail logging, and streaming events (SSE).
"""

import asyncio
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.domains.campaigns.models import Campaign, CampaignCreate, CampaignStatus, Pledge, PledgeCreate, PledgeStatus
from app.domains.auth.models import Member
from app.domains.audit.service import log_event

# Active client connection queues for Server-Sent Events (SSE) broadcasting
_sse_subscribers: list[asyncio.Queue] = []


async def broadcast_campaign_event(data: str) -> None:
    """Pushes a JSON string update to all open SSE subscriber client queues."""
    for queue in list(_sse_subscribers):
        await queue.put(data)


def create_campaign(session: Session, campaign_in: CampaignCreate, creator_id: UUID) -> Campaign:
    """Creates a new campaign entity and records a system audit event, as ONE transaction."""
    campaign = Campaign(
        creator_id=creator_id,
        title=campaign_in.title,
        goal_amount=campaign_in.goal_amount,
        raised_amount=Decimal("0.00"),
        status=CampaignStatus.OPEN.value
    )
    session.add(campaign)
    session.flush()  # get campaign.id without ending the transaction

    log_event(
        session=session,
        action="CAMPAIGN_CREATED",
        target_type="Campaign",
        actor_id=creator_id,
        target_id=campaign.id
    )

    session.commit()  # ONE commit for the whole business action
    session.refresh(campaign)
    return campaign


def get_campaign_by_id(session: Session, campaign_id: UUID) -> Campaign:
    """Fetches a campaign by UUID or raises an HTTP 404 Exception."""
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    return campaign


def list_campaigns(
    session: Session,
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
) -> List[Campaign]:
    """Retrieves a paginated list of campaigns, optionally filtered by status."""
    statement = select(Campaign)
    if status_filter:
        statement = statement.where(Campaign.status == status_filter)
    statement = statement.order_by(Campaign.created_at.desc()).offset(skip).limit(limit)
    return session.exec(statement).all()


def close_campaign(session: Session, campaign_id: UUID, actor_id: UUID) -> Campaign:
    """Closes an open campaign, as ONE transaction including its audit row."""
    campaign = get_campaign_by_id(session, campaign_id)

    if campaign.status == CampaignStatus.CLOSED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign is already closed"
        )

    campaign.status = CampaignStatus.CLOSED.value
    session.add(campaign)

    log_event(
        session=session,
        action="CAMPAIGN_CLOSED",
        target_type="Campaign",
        actor_id=actor_id,
        target_id=campaign.id
    )

    session.commit()  # ONE commit
    session.refresh(campaign)
    return campaign


def create_pledge(session: Session, pledge_in: PledgeCreate, user_id: UUID) -> Pledge:
    """
    Validates user member status and target campaign availability, then
    creates a pledge and its audit row as ONE transaction.
    """
    statement = select(Member).where(Member.user_id == user_id)
    member = session.exec(statement).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member profile not found for user"
        )

    campaign = get_campaign_by_id(session, pledge_in.campaign_id)
    if campaign.status != CampaignStatus.OPEN.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot pledge to a closed campaign"
        )

    pledge = Pledge(
        member_id=member.id,
        campaign_id=campaign.id,
        amount=pledge_in.amount,
        status=PledgeStatus.PENDING.value
    )
    session.add(pledge)
    session.flush()  # get pledge.id without ending the transaction

    log_event(
        session=session,
        action="PLEDGE_CREATED",
        target_type="Pledge",
        actor_id=user_id,
        target_id=pledge.id
    )

    session.commit()  # ONE commit
    session.refresh(pledge)
    return pledge