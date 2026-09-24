import asyncio
import json
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.core.deps import get_session, get_current_user, require_roles
from app.db.redis import get_redis
from app.domains.auth.models import User, UserRole
from app.domains.campaigns.models import CampaignCreate, CampaignRead, PledgeCreate, PledgeRead
from app.domains.campaigns import service

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

CAMPAIGNS_CACHE_TTL_SECONDS = 30


# Creates a new campaign. Restricted to Admin role.
@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(
    campaign_in: CampaignCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles([UserRole.ADMIN.value]))
):
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


# Fetches a paginated list of campaigns.
@router.get("", response_model=List[CampaignRead])
def list_campaigns(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session)
):
    # Cache key embeds the current version number. Any write that affects
    # campaigns bumps that version, so old cached keys just stop getting
    # hit and expire naturally -- no need to hunt down and delete them.
    r = get_redis()
    cache_key = None
    try:
        version = r.get("campaigns:cache_version") or "0"
        cache_key = f"campaigns:list:v{version}:{skip}:{limit}"
        cached = r.get(cache_key)
        if cached is not None:
            return [CampaignRead(**item) for item in json.loads(cached)]
    except Exception as exc:
        print(f"[redis] cache read failed, falling back to DB (non-fatal): {exc}")

    campaigns = service.list_campaigns(session, skip, limit)
    result = [
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

    if cache_key is not None:
        try:
            r.setex(cache_key, CAMPAIGNS_CACHE_TTL_SECONDS, json.dumps([item.dict() for item in result], default=str))
        except Exception as exc:
            print(f"[redis] cache write failed (non-fatal): {exc}")

    return result


# Retrieves details of a specific campaign by ID.
@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: UUID, session: Session = Depends(get_session)):
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


# Closes a campaign. Restricted to Admin and Finance roles.
@router.patch("/{campaign_id}/close", response_model=CampaignRead)
def close_campaign(
    campaign_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles([UserRole.ADMIN.value, UserRole.FINANCE.value]))
):
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


# Registers a pledge toward an active campaign.
@router.post("/pledges", response_model=PledgeRead, status_code=status.HTTP_201_CREATED)
def create_pledge(
    pledge_in: PledgeCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pledge = service.create_pledge(session, pledge_in, current_user.id)
    return PledgeRead(
        id=pledge.id,
        member_id=pledge.member_id,
        campaign_id=pledge.campaign_id,
        amount=pledge.amount,
        status=pledge.status,
        created_at=pledge.created_at.isoformat()
    )


# SSE endpoint for live campaign ticker updates.
@router.get("/stream/live", response_class=StreamingResponse)
async def stream_campaign_events():
    queue: asyncio.Queue = asyncio.Queue()
    service._sse_subscribers.append(queue)

    async def event_generator():
        try:
            while True:
                try:
                    # 15s heartbeat so proxies don't kill an idle connection
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            if queue in service._sse_subscribers:
                service._sse_subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")