"""
Access — the examiner's test list:
    Given no token, when I call a protected route, then 401.
    Given a donor token on the audit log, then 403.
"""


def test_no_token_on_protected_route_returns_401(client, open_campaign):
    response = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "1000.00", "bank_ref": "TXN-NOAUTH"},
    )
    assert response.status_code == 401


def test_no_token_on_audit_log_returns_401(client):
    response = client.get("/v1/admin/audit-log")
    assert response.status_code == 401


def test_donor_token_on_audit_log_returns_403(client, donor, auth_headers):
    response = client.get("/v1/admin/audit-log", headers=auth_headers(donor))
    assert response.status_code == 403


def test_donor_token_cannot_create_campaign(client, donor, auth_headers):
    response = client.post(
        "/v1/campaigns",
        json={"title": "Should not be created", "goal_amount": "1000.00"},
        headers=auth_headers(donor),
    )
    assert response.status_code == 403


def test_donor_token_cannot_read_financial_statement(client, donor, auth_headers):
    response = client.get("/v1/reports/statement", headers=auth_headers(donor))
    assert response.status_code == 403


def test_invalid_bearer_token_returns_401(client):
    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_valid_token_reaches_me_endpoint(client, donor, auth_headers):
    response = client.get("/v1/auth/me", headers=auth_headers(donor))
    assert response.status_code == 200
    assert response.json()["email"] == donor.email
