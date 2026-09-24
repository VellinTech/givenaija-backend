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
from app.domains.campaigns.service import broadcast_campaign_event, bump_campaigns_cache_version
from app.db.firestore import write_donation_feed_entry


# Records a donation: checks member + campaign, blocks duplicate bank_ref,
# updates the campaign total, issues a receipt, writes the audit row,
# invalidates the campaigns cache, and mirrors the event to Firestore.
def create_donation(session: Session, donation_in: DonationCreate, user_id: UUID) -> Donation:
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

    # 8. raised_amount just changed -- invalidate cached campaign list pages
    bump_campaigns_cache_version()

    # 9. Best-effort Firestore feed write for the campaign page's live ticker
    write_donation_feed_entry(str(campaign.id), {
        "donation_id": str(donation.id),
        "campaign_id": str(campaign.id),
        "amount": str(donation.amount),
        "bank_ref": donation.bank_ref,
        "created_at": donation.created_at.isoformat(),
    })

    return donation


# Retrieves all historical donations made by the current authenticated user.
def get_user_donations(session: Session, user_id: UUID) -> List[Donation]:
    statement = (
        select(Donation)
        .join(Member, Donation.member_id == Member.id)
        .where(Member.user_id == user_id)
        .order_by(Donation.created_at.desc())
    )
    return session.exec(statement).all()


# Retrieves a receipt by its own UUID.
def get_receipt_by_id(session: Session, receipt_id: UUID) -> Receipt:
    receipt = session.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )
    return receipt


# Retrieves the receipt for a given donation. Same donation_id always
# returns the same receipt_number -- receipts are issued once, at
# donation time, and never regenerated.
def get_receipt_by_donation_id(session: Session, donation_id: UUID) -> Receipt:
    statement = select(Receipt).where(Receipt.donation_id == donation_id)
    receipt = session.exec(statement).first()
    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found for this donation"
        )
    return receipt


# Generates summary financial metrics, optionally filtered by date range.
def generate_financial_statement(
    session: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> FinancialStatement:
    statement = select(Donation)
    if date_from is not None:
        statement = statement.where(Donation.created_at >= date_from)
    if date_to is not None:
        statement = statement.where(Donation.created_at <= date_to)
    donations = session.exec(statement).all()

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