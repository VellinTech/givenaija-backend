"""
Audit log — reading and filtering. The append-only guarantee itself is
covered by test_hard_problem.py::test_audit_log_update_delete_fails_at_db_level.
"""


def test_admin_can_read_audit_log(client, admin, auth_headers):
    headers = auth_headers(admin)
    client.post("/v1/campaigns", json={"title": "Feed the Homeless", "goal_amount": "100000.00"}, headers=headers)

    response = client.get("/v1/admin/audit-log", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["action"] == "CAMPAIGN_CREATED"


def test_finance_officer_cannot_read_audit_log(client, finance_officer, auth_headers):
    # Only admin reads the audit log in this design; finance officers
    # record money but do not get to inspect who-did-what.
    response = client.get("/v1/admin/audit-log", headers=auth_headers(finance_officer))
    assert response.status_code == 403


def test_audit_log_can_be_filtered_by_action(client, admin, auth_headers, open_campaign):
    headers = auth_headers(admin)
    client.patch(f"/v1/campaigns/{open_campaign.id}/close", headers=headers)
    client.post("/v1/campaigns", json={"title": "Another one", "goal_amount": "50000.00"}, headers=headers)

    response = client.get("/v1/admin/audit-log?action=CAMPAIGN_CLOSED", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["action"] == "CAMPAIGN_CLOSED"


def test_audit_log_pagination(client, admin, auth_headers):
    headers = auth_headers(admin)
    for i in range(5):
        client.post("/v1/campaigns", json={"title": f"Campaign {i}", "goal_amount": "1000.00"}, headers=headers)

    response = client.get("/v1/admin/audit-log?skip=0&limit=2", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2
