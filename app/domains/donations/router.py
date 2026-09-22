"""
Donations Domain API Routes.

Exposes REST endpoints for creating donations, retrieving receipts,
and viewing financial summary reports.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
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
    Records a monetary donation. Supports Idempotency-Key headers for safe client retries.
    """
    # Check idempotency header if present
    payload_hash = compute_payload_hash(donation_in.dict())
    if idempotency_key:
        check_or_reserve_idempotency_key(
            session=session,
            idempotency_key=idempotency_key,
            endpoint="/donations",
            payload_hash=payload_hash
        )

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

    # Save idempotent response state
    if idempotency_key:
        save_idempotency_response(
            session=session,
            key=idempotency_key,
            endpoint="/donations",
            body_hash=payload_hash,
            response_data=response_data.dict()
        )

    return response_data


@router.get("/donations/me", response_model=List[DonationRead])
def get_my_donations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Retrieves donation history for the authenticated user."""
    donations = service.get_user_donations(session, current_user.id)
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
        for d in donations
    ]


@router.get("/receipts/{receipt_id}", response_model=ReceiptRead)
def get_receipt(
    receipt_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Retrieves receipt details by ID."""
    receipt = service.get_receipt_by_id(session, receipt_id)
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
def get_financial_statement(session: Session = Depends(get_session)):
    """Generates an aggregated financial statement. Restricted to Admin and Finance roles."""
    return service.generate_financial_statement(session)