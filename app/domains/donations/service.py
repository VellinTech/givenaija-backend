"""
Donations Domain Business Logic.

Handles transaction processing, unique bank reference validation, goal incrementing,
receipt generation, and financial reporting.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4
from fastapi import HTTPException, status
from sqlmodel import Session, select, func

from app.domains.donations.models import Donation, DonationCreate, DonationStatus, Receipt, FinancialStatement
from app.domains.campaigns.models import Campaign, CampaignStatus
from app.domains.auth.models import Member
from app.domains.audit.service import log_event
from app.domains.campaigns.service import broadcast_campaign_event


def create_donation(session: Session, donation_in: DonationCreate, user_id: UUID) -> Donation:
    """
    Executes a donation entry:
    1. Validates donor member profile.
    2. Validates target campaign active status.
    3. Checks bank reference uniqueness to eliminate double-counting.
    4. Updates campaign raised_amount cached value atomically.
    5. Issues proof of payment receipt.
    """
    # 1. Fetch member entity
    statement = select(Member).where(Member.user_id == user_id)
    member = session.exec(statement).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member profile required to make a donation"
        )

    # 2. Fetch target campaign
    campaign = session.get(Campaign, donation_in.campaign_id)
    if not campaign or campaign.status != CampaignStatus.OPEN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target campaign is invalid or closed"
        )

    # 3. Prevent duplicate processing via unique bank_ref check
    dup_check = select(Donation).where(Donation.bank_ref == donation_in.bank_ref)
    if session.exec(dup_check).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Donation with bank reference '{donation_in.bank_ref}' has already been processed"
        )

    # 4. Save successful donation
    donation = Donation(
        member_id=member.id,
        campaign_id=campaign.id,
        amount=donation_in.amount,
        bank_ref=donation_in.bank_ref,
        status=DonationStatus.SUCCESS.value
    )
    session.add(donation)

    # 5. Increment campaign raised amount
    campaign.raised_amount += donation_in.amount
    session.add(campaign)

    session.commit()
    session.refresh(donation)

    # 6. Generate receipt entity
    receipt_number = f"REC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
    receipt = Receipt(
        donation_id=donation.id,
        receipt_number=receipt_number
    )
    session.add(receipt)
    session.commit()

    # 7. Write audit record
    log_event(
        session=session,
        action="DONATION_SUCCESSFUL",
        target_type="Donation",
        actor_id=user_id,
        target_id=donation.id
    )

    return donation


def get_user_donations(session: Session, user_id: UUID) -> List[Donation]:
    """Retrieves all historical donations made by the current authenticated user."""
    statement = (
        select(Donation)
        .join(Member, Donation.member_id == Member.id)
        .where(Member.user_id == user_id)
        .order_by(Donation.created_at.desc())
    )
    return session.exec(statement).all()


def get_receipt_by_id(session: Session, receipt_id: UUID) -> Receipt:
    """Retrieves a receipt by its UUID or raises HTTP 404."""
    receipt = session.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )
    return receipt


def generate_financial_statement(session: Session) -> FinancialStatement:
    """Generates high-level financial summary metrics across all donations."""
    donations = session.exec(select(Donation)).all()
    
    total_count = len(donations)
    successful_count = sum(1 for d in donations if d.status == DonationStatus.SUCCESS.value)
    failed_count = sum(1 for d in donations if d.status == DonationStatus.FAILED.value)
    total_revenue = sum((d.amount for d in donations if d.status == DonationStatus.SUCCESS.value), Decimal("0.00"))

    return FinancialStatement(
        total_donations_count=total_count,
        total_revenue_raised=total_revenue,
        successful_donations_count=successful_count,
        failed_donations_count=failed_count,
        generated_at=datetime.utcnow().isoformat()
    )