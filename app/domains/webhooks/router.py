from datetime import datetime

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.deps import get_session
from app.domains.webhooks.service import confirm_payment, verify_signature


router = APIRouter(
    tags=["Webhooks"],
)


class PaymentWebhook(BaseModel):
    event_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    amount: int = Field(ge=0)
    currency: str = Field(min_length=1)
    paid_at: datetime


@router.post("/webhooks/payment")
async def payment_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    session: Session = Depends(get_session),
):
    """
    Receive and securely process payment provider webhooks.
    """

    # Read the exact raw request body.
    # The provider signs these exact bytes.
    raw_body = await request.body()

    # Verify the signature before parsing the JSON.
    verify_signature(raw_body, x_signature)

    # Validate and parse the JSON payload.
    payload = PaymentWebhook.model_validate_json(raw_body)

    return confirm_payment(
        session,
        event_id=payload.event_id,
        event_type=payload.type,
        reference=payload.reference,
        amount=payload.amount,
        currency=payload.currency,
    )