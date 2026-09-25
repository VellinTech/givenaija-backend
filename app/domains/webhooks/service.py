import hashlib
import hmac
import logging
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.domains.donations.models import Donation, DonationStatus
from app.domains.webhooks.models import ProcessedEvent


logger = logging.getLogger(__name__)


def verify_signature(raw_body: bytes, signature: str | None) -> None:
    """
    Verify the payment provider's HMAC-SHA256 signature.

    The provider signs the exact raw request body, so verification
    must happen before parsing or modifying the JSON payload.
    """

    if not signature:
        raise HTTPException(
            status_code=401,
            detail="Missing webhook signature",
        )

    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        )


def reserve_event(
    session: Session,
    event_id: str,
    event_type: str,
    reference: str,
) -> bool:
    """
    Atomically reserve a webhook event.

    Returns:
        True  -> this is a new event
        False -> this event was already processed
    """

    statement = text(
        """
        INSERT INTO processed_events
            (event_id, event_type, reference, processed_at)
        VALUES
            (:event_id, :event_type, :reference, NOW())
        ON CONFLICT (event_id) DO NOTHING
        """
    )

    result = session.execute(
        statement,
        {
            "event_id": event_id,
            "event_type": event_type,
            "reference": reference,
        },
    )

    return result.rowcount == 1


def confirm_payment(
    session: Session,
    *,
    event_id: str,
    event_type: str,
    reference: str,
    amount: int,
    currency: str,
) -> dict:
    """
    Process a successful payment webhook.

    The provider sends monetary amounts in the smallest currency unit.
    For NGN, this means kobo, so 45000 becomes ₦450.00.

    IMPORTANT:
    This function does NOT create a new donation, receipt, ledger
    entry, or campaign increment. Those financial side effects are
    already handled by the donation service.
    """

    if event_type != "payment.succeeded":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported webhook event type: {event_type}",
        )

    if currency.upper() != "NGN":
        raise HTTPException(
            status_code=400,
            detail="Unsupported payment currency",
        )

    if amount < 0:
        raise HTTPException(
            status_code=400,
            detail="Payment amount cannot be negative",
        )

    donation = session.exec(
        select(Donation).where(
            Donation.bank_ref == reference
        )
    ).first()

    # Unknown payment reference.
    # We intentionally acknowledge the webhook so the provider does
    # not retry an event that GiveNaija cannot associate with a donation.
    if not donation:
        logger.warning(
            "Received payment webhook for unknown reference: %s",
            reference,
        )

        is_new_event = reserve_event(
            session,
            event_id=event_id,
            event_type=event_type,
            reference=reference,
        )

        if not is_new_event:
            session.rollback()

            return {
                "status": "already_processed",
                "event_id": event_id,
                "reference": reference,
                "orphan": True,
            }

        session.commit()

        return {
            "status": "accepted",
            "event_id": event_id,
            "reference": reference,
            "orphan": True,
        }    
 
    # Provider amount is in kobo; donation.amount is stored in naira.
    provider_amount = (
        Decimal(amount) / Decimal("100")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    if provider_amount != donation.amount:
        raise HTTPException(
            status_code=409,
            detail=(
                "Payment amount does not match donation amount"
            ),
        )

    is_new_event = reserve_event(
        session,
        event_id=event_id,
        event_type=event_type,
        reference=reference,
    )

    if not is_new_event:
        session.rollback()

        return {
            "status": "already_processed",
            "event_id": event_id,
            "reference": reference,
            "donation_id": str(donation.id),
        }

    # The donation already exists and its financial effects have
    # already been posted by the donation service.
    #
    # We only confirm its payment status here.
    donation.status = DonationStatus.SUCCESS.value
    session.add(donation)

    session.commit()
    session.refresh(donation)

    logger.info(
        "Payment webhook processed successfully: event_id=%s reference=%s",
        event_id,
        reference,
    )

    return {
        "status": "processed",
        "event_id": event_id,
        "reference": reference,
        "donation_id": str(donation.id),
    }