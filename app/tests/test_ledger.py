"""
General ledger: accounts and journal entries. Not one of the brief's five
required hard-problem tests, but the ledger is what the hard problem's
"contract's ledger rows sum to zero" guarantee rests on, so it earns its
own coverage.
"""
from decimal import Decimal


def test_finance_can_create_account(client, finance_officer, auth_headers):
    response = client.post(
        "/v1/ledger/accounts",
        json={"code": "2000", "name": "Accounts Payable", "account_type": "LIABILITY"},
        headers=auth_headers(finance_officer),
    )
    assert response.status_code == 201


def test_duplicate_account_code_returns_409(client, finance_officer, auth_headers):
    headers = auth_headers(finance_officer)
    payload = {"code": "3000", "name": "Equity", "account_type": "EQUITY"}
    client.post("/v1/ledger/accounts", json=payload, headers=headers)
    response = client.post("/v1/ledger/accounts", json=payload, headers=headers)
    assert response.status_code == 409


def test_donor_cannot_list_accounts(client, donor, auth_headers):
    response = client.get("/v1/ledger/accounts", headers=auth_headers(donor))
    assert response.status_code == 403


def test_unbalanced_journal_entry_is_rejected(client, finance_officer, auth_headers):
    headers = auth_headers(finance_officer)
    account_a = client.post(
        "/v1/ledger/accounts", json={"code": "1100", "name": "Cash", "account_type": "ASSET"}, headers=headers
    ).json()
    account_b = client.post(
        "/v1/ledger/accounts", json={"code": "4100", "name": "Revenue", "account_type": "REVENUE"}, headers=headers
    ).json()

    response = client.post(
        "/v1/ledger/entries",
        json={
            "description": "Deliberately unbalanced entry",
            "lines": [
                {"account_id": account_a["id"], "debit": "100.00", "credit": "0.00"},
                {"account_id": account_b["id"], "debit": "0.00", "credit": "90.00"},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_balanced_journal_entry_is_accepted(client, finance_officer, auth_headers):
    headers = auth_headers(finance_officer)
    account_a = client.post(
        "/v1/ledger/accounts", json={"code": "1200", "name": "Cash 2", "account_type": "ASSET"}, headers=headers
    ).json()
    account_b = client.post(
        "/v1/ledger/accounts", json={"code": "4200", "name": "Revenue 2", "account_type": "REVENUE"}, headers=headers
    ).json()

    response = client.post(
        "/v1/ledger/entries",
        json={
            "description": "Balanced entry",
            "lines": [
                {"account_id": account_a["id"], "debit": "500.00", "credit": "0.00"},
                {"account_id": account_b["id"], "debit": "0.00", "credit": "500.00"},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201


def test_unknown_journal_entry_returns_404(client, finance_officer, auth_headers):
    import uuid
    response = client.get(f"/v1/ledger/entries/{uuid.uuid4()}", headers=auth_headers(finance_officer))
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# NOTE FOR THE TEAM: this test currently fails against the code as uploaded.
#
# app/domains/donations/service.py::generate_financial_statement() returns
#     FinancialStatement(
#         total_donations_count=total_count,
#         total_revenue_raised=total_revenue,
#         successful_donations_count=successful_count,
#     )
# but FinancialStatement also requires `failed_donations_count` and
# `generated_at`, which are never passed in -- `failed_count` is computed
# two lines above and then silently dropped. That raises a pydantic
# validation error (500) the moment anyone calls GET /v1/reports/statement.
# Fix is one line: pass failed_donations_count=failed_count and
# generated_at=datetime.now(timezone.utc).isoformat().
# --------------------------------------------------------------------------- #
def test_financial_statement_reports_totals(client, donor, finance_officer, auth_headers, open_campaign):
    client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "9000.00", "bank_ref": "TXN-STATEMENT-0001"},
        headers=auth_headers(donor),
    )

    response = client.get("/v1/reports/statement", headers=auth_headers(finance_officer))
    assert response.status_code == 200
    body = response.json()
    assert body["total_donations_count"] == 1
    assert Decimal(str(body["total_revenue_raised"])) == Decimal("9000.00")
    assert body["successful_donations_count"] == 1
    assert body["failed_donations_count"] == 0
    assert body["generated_at"]
