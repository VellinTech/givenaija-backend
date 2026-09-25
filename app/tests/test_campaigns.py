"""
Control & records — campaigns and pledges.
"""
from decimal import Decimal


def test_admin_can_create_campaign(client, admin, auth_headers):
    response = client.post(
        "/v1/campaigns",
        json={"title": "School Roof Repair", "goal_amount": "300000.00"},
        headers=auth_headers(admin),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "OPEN"
    assert Decimal(str(body["raised_amount"])) == Decimal("0.00")


def test_list_campaigns_is_public(client, open_campaign):
    response = client.get("/v1/campaigns")
    assert response.status_code == 200
    assert any(c["id"] == str(open_campaign.id) for c in response.json())


def test_get_campaign_by_id(client, open_campaign):
    response = client.get(f"/v1/campaigns/{open_campaign.id}")
    assert response.status_code == 200
    assert response.json()["title"] == open_campaign.title


def test_get_unknown_campaign_returns_404(client):
    import uuid
    response = client.get(f"/v1/campaigns/{uuid.uuid4()}")
    assert response.status_code == 404


def test_admin_can_close_open_campaign(client, admin, auth_headers, open_campaign):
    response = client.patch(f"/v1/campaigns/{open_campaign.id}/close", headers=auth_headers(admin))
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


def test_finance_can_close_campaign(client, finance_officer, auth_headers, open_campaign):
    response = client.patch(f"/v1/campaigns/{open_campaign.id}/close", headers=auth_headers(finance_officer))
    assert response.status_code == 200


def test_donor_cannot_close_campaign(client, donor, auth_headers, open_campaign):
    response = client.patch(f"/v1/campaigns/{open_campaign.id}/close", headers=auth_headers(donor))
    assert response.status_code == 403


def test_member_can_pledge_to_open_campaign(client, donor, auth_headers, open_campaign):
    response = client.post(
        "/v1/campaigns/pledges",
        json={"campaign_id": str(open_campaign.id), "amount": "5000.00"},
        headers=auth_headers(donor),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"


def test_pledge_to_closed_campaign_is_rejected(client, donor, auth_headers, closed_campaign):
    response = client.post(
        "/v1/campaigns/pledges",
        json={"campaign_id": str(closed_campaign.id), "amount": "5000.00"},
        headers=auth_headers(donor),
    )
    assert response.status_code in (400, 409)
