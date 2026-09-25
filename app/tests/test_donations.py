"""
Recording donations — the examiner's test list:
    Given a new bank reference, when recorded, then 201 and one donation row.
    Given a bank reference already recorded, when recorded again, then 409
        and totals do not change.                          (see test_hard_problem.py)
    Given the same Idempotency-Key is retried, then 200 with the original response.
    Given a closed campaign, when recording against it, then 409.
"""
from decimal import Decimal

from sqlmodel import select

from app.domains.ledger.models import JournalLine


def test_new_donation_returns_201_and_updates_campaign_total(client, session, donor, auth_headers, open_campaign):
    response = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "20000.00", "bank_ref": "TXN-0001"},
        headers=auth_headers(donor),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "SUCCESS"

    session.refresh(open_campaign)
    assert Decimal(str(open_campaign.raised_amount)) == Decimal("20000.00")


def test_donation_posts_a_balanced_ledger_entry(client, session, donor, auth_headers, open_campaign):
    response = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "12345.00", "bank_ref": "TXN-LEDGER-0001"},
        headers=auth_headers(donor),
    )
    assert response.status_code == 201
    entry_id = response.json()["journal_entry_id"]
    assert entry_id is not None

    lines = session.exec(select(JournalLine).where(JournalLine.journal_entry_id == entry_id)).all()
    total_debits = sum((line.debit for line in lines), Decimal("0.00"))
    total_credits = sum((line.credit for line in lines), Decimal("0.00"))

    assert total_debits == total_credits == Decimal("12345.00")


def test_retrying_same_idempotency_key_and_body_returns_saved_response(client, donor, auth_headers, open_campaign):
    headers = {**auth_headers(donor), "Idempotency-Key": "idem-key-001"}
    body = {"campaign_id": str(open_campaign.id), "amount": "7000.00", "bank_ref": "TXN-IDEM-0001"}

    first = client.post("/v1/donations", json=body, headers=headers)
    second = client.post("/v1/donations", json=body, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json() == second.json()


def test_same_idempotency_key_with_different_body_returns_409(client, donor, auth_headers, open_campaign):
    headers = {**auth_headers(donor), "Idempotency-Key": "idem-key-002"}

    first = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "1000.00", "bank_ref": "TXN-IDEM-0002-A"},
        headers=headers,
    )
    assert first.status_code == 201

    second = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "2000.00", "bank_ref": "TXN-IDEM-0002-B"},
        headers=headers,
    )
    assert second.status_code == 409


def test_donation_against_closed_campaign_returns_409(client, donor, auth_headers, closed_campaign):
    response = client.post(
        "/v1/donations",
        json={"campaign_id": str(closed_campaign.id), "amount": "5000.00", "bank_ref": "TXN-CLOSED-0001"},
        headers=auth_headers(donor),
    )
    assert response.status_code == 409


def test_donation_against_unknown_campaign_returns_404(client, donor, auth_headers):
    import uuid
    response = client.post(
        "/v1/donations",
        json={"campaign_id": str(uuid.uuid4()), "amount": "5000.00", "bank_ref": "TXN-UNKNOWN-0001"},
        headers=auth_headers(donor),
    )
    assert response.status_code == 404


def test_donor_can_list_own_donations(client, donor, auth_headers, open_campaign):
    headers = auth_headers(donor)
    for i in range(3):
        client.post(
            "/v1/donations",
            json={"campaign_id": str(open_campaign.id), "amount": "1000.00", "bank_ref": f"TXN-LIST-{i}"},
            headers=headers,
        )

    response = client.get("/v1/donations/me?skip=0&limit=2", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_donor_cannot_see_another_donors_receipt(client, session, donor, make_user, auth_headers, open_campaign):
    from app.domains.auth.models import UserRole

    other_donor = make_user(UserRole.DONOR)

    donate = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "3000.00", "bank_ref": "TXN-OWNERSHIP-0001"},
        headers=auth_headers(donor),
    )
    donation_id = donate.json()["id"]

    response = client.get(f"/v1/receipts/{donation_id}", headers=auth_headers(other_donor))
    assert response.status_code == 404


def test_unknown_receipt_returns_404(client, donor, auth_headers):
    import uuid
    response = client.get(f"/v1/receipts/{uuid.uuid4()}", headers=auth_headers(donor))
    assert response.status_code == 404
