# GiveNaija — NGO Donations & Members

**Team Mighty Spark — Victor & Anthony**

Record every naira exactly once, with an audit trail nobody can edit.

> **Note on this README:** the sections "The hard problem" and "Why this
> design" are meant to be written in your own words and defended at a
> whiteboard with no notes (Rule 8 / Rule 5). Treat the drafts below as a
> starting point to rewrite in your own voice, not as the final text —
> if it still reads like a manual when you're done editing it, that's the
> signal to go over it again.

---

## 1. What this is

An NGO or church needs to know, beyond argument, that every donation was
counted once, that nobody quietly edited a record after the fact, and that
staff can't recreate a bank transfer twice by accident. GiveNaija is the
backend for that: donors pledge and give to campaigns, a finance officer
records confirmed bank transfers, an admin manages campaigns and reads an
audit log that the database itself will not let anyone edit or delete.

## 2. Setup

### Requirements
- Docker and Docker Compose
- (optional, for running things outside Docker) Python 3.11 and [uv](https://github.com/astral-sh/uv)

### Run it

```bash
docker compose up --build
```

This starts four services: `api` (FastAPI on :8000), `db` (Postgres 15 on
:5432), `redis` (:6379) and `firestore` (the Firestore emulator, on :8080).
A `pgadmin` container is also included for poking at the database
(http://localhost:5050, admin@admin.com / admin123).

Once it's up:

```bash
# Apply migrations (creates tables, then the restricted givenaija_app role)
docker compose exec api alembic upgrade head

# Seed demo accounts (safe to re-run)
docker compose exec api python -m app.db.seed
```

- API root: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

All application routes are mounted under `/v1` (e.g. `POST /v1/auth/login`).

### Running the API outside Docker

```bash
uv sync
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/givenaija"
alembic upgrade head
python -m app.db.seed
fastapi dev app/main.py
```

### Configuration

Everything environment-specific is read from environment variables via
`pydantic-settings` (`app/core/config.py`) — see `.env` for the local
defaults. **Known gap:** this repo currently commits `.env` directly rather
than a `.env.example` with real secrets kept out of git; before this goes
anywhere near a real deploy, swap that around (commit `.env.example`,
`.gitignore` the real `.env`, rotate `WEBHOOK_SECRET`/`SECRET_KEY`/
`PAYSTACK_SECRET_KEY`).

## 3. Demo accounts

Created by `python -m app.db.seed` directly in the database — `POST
/auth/register` only ever creates **donor** accounts by design, so this is
the only way to get a finance or admin login in this project.

| Role    | Email                      | Password          |
|---------|-----------------------------|-------------------|
| Admin   | admin@givenaija.test         | AdminPass123!     |
| Finance | finance@givenaija.test       | FinancePass123!   |
| Donor   | donor@givenaija.test          | DonorPass123!     |

Log in with `POST /v1/auth/login` to get a bearer token, then pass it as
`Authorization: Bearer <token>` on everything else.

## 4. Data model (ERD)

```mermaid
erDiagram
    USERS ||--o| MEMBERS : "has profile"
    USERS ||--o{ CAMPAIGNS : creates
    USERS ||--o{ AUDIT_LOG : "acts as"
    MEMBERS ||--o{ PLEDGES : makes
    MEMBERS ||--o{ DONATIONS : makes
    CAMPAIGNS ||--o{ PLEDGES : receives
    CAMPAIGNS ||--o{ DONATIONS : receives
    DONATIONS ||--|| RECEIPTS : "issues exactly one"
    DONATIONS }o--|| JOURNAL_ENTRIES : "posts one balanced entry"
    JOURNAL_ENTRIES ||--o{ JOURNAL_LINES : contains
    JOURNAL_LINES }o--|| ACCOUNTS : "debits/credits"

    USERS {
        uuid id PK
        string email UK
        string password_hash
        string role "donor | finance | admin"
    }
    MEMBERS {
        uuid id PK
        uuid user_id FK
        string phone
    }
    CAMPAIGNS {
        uuid id PK
        uuid creator_id FK
        string title
        decimal goal_amount
        decimal raised_amount
        string status "OPEN | CLOSED"
    }
    PLEDGES {
        uuid id PK
        uuid member_id FK
        uuid campaign_id FK
        decimal amount
        string status "PENDING | FULFILLED | CANCELLED"
    }
    DONATIONS {
        uuid id PK
        uuid member_id FK
        uuid campaign_id FK
        decimal amount
        string bank_ref UK "the double-counting guard"
        string status "PENDING | SUCCESS | FAILED"
        uuid journal_entry_id
    }
    RECEIPTS {
        uuid id PK
        uuid donation_id FK UK
        string receipt_number UK
    }
    IDEMPOTENCY_KEYS {
        string key PK
        string endpoint
        string body_hash
        string response_json
    }
    PROCESSED_EVENTS {
        string event_id PK
        string event_type
        string reference
    }
    ACCOUNTS {
        uuid id PK
        string code UK
        string name
        string account_type
    }
    JOURNAL_ENTRIES {
        uuid id PK
        string description
        string reference_id
    }
    JOURNAL_LINES {
        uuid id PK
        uuid journal_entry_id FK
        uuid account_id FK
        decimal debit
        decimal credit
    }
    AUDIT_LOG {
        uuid id PK
        uuid actor_id FK
        string action
        string target_type
        uuid target_id
    }
```

`idempotency_keys` and `processed_events` aren't tied to a single table by
foreign key on purpose — they're generic guards keyed by client-supplied
key / provider-supplied event id respectively, reused across whichever
endpoint needs them.

## 5. How a request flows (general shape)

```mermaid
flowchart TD
    A[Client sends HTTPS request] --> B{Within rate limit?}
    B -- No --> B1[429 + Retry-After]
    B -- Yes --> C[Middleware: X-Request-ID + timing]
    C --> D{CORS origin allowed?}
    D -- No --> D1[Blocked by browser]
    D -- Yes --> E[Router /v1 matches path + method]
    E --> F{Bearer JWT valid?}
    F -- No --> F1[401 Unauthorized]
    F -- Yes --> G{Role permits this route?}
    G -- No --> G1[403 Forbidden]
    G -- Yes --> H{Body passes Pydantic validation?}
    H -- No --> H1[422 Unprocessable]
    H -- Yes --> I[Service layer: business rules]
    I --> J{Cache hit? Redis, list endpoints only}
    J -- Yes --> J1[Return cached response]
    J -- No --> K[Postgres transaction: BEGIN ... COMMIT / ROLLBACK]
    K --> L[Audit log row written in the SAME transaction]
    L --> M[Cache version bumped, Firestore feed write, SSE broadcast]
    M --> N[Response model -> status code + X-Request-ID]
```

Middleware for request-id/timing is implemented (`app/main.py`); **rate
limiting (429 + Retry-After) is not implemented yet** — noted as a gap in
§8 below.

## 6. The hard problem — "Exactly once, and an audit trail that cannot be edited"

Two separate guarantees, enforced two different ways because they fail in
two different ways:

**Exactly once.** `donations.bank_ref` is a `UNIQUE` column. Recording the
same bank transfer twice — even from two finance officers clicking "record"
at the same instant — can only ever produce one row: the second INSERT
hits the UNIQUE constraint and the transaction rolls back to a clean 409.
`POST /donations` also accepts an `Idempotency-Key` header for the case
where the *client* retries a request it's unsure went through (a timeout,
a flaky connection): the first request with a given key does the work and
saves its response; every later request with that same key and the same
body gets the saved response back, untouched, instead of re-running
anything.

**An audit trail that cannot be edited.** This isn't application logic —
it's enforced by PostgreSQL permissions. Alembic migration
`a7c9e4f2b1d3_add_app_db_role` creates a dedicated, non-superuser login
role (`givenaija_app`) that the application actually connects as in
`docker-compose.yml`. That role is granted `SELECT, INSERT` on `audit_log`
and explicitly has `UPDATE, DELETE, TRUNCATE` **revoked**. So even a bug in
the application code, or someone with a raw SQL client and the app's own
credentials, physically cannot rewrite history — the database refuses the
statement before it ever touches a row. Every service function that
changes something meaningful (`create_campaign`, `close_campaign`,
`create_pledge`, `create_donation`) writes its `audit_log` row inside the
same transaction as the change it's logging, so there's no code path where
a change happens and the log entry doesn't.

```mermaid
flowchart TD
    A["Finance officer sends POST /v1/donations (bank_ref)"] --> B{Idempotency-Key seen before?}
    B -- Yes, same body --> B1[Return saved response, 200]
    B -- Yes, different body --> B2[409 - key reused with different payload]
    B -- No / not sent --> C[BEGIN transaction]
    C --> D{bank_ref already exists?}
    D -- Yes --> D1[ROLLBACK -> 409]
    D -- No --> E[INSERT donation, UPDATE campaign.raised_amount]
    E --> F{UNIQUE violation on bank_ref? two officers, same instant}
    F -- Yes --> F1[ROLLBACK -> 409, exactly one winner]
    F -- No --> G[INSERT receipt, INSERT audit_log row, post balanced ledger entry]
    G --> H[COMMIT -> 201]
    H --> I[Save Idempotency-Key response, bump cache version, Firestore feed, SSE broadcast]
```

The five required tests for this (in `tests/test_hard_problem.py`, committed
failing before the code that makes them pass, per Rule 4):

1. Recording a bank reference twice → one donation row and a 409 the second time.
2. Two officers recording the same reference at the same time → exactly one succeeds.
3. Every admin/finance change adds exactly one `audit_log` row.
4. `UPDATE` or `DELETE` on `audit_log` fails at the database level.
5. Requesting a receipt twice returns the same receipt number.

## 7. Why this design

- **Double-entry ledger, not a running total.** `campaigns.raised_amount`
  is a convenience counter for the progress bar; the real source of truth
  for money is `journal_lines`, where every donation posts a balanced
  debit (Cash) and credit (that campaign's own revenue account). A balance
  is always something you can recompute by summing rows, never a single
  number you trust blindly — that's what makes a dispute traceable line by
  line instead of "the database says X, believe it."
- **Idempotency keys and UNIQUE constraints solve different problems, so we
  use both.** The UNIQUE constraint on `bank_ref` stops the *business*
  mistake (the same real-world transfer entered twice, by anyone, any way).
  The `Idempotency-Key` header stops the *network* problem (a client that
  legitimately doesn't know whether its last request landed). Relying on
  only one of them would leave a hole: UNIQUE alone doesn't help a client
  that retries with a slightly different-looking request for the same
  transfer; idempotency keys alone don't stop two different staff members
  from independently keying in the same paper receipt.
- **Append-only enforced by the database, not by convention.** "Please
  don't edit the audit log" is not a guarantee. A revoked GRANT is.
  Putting this at the Postgres permission layer means it holds even against
  a bug in our own code, a future teammate who doesn't know the rule, or
  someone with direct database access — not just against a well-behaved
  ORM call.
- **The webhook only confirms; the donation endpoint does the real work.**
  `POST /donations` is what actually creates the donation, moves the
  campaign total, and posts the ledger entry — the payment provider's
  webhook (`POST /webhooks/payment`) exists to confirm that money really
  arrived and to keep the flow safe against retries and forged calls, via
  `hmac.compare_digest` signature verification and a `processed_events`
  table keyed on the provider's `event_id`. An unrecognised `reference` is
  still acknowledged with 200 (so the provider doesn't hammer us with
  retries for something we can't match) but logged as an orphan rather than
  silently dropped.

## 8. What's implemented, and what's still open

**Implemented:** JWT auth with bcrypt-hashed passwords and 3 roles
(donor/finance/admin); campaigns and pledges; donations with idempotency
keys, a UNIQUE `bank_ref` guard, and per-donation receipts; a double-entry
general ledger; an append-only audit log enforced at the Postgres
permission level; a signed, idempotent payment webhook; an SSE stream for
live campaign donations; Redis-cached campaign listing with
version-based invalidation; Firestore feeds for the donation ticker and
admin activity feed; Alembic migrations; Docker Compose for the full stack.

**Known gaps** (tracked honestly rather than swept under the rug — some of
these are caught by the test suite itself):

- `generate_financial_statement()` (`GET /reports/statement`) drops
  `failed_donations_count` and `generated_at` when building its response,
  which fails Pydantic validation. One-line fix — see the comment above
  `test_financial_statement_reports_totals` in `tests/test_ledger.py`.
- `POST /donations` doesn't currently restrict to the finance/admin roles,
  so any authenticated donor can record a "confirmed bank transfer"
  against themselves — the user story describes this as a finance-officer
  action. Worth a `require_roles([...])` before demo day.
- No rate limiting (429 + Retry-After) on sign-in or public endpoints yet.
- No background tasks yet for the donor's thank-you email / receipt email.
- No GitHub Actions workflow yet (tests currently only run locally /
  manually in Docker).
- `.env` is committed directly rather than `.env.example` — fine for a
  shared learning repo, not fine to carry into a real deployment.
- `PATCH /campaigns/{id}/close` returns `400` for an already-closed
  campaign rather than `409`; worth aligning with the rest of the API's
  "one error shape" convention (the `{"error": {"code", "message",
  "request_id"}}` shape isn't wired up as a single global exception
  handler yet either — errors currently come back as FastAPI's default
  `{"detail": ...}`).

## 9. Tests

```bash
uv sync --extra test
export TEST_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/givenaija_test"
createdb givenaija_test   # or: docker compose exec db createdb -U postgres givenaija_test
pytest -v
```

Tests run against a **real Postgres test database**, never against the
production one and never against SQLite — the things worth proving here
(the UNIQUE-constraint race, the revoked database permissions on
`audit_log`) only actually prove anything against real Postgres. See
`tests/conftest.py` for how the test database, roles, and fixtures are
wired up, and `TESTS.md` for the full test list mapped back to the brief's
acceptance criteria.
