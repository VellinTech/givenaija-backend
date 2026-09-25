"""
Webhook — the examiner's test list:
    Given a signed webhook, then 200 and the donation is confirmed.
    Given the same event again, then 200 and no change.
    Given a bad signature, then 401.
    Given an unknown reference, then 200 but logged as an orphan.
"""
def _post_webhook(client, raw_body: bytes, signature: str | None):
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Signature"] = signature
    # `content=` sends the exact raw bytes untouched -- required here since
    # the signature covers the exact byte string the provider sent.
    return client.post("/v1/webhooks/payment", content=raw_body, headers=headers)


def test_missing_signature_returns_401(client, webhook_payload):
    raw, _sig = webhook_payload()
    response = _post_webhook(client, raw, signature=None)
    assert response.status_code == 401


def test_bad_signature_returns_401(client, webhook_payload):
    raw, _sig = webhook_payload()
    response = _post_webhook(client, raw, signature="0" * 64)
    assert response.status_code == 401


def test_unknown_reference_returns_200_and_is_logged_as_orphan(client, webhook_payload):
    raw, sig = webhook_payload(reference="NO-SUCH-DONATION")
    response = _post_webhook(client, raw, sig)
    assert response.status_code == 200
    body = response.json()
    assert body["orphan"] is True
    assert body["status"] == "accepted"


def test_duplicate_event_id_for_unknown_reference_is_a_no_op(client, webhook_payload):
    raw, sig = webhook_payload(reference="NO-SUCH-DONATION-2")
    first = _post_webhook(client, raw, sig)
    second = _post_webhook(client, raw, sig)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "already_processed"


def test_valid_webhook_confirms_matching_donation(client, session, donor, auth_headers, open_campaign, webhook_payload):
    donate = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "20000.00", "bank_ref": "TXN-WEBHOOK-0001"},
        headers=auth_headers(donor),
    )
    assert donate.status_code == 201

    raw, sig = webhook_payload(reference="TXN-WEBHOOK-0001", amount=2000000)  # kobo
    response = _post_webhook(client, raw, sig)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["donation_id"] == donate.json()["id"]


def test_duplicate_event_id_for_known_reference_does_not_reprocess(client, donor, auth_headers, open_campaign, webhook_payload):
    donate = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "20000.00", "bank_ref": "TXN-WEBHOOK-0002"},
        headers=auth_headers(donor),
    )
    assert donate.status_code == 201

    raw, sig = webhook_payload(reference="TXN-WEBHOOK-0002", amount=2000000)
    first = _post_webhook(client, raw, sig)
    second = _post_webhook(client, raw, sig)

    assert first.status_code == 200
    assert first.json()["status"] == "processed"
    assert second.status_code == 200
    assert second.json()["status"] == "already_processed"


def test_webhook_amount_mismatch_returns_409(client, donor, auth_headers, open_campaign, webhook_payload):
    donate = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "20000.00", "bank_ref": "TXN-WEBHOOK-0003"},
        headers=auth_headers(donor),
    )
    assert donate.status_code == 201

    # 1,000 kobo == ₦10.00, does not match the ₦20,000.00 donation above
    raw, sig = webhook_payload(reference="TXN-WEBHOOK-0003", amount=1000)
    response = _post_webhook(client, raw, sig)
    assert response.status_code == 409


def test_webhook_unsupported_event_type_returns_400(client, webhook_payload):
    raw, sig = webhook_payload(type="payment.refunded")
    response = _post_webhook(client, raw, sig)
    assert response.status_code == 400


def test_webhook_unsupported_currency_returns_400(client, webhook_payload):
    raw, sig = webhook_payload(currency="USD")
    response = _post_webhook(client, raw, sig)
    assert response.status_code == 400
