
import hashlib
import hmac
import json
import os
import uuid
from decimal import Decimal
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

# Import every domain's models so SQLModel.metadata knows about all tables
# before create_all() runs. Importing app.main pulls in the routers, which
# in turn import the services, which import the models -- but doing it
# explicitly here is what actually guarantees registration order.
from app.domains.auth.models import User, Member, UserRole
from app.domains.campaigns.models import Campaign, Pledge
from app.domains.donations.models import Donation, Receipt, IdempotencyKey
from app.domains.ledger.models import Account, JournalEntry, JournalLine
from app.domains.audit.models import AuditLog
from app.domains.webhooks.models import ProcessedEvent

from app.core.config import settings
from app.core.security import get_password_hash, create_access_token
from app.db.session import get_session
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/givenaija_test",
)

APP_ROLE = "givenaija_app"
APP_ROLE_PASSWORD = "givenaija_app_password"


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, echo=False)
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(autouse=True)
def clean_tables(engine):
    """
    Truncate every table before each test so tests don't leak state into
    one another (each test sets up its own data, per the project's testing
    standard).
    """
    with engine.connect() as conn:
        conn.execute(text("SET session_replication_role = 'replica';"))
        for table in reversed(SQLModel.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE;'))
        conn.execute(text("SET session_replication_role = 'origin';"))
        conn.commit()
    yield


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine) -> Iterator[TestClient]:
    def _get_test_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _get_test_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Users & auth
# --------------------------------------------------------------------------- #

def _make_user(session: Session, role: UserRole, email: str | None = None) -> User:
    """
    Creates a user + member profile directly in the DB, the same way
    app/db/seed.py does it. This is required for finance/admin accounts
    because POST /auth/register always creates DONOR accounts by design.
    """
    email = email or f"{role.value}-{uuid.uuid4().hex[:8]}@givenaija.test"
    user = User(
        email=email,
        password_hash=get_password_hash("Password123!"),
        role=role.value,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    member = Member(user_id=user.id, phone=None, bio=None)
    session.add(member)
    session.commit()

    return user


@pytest.fixture
def make_user(session):
    """Factory fixture: make_user(UserRole.DONOR) -> User"""
    def _factory(role: UserRole = UserRole.DONOR, email: str | None = None) -> User:
        return _make_user(session, role, email)
    return _factory


@pytest.fixture
def donor(session) -> User:
    return _make_user(session, UserRole.DONOR)


@pytest.fixture
def finance_officer(session) -> User:
    return _make_user(session, UserRole.FINANCE)


@pytest.fixture
def admin(session) -> User:
    return _make_user(session, UserRole.ADMIN)


@pytest.fixture
def auth_headers():
    """auth_headers(user) -> {"Authorization": "Bearer ..."}"""
    def _factory(user: User) -> dict:
        token = create_access_token(subject=user.id)
        return {"Authorization": f"Bearer {token}"}
    return _factory


# --------------------------------------------------------------------------- #
# Campaigns / donations helpers
# --------------------------------------------------------------------------- #

@pytest.fixture
def open_campaign(session, admin):
    campaign = Campaign(
        creator_id=admin.id,
        title="Borehole for Ikot Ekpene",
        goal_amount=Decimal("2000000.00"),
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@pytest.fixture
def closed_campaign(session, admin):
    campaign = Campaign(
        creator_id=admin.id,
        title="Borehole (closed)",
        goal_amount=Decimal("2000000.00"),
        status="CLOSED",
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


# --------------------------------------------------------------------------- #
# Webhook signing
# --------------------------------------------------------------------------- #

def sign_payload(raw_body: bytes) -> str:
    """Signs a raw request body the way the payment provider's mock does."""
    return hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


@pytest.fixture
def webhook_payload():
    """webhook_payload(**overrides) -> (raw_body_bytes, signature_header)"""
    def _factory(**overrides) -> tuple[bytes, str]:
        body = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "type": "payment.succeeded",
            "reference": "UNKNOWN-REF",
            "amount": 2000000,  # kobo => ₦20,000.00
            "currency": "NGN",
            "paid_at": "2026-09-25T10:00:00+00:00",
        }
        body.update(overrides)
        raw = json.dumps(body).encode("utf-8")
        return raw, sign_payload(raw)
    return _factory


# --------------------------------------------------------------------------- #
# Raw DB role connection, for proving audit_log is append-only at the DB level
# --------------------------------------------------------------------------- #

@pytest.fixture
def app_role_engine(engine):
    """
    Provisions the restricted `givenaija_app` role against the TEST database
    (the same grants alembic migration a7c9e4f2b1d3 applies in production),
    yields an engine connected AS that role, and tears the role down again.

    This makes the append-only guarantee testable without requiring the
    test database to have alembic migrations pre-applied.
    """
    with engine.connect() as conn:
        conn.execute(text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_ROLE_PASSWORD}'
                        NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
                END IF;
            END $$;
        """))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE};"))
        conn.execute(text(f"""
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};
        """))
        conn.execute(text(f"GRANT SELECT, INSERT ON TABLE audit_log TO {APP_ROLE};"))
        conn.execute(text(f"REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_log FROM {APP_ROLE};"))
        conn.commit()

    role_url = TEST_DATABASE_URL.replace(
        "postgresql+psycopg://postgres:postgres@",
        f"postgresql+psycopg://{APP_ROLE}:{APP_ROLE_PASSWORD}@",
    )
    role_engine = create_engine(role_url)
    yield role_engine
    role_engine.dispose()

    with engine.connect() as conn:
        conn.execute(text(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {APP_ROLE};"))
        conn.execute(text(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE};"))
        conn.commit()
