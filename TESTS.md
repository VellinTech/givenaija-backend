# Test plan

56 tests across 9 files, run with `pytest -v` against a real Postgres test
database (see README §9 for setup). Every acceptance-criteria line from the
brief is turned into exactly one test, named after what it proves.

## The hard problem (`tests/test_hard_problem.py`)

The five tests the brief requires to be committed **failing before the code
that makes them pass** (Rule 4). Do not rename these once committed —
they're what an examiner runs first.

| Test | Proves |
|---|---|
| `test_recording_bank_reference_twice_returns_409` | one donation row + 409 on the repeat |
| `test_concurrent_same_bank_ref_exactly_one_succeeds` | two officers, same instant, same reference → one 201, one 409 |
| `test_every_admin_finance_change_adds_one_audit_log_row` | every state-changing action logs exactly once |
| `test_audit_log_update_delete_fails_at_db_level` | `UPDATE`/`DELETE` on `audit_log` rejected by Postgres itself |
| `test_requesting_receipt_twice_returns_same_receipt_number` | receipts are one-time resources, never re-minted |

## Access (`tests/test_access.py`)

| Test | Brief line |
|---|---|
| `test_no_token_on_protected_route_returns_401` | Given no token, when I call a protected route, then 401 |
| `test_no_token_on_audit_log_returns_401` | (same, on the audit log specifically) |
| `test_donor_token_on_audit_log_returns_403` | Given a donor token on the audit log, then 403 |
| `test_donor_token_cannot_create_campaign` | role check on an admin-only route |
| `test_donor_token_cannot_read_financial_statement` | role check on a finance/admin-only route |
| `test_invalid_bearer_token_returns_401` | garbage/expired token is rejected |
| `test_valid_token_reaches_me_endpoint` | positive control — a good token works |

## Auth (`tests/test_auth.py`)

Registration, login, duplicate email, wrong password, unknown email — the
"Accounts & access" user stories, plus a check that the response model
never leaks `password_hash` (clean-code standard: "A response model never
contains password_hash or internal fields nobody asked for").

## Campaigns (`tests/test_campaigns.py`)

Create (admin only), public list/get, 404 on unknown id, close (admin or
finance, donor forbidden), pledge to an open campaign, pledge to a closed
campaign rejected.

## Donations (`tests/test_donations.py`)

| Test | Brief line |
|---|---|
| `test_new_donation_returns_201_and_updates_campaign_total` | Given a new bank reference, when recorded, then 201 and one donation row |
| `test_donation_posts_a_balanced_ledger_entry` | double-entry: debits == credits on every donation |
| `test_retrying_same_idempotency_key_and_body_returns_saved_response` | Given the same Idempotency-Key is retried, then 200 with the original response |
| `test_same_idempotency_key_with_different_body_returns_409` | idempotency key reused with a different payload |
| `test_donation_against_closed_campaign_returns_409` | Given a closed campaign, when recording against it, then 409 |
| `test_donation_against_unknown_campaign_returns_404` | unknown campaign_id |
| `test_donor_can_list_own_donations` | `GET /donations/me` pagination |
| `test_donor_cannot_see_another_donors_receipt` | receipt ownership is enforced |
| `test_unknown_receipt_returns_404` | unknown donation_id |

## Ledger (`tests/test_ledger.py`)

Account creation (finance/admin only, duplicate code → 409), donor forbidden
from listing accounts, unbalanced journal entry rejected (400), balanced
entry accepted (201), unknown entry → 404, and the financial statement
report (currently fails — see the comment in the test file and README §8).

## Audit (`tests/test_audit.py`)

Admin can read the log, finance officer cannot, filtering by `action`,
pagination.

## Webhooks (`tests/test_webhooks.py`)

| Test | Brief line |
|---|---|
| `test_missing_signature_returns_401` / `test_bad_signature_returns_401` | wrong/missing signature → 401 |
| `test_unknown_reference_returns_200_and_is_logged_as_orphan` | unknown reference → 200, logged as orphan |
| `test_duplicate_event_id_for_unknown_reference_is_a_no_op` | idempotency on the orphan path too |
| `test_valid_webhook_confirms_matching_donation` | valid signature confirms the donation |
| `test_duplicate_event_id_for_known_reference_does_not_reprocess` | duplicate event → 200, no change |
| `test_webhook_amount_mismatch_returns_409` | provider amount must match the donation |
| `test_webhook_unsupported_event_type_returns_400` / `test_webhook_unsupported_currency_returns_400` | payload validation |

## SSE (`tests/test_sse.py`)

`test_donation_is_pushed_to_open_campaign_stream` — opens
`GET /campaigns/stream/live`, performs a donation through the normal API,
and asserts the `donation.recorded` event arrives on the stream within one
second, per: "Given a donation is recorded, then every open campaign
stream receives it within one second."
