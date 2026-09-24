"""
Donations Domain API Routes.

Exposes REST endpoints for creating donations, retrieving receipts,
and viewing financial summary reports.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query, status
from sqlmodel import Session

from app.core.deps import get_session, get_current_user, require_roles
from app.core.idempotency import compute_payload_hash, check_or_reserve_idempotency_key, save_idempotency_response
from app.domains.auth.models import User, UserRole
from app.domains.donations.models import DonationCreate, DonationRead, ReceiptRead, FinancialStatement
from app.domains.donations import service

router = APIRouter(tags=["Donations & Reports"])


@router.post("/donations", response_model=DonationRead, status_code=status.HTTP_201_CREATED)
def create_donation(
    donation_in: DonationCreate,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Records a monetary donation. Supports Idempotency-Key headers for safe
    client retries: retrying the exact same request with the same key
    returns the ORIGINAL response, unchanged, without re-running the
    business logic a second time.
    """
    payload_dict = donation_in.dict()

    if idempotency_key:
        cached_response = check_or_reserve_idempotency_key(
            session=session,
            key=idempotency_key,
            endpoint="/donations",
            payload=payload_dict,
        )
        if cached_response is not None:
            # Same key + same payload as a previous request — short-circuit
            # and return the exact original response. Do NOT re-run
            # service.create_donation(), or the bank_ref UNIQUE check would
            # incorrectly reject this as a duplicate.
            return cached_response

    donation = service.create_donation(session, donation_in, current_user.id)

    response_data = DonationRead(
        id=donation.id,
        member_id=donation.member_id,
        campaign_id=donation.campaign_id,
        amount=donation.amount,
        bank_ref=donation.bank_ref,
        status=donation.status,
        created_at=donation.created_at.isoformat()
    )

    if idempotency_key:
        save_idempotency_response(
            session=session,
            key=idempotency_key,
            endpoint="/donations",
            payload=payload_dict,
            response_data=response_data.dict(),
        )
        session.commit()

    return response_data


@router.get("/donations/me", response_model=List[DonationRead])
def get_my_donations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Retrieves paginated donation history for the authenticated user."""
    donations = service.get_user_donations(session, current_user.id)
    paginated = donations[skip: skip + limit]
    return [
        DonationRead(
            id=d.id,
            member_id=d.member_id,
            campaign_id=d.campaign_id,
            amount=d.amount,
            bank_ref=d.bank_ref,
            status=d.status,
            created_at=d.created_at.isoformat()
        )
        for d in paginated
    ]


@router.get("/receipts/{donation_id}", response_model=ReceiptRead)
def get_receipt(
    donation_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the receipt for a given donation. Asking for the same
    donation_id repeatedly always returns the same receipt_number.

    NOTE: an ownership check (only the donor who made this donation, or a
    finance/admin user, may view it) is not yet enforced here — see the
    project audit document, Part 3.9, for the follow-up fix.
    """
    receipt = service.get_receipt_by_donation_id(session, donation_id)
    return ReceiptRead(
        id=receipt.id,
        donation_id=receipt.donation_id,
        receipt_number=receipt.receipt_number,
        issued_at=receipt.issued_at.isoformat()
    )


@router.get(
    "/reports/statement",
    response_model=FinancialStatement,
    dependencies=[Depends(require_roles([UserRole.ADMIN.value, UserRole.FINANCE.value]))]
)
def get_financial_statement(
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = Query(default=None),
    session: Session = Depends(get_session),
):
    """
    Generates an aggregated financial statement, optionally filtered by date
    range (?from=2026-01-01&to=2026-01-31). Restricted to finance/admin.
    """
    return service.generate_financial_statement(session, date_from=from_, date_to=to)