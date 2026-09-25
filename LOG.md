# LOG

Five lines a day, written by whoever did the work that day, per Rule 3.
This first pass is reconstructed from our own git history (`git log --all
--pretty=format:'%h|%ad|%an|%s' --date=short`) so nothing here is invented —
but you should still read it over and correct anything that doesn't match
your memory of *why*, since the commit messages only tell us *what*.

---

## 2026-09-17 — Project setup

- **Did:** Initial push; scaffolded the project structure, Docker setup,
  and a `/health` endpoint. Fixed `.gitignore` twice after committing
  things we shouldn't have (`80f167f`, `0d7c1c2`).
- **Broke:** Nothing yet — this was scaffolding, no business logic.
- **Learnt:** Get `.gitignore` right *before* the first commit, not after —
  cleaning already-tracked files out of history is more annoying than
  writing the ignore rules up front.
- **Next:** Design review with the brief — draw the ERD and endpoint list
  on paper, write "the hard problem" in our own words, get it signed off
  before writing more code (Rule 1).
- **Who:** Victor — project scaffolding, Docker, health check, gitignore.

## 2026-09-20 — Auth groundwork

- **Did:** First pass at the auth endpoints and dependency/toml fixups.
- **Broke:** Dependency versions needed pinning more than once as the
  project grew (this kept recurring through the following days too).
- **Learnt:** `fastapi[standard]` pulls in more than we needed to think
  about up front (bcrypt, pydantic-settings versions) — worth locking
  versions early rather than chasing incompatibilities later.
- **Next:** Real user/role models, not just an endpoint stub.
- **Who:** Victor — auth endpoint work and `pyproject.toml` fixes.

## 2026-09-22 — Data models

- **Did:** Core SQLModel table definitions ("model created").
- **Broke:** Nothing recorded — mostly additive model work.
- **Learnt:** Deciding the shape of `users` / `members` / roles up front
  saved us from reworking the auth layer later once campaigns and
  donations needed to hang off `Member`, not `User`, directly.
- **Next:** Wire up `HTTPBearer` + role checks, then start on the
  register/login flow for real.
- **Who:** Victor & Anthony (co-authored) — data modeling.

## 2026-09-23 — Auth is real, campaigns exist

- **Did:** `HTTPBearer` dependency and role-based access control
  (`require_roles`); user registration, login and role-based auth models;
  campaign creation, listing, closing, and pledges.
- **Broke:** Nothing that needed a follow-up fix commit the same day — this
  was a genuinely productive day.
- **Learnt:** Keeping `get_current_user` and `require_roles` as reusable
  FastAPI dependencies (rather than checks copy-pasted into each route)
  paid off immediately once campaigns needed the same admin/finance/donor
  distinctions auth already had.
- **Next:** Donations — the part where money and idempotency actually
  matter.
- **Who:** Anthony — HTTPBearer/RBAC, campaign endpoints. Victor —
  registration/login/role models.

## 2026-09-24 — The hard problem, webhooks, audit, Firestore (the big day)

- **Did:** Single-transaction atomicity for donations + audit log, with
  the idempotency-key wiring fixed properly; Alembic migrations, Docker
  config, timezone-aware base model, seed script; webhook domain
  scaffolded; Firestore feeds wired up (`donation_feed`, `activity_feed`);
  service-layer functions for donations; audit events added for every
  action that changes state; SSE stream fixed.
- **Broke:** bcrypt version mismatch broke password hashing until pinned
  (`bcrypt<4.1`); the idempotency signature was wrong on the first pass
  and had to be fixed before it actually prevented duplicate work; SSE
  broke once and needed a dedicated fix commit; renamed `ledeger` →
  `ledger` after noticing the typo in a whole domain folder name.
- **Learnt:** "One transaction per business action" is easy to say and
  easy to get subtly wrong — our first version of `create_donation` was
  committing the donation and the audit log in separate transactions,
  which meant a crash between them could silently produce a donation with
  no audit trail. Fixing that into one transaction was the single most
  important change of the day, and it's the whole point of the hard
  problem.
- **Next:** Turn the "exactly once, audit trail that cannot be edited"
  guarantee into the five committed-failing-first tests the brief
  requires, and prove the append-only guarantee at the database
  permission level, not just in application code.
- **Who:** Victor — atomicity fix, migrations/Docker/seed, Firestore,
  ledger rename, audit events. Anthony — webhook scaffolding, donation
  service functions, audit feed writes, SSE fix.

## 2026-09-25 — Hardening and the webhook

- **Did:** Hardened backend security and financial transaction integrity
  (this is where the `givenaija_app` restricted database role was added —
  `SELECT/INSERT` only on `audit_log`, `UPDATE/DELETE/TRUNCATE` revoked);
  added the secure, idempotent payment webhook (HMAC-SHA256 signature
  verification via `hmac.compare_digest`, `processed_events` table to
  ignore duplicate provider callbacks).
- **Broke:** Nothing new broke, but this is exactly the kind of change
  that needs the hard-problem tests written *before* it, not after — we
  wrote the code first this time and are backfilling the required five
  tests, which is the wrong order per Rule 4 and worth naming honestly
  rather than pretending otherwise.
- **Learnt:** Database-level permission grants are a genuinely different
  (and stronger) kind of guarantee than an application-level check —
  `REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_log FROM givenaija_app`
  holds even if we later write a route that tries to "helpfully" let an
  admin edit a log entry. It's worth understanding *why* that's a
  meaningfully different guarantee before the viva, not just that it
  exists.
- **Next:** Backfill `tests/test_hard_problem.py` and the rest of the
  suite (this took the team from 0 to 56 tests, see `TESTS.md`); fix the
  one-line bug in `generate_financial_statement()`; decide whether
  `POST /donations` should require the finance/admin role; add rate
  limiting and the GitHub Actions workflow before demo day.
- **Who:** Victor — the security hardening commit and the payment
  webhook.

---

### For the next entries

Keep going forward with this same five-line shape, written by whoever
actually did that day's work, in first person. Things worth naming
honestly even when they're not flattering: a commit message like "few
changes" (`971d4d5`) or "harden backend security..." doesn't tell an
examiner *what broke* or *what you learnt* — the two things this log
exists to capture that git history alone doesn't.
