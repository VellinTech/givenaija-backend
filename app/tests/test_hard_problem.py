"""
The hard problem: "Exactly once, and an audit trail that cannot be edited."

These are the five tests the brief requires to be committed FAILING before
the code that makes them pass (Rule 4 — Tests first for the hard problem).
Keep this file's test names and shape stable; they are what the examiner
will run first.
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from sqlmodel import Session, select
from sqlalchemy.exc import DBAPIError

from app.domains.audit.models import AuditLog
from app.domains.campaigns.models import Campaign
from app.domains.donations.models import Donation


# --------------------------------------------------------------------------- #
# 1. Recording a bank reference twice -> one donation row and a 409 the
#    second time.
# --------------------------------------------------------------------------- #
def test_recording_bank_reference_twice_returns_409(client, session, donor, auth_headers, open_campaign):
    headers = auth_headers(donor)
    body = {
        "campaign_id": str(open_campaign.id),
        "amount": "20000.00",
        "bank_ref": "TXN-DUP-0001",
    }

    first = client.post("/v1/donations", json=body, headers=headers)
    assert first.status_code == 201

    second = client.post("/v1/donations", json=body, headers=headers)
    assert second.status_code == 409

    donations = session.exec(
        select(Donation).where(Donation.bank_ref == "TXN-DUP-0001")
    ).all()
    assert len(donations) == 1

    session.refresh(open_campaign)
    assert Decimal(str(open_campaign.raised_amount)) == Decimal("20000.00")


# --------------------------------------------------------------------------- #
# 2. Two officers recording the same reference at the same time -> exactly
#    one succeeds.
# --------------------------------------------------------------------------- #
def test_concurrent_same_bank_ref_exactly_one_succeeds(client, donor, finance_officer, auth_headers, open_campaign):
    donor_headers = auth_headers(donor)
    finance_headers = auth_headers(finance_officer)

    body = {
        "campaign_id": str(open_campaign.id),
        "amount": "15000.00",
        "bank_ref": "TXN-RACE-0001",
    }

    barrier = threading.Barrier(2)

    def fire(headers):
        barrier.wait()  # line both threads up so the requests overlap
        return client.post("/v1/donations", json=body, headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(fire, donor_headers)
        future_b = pool.submit(fire, finance_headers)
        response_a = future_a.result()
        response_b = future_b.result()

    statuses = sorted([response_a.status_code, response_b.status_code])
    assert statuses == [201, 409]


# --------------------------------------------------------------------------- #
# 3. Every admin/finance change adds exactly one audit_log row.
# --------------------------------------------------------------------------- #
def test_every_admin_finance_change_adds_one_audit_log_row(client, session, admin, auth_headers):
    headers = auth_headers(admin)

    before = session.exec(select(AuditLog)).all()
    assert len(before) == 0

    response = client.post(
        "/v1/campaigns",
        json={"title": "Clean Water for Nsukka", "goal_amount": "500000.00"},
        headers=headers,
    )
    assert response.status_code == 201

    after = session.exec(select(AuditLog)).all()
    assert len(after) == 1
    assert after[0].action == "CAMPAIGN_CREATED"
    assert after[0].actor_id == admin.id
    assert str(after[0].target_id) == response.json()["id"]

    # A second admin action adds exactly one more row, not zero and not several.
    campaign_id = response.json()["id"]
    close_response = client.patch(f"/v1/campaigns/{campaign_id}/close", headers=headers)
    assert close_response.status_code == 200

    after_close = session.exec(select(AuditLog)).all()
    assert len(after_close) == 2
    assert after_close[1].action == "CAMPAIGN_CLOSED"


# --------------------------------------------------------------------------- #
# 4. UPDATE or DELETE on audit_log fails at the database level.
# --------------------------------------------------------------------------- #
def test_audit_log_update_delete_fails_at_db_level(session, app_role_engine, admin):
    from sqlalchemy import text as sql_text

    log = AuditLog(actor_id=admin.id, action="CAMPAIGN_CREATED", target_type="Campaign", target_id=admin.id)
    session.add(log)
    session.commit()
    session.refresh(log)

    with app_role_engine.connect() as conn:
        # The application's own DB role can INSERT/SELECT audit_log (that's
        # how log_event() works) but must never be able to UPDATE or DELETE
        # a row once it's written.
        try:
            conn.execute(
                sql_text("UPDATE audit_log SET action = 'TAMPERED' WHERE id = :id"),
                {"id": str(log.id)},
            )
            conn.commit()
            update_denied = False
        except DBAPIError:
            update_denied = True
            conn.rollback()  # clear the failed-transaction state before the next check

        try:
            conn.execute(sql_text("DELETE FROM audit_log WHERE id = :id"), {"id": str(log.id)})
            conn.commit()
            delete_denied = False
        except DBAPIError:
            delete_denied = True
            conn.rollback()

    assert update_denied, "UPDATE on audit_log must be rejected at the database level"
    assert delete_denied, "DELETE on audit_log must be rejected at the database level"

    # Prove the row really is untouched.
    session.refresh(log)
    assert log.action == "CAMPAIGN_CREATED"


# --------------------------------------------------------------------------- #
# 5. Requesting a receipt twice returns the same receipt number.
# --------------------------------------------------------------------------- #
def test_requesting_receipt_twice_returns_same_receipt_number(client, donor, auth_headers, open_campaign):
    headers = auth_headers(donor)

    donate_response = client.post(
        "/v1/donations",
        json={
            "campaign_id": str(open_campaign.id),
            "amount": "10000.00",
            "bank_ref": "TXN-RECEIPT-0001",
        },
        headers=headers,
    )
    assert donate_response.status_code == 201
    donation_id = donate_response.json()["id"]

    first = client.get(f"/v1/receipts/{donation_id}", headers=headers)
    second = client.get(f"/v1/receipts/{donation_id}", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["receipt_number"] == second.json()["receipt_number"]
