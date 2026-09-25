"""
Accounts & access — register and sign in.
"""


def test_register_creates_donor_account(client):
    response = client.post(
        "/v1/auth/register",
        json={"email": "ada@example.com", "password": "StrongPass123!", "phone": "+2348011112222"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["role"] == "donor"
    assert "password_hash" not in body  # response model must never leak internal fields


def test_register_duplicate_email_returns_409(client):
    payload = {"email": "dupe@example.com", "password": "StrongPass123!"}
    first = client.post("/v1/auth/register", json=payload)
    second = client.post("/v1/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_with_correct_credentials_returns_token(client):
    client.post(
        "/v1/auth/register",
        json={"email": "emeka@example.com", "password": "StrongPass123!"},
    )
    response = client.post(
        "/v1/auth/login",
        json={"email": "emeka@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_with_wrong_password_returns_401(client):
    client.post(
        "/v1/auth/register",
        json={"email": "chidi@example.com", "password": "StrongPass123!"},
    )
    response = client.post(
        "/v1/auth/login",
        json={"email": "chidi@example.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401


def test_login_with_unknown_email_returns_401(client):
    response = client.post(
        "/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever"},
    )
    assert response.status_code == 401
