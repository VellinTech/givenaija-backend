"""
Campaigns Domain API Routes.

Exposes REST endpoints for campaign lifecycle management, pledge execution,
and real-time Server-Sent Events (SSE) streaming updates.
"""

import asyncio
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.core.deps import get_session, get_current_user, require_roles
from app.domains.auth.models import User, UserRole
from app.domains.campaigns.models import CampaignCreate, CampaignRead, PledgeCreate, PledgeRead
from app.domains.campaigns import service

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(
    campaign_in: CampaignCreate,
    session: Session = Depends(get_session),

current_user: User = Depends(require_roles([UserRole.ADMIN.value]))
):
    """Creates a new campaign. Accessible by authenticated users."""
    campaign = service.create_campaign(session, campaign_in, current_user.id)
    return CampaignRead(
        id=campaign.id,
        creator_id=campaign.creator_id,
        title=campaign.title,
        goal_amount=campaign.goal_amount,
        raised_amount=campaign.raised_amount,
        status=campaign.status,
        created_at=campaign.created_at.isoformat()
    )


@router.get("", response_model=List[CampaignRead])
def list_campaigns(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session)
):
    """Fetches a paginated list of campaigns."""
    campaigns = service.list_campaigns(session, skip, limit)
    return [
        CampaignRead(
            id=c.id,
            creator_id=c.creator_id,
            title=c.title,
            goal_amount=c.goal_amount,
            raised_amount=c.raised_amount,
            status=c.status,
            created_at=c.created_at.isoformat()
        )
        for c in campaigns
    ]


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: UUID, session: Session = Depends(get_session)):
    """Retrieves details of a specific campaign by ID."""
    campaign = service.get_campaign_by_id(session, campaign_id)
    return CampaignRead(
        id=campaign.id,
        creator_id=campaign.creator_id,
        title=campaign.title,
        goal_amount=campaign.goal_amount,
        raised_amount=campaign.raised_amount,
        status=campaign.status,
        created_at=campaign.created_at.isoformat()
    )


@router.patch("/{campaign_id}/close", response_model=CampaignRead)
def close_campaign(
    campaign_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles([UserRole.ADMIN.value, UserRole.FINANCE.value]))
):
    """Closes a campaign. Restricted to Admin and Finance roles."""
    campaign = service.close_campaign(session, campaign_id, current_user.id)
    return CampaignRead(
        id=campaign.id,
        creator_id=campaign.creator_id,
        title=campaign.title,
        goal_amount=campaign.goal_amount,
        raised_amount=campaign.raised_amount,
        status=campaign.status,
        created_at=campaign.created_at.isoformat()
    )


@router.post("/pledges", response_model=PledgeRead, status_code=status.HTTP_201_CREATED)
def create_pledge(
    pledge_in: PledgeCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Registers a pledge toward an active campaign."""
    pledge = service.create_pledge(session, pledge_in, current_user.id)
    return PledgeRead(
        id=pledge.id,
        member_id=pledge.member_id,
        campaign_id=pledge.campaign_id,
        amount=pledge.amount,
        status=pledge.status,
        created_at=pledge.created_at.isoformat()
    )


@router.get("/stream/live", response_class=StreamingResponse)
async def stream_campaign_events():
    """
    Server-Sent Events (SSE) endpoint providing real-time ticker updates for campaign events.
    """
    queue: asyncio.Queue = asyncio.Queue()
    service._sse_subscribers.append(queue)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            if queue in service._sse_subscribers:
                service._sse_subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")