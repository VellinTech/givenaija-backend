"""
One-command seed script.

Creates demo accounts directly in the database, bypassing the public
/auth/register endpoint (which only ever creates DONOR accounts by design).
This is the only supported way to get admin/finance users in this project.

Usage:
    python -m app.db.seed

Safe to re-run: existing users (matched by email) are left untouched.
"""

from sqlmodel import Session, select

from app.db.session import engine
from app.core.security import get_password_hash
from app.domains.auth.models import User, Member, UserRole


# (email, password, role, phone)
SEED_USERS = [
    ("admin@givenaija.test", "AdminPass123!", UserRole.ADMIN, None),
    ("finance@givenaija.test", "FinancePass123!", UserRole.FINANCE, None),
    ("donor@givenaija.test", "DonorPass123!", UserRole.DONOR, "+2348000000000"),
]


def seed_user(session: Session, email: str, password: str, role: UserRole, phone: str | None) -> None:
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        print(f"  skip  {email} (already exists, role={existing.role})")
        return

    user = User(
        email=email,
        password_hash=get_password_hash(password),
        role=role.value,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    member = Member(user_id=user.id, phone=phone, bio=None)
    session.add(member)
    session.commit()

    print(f"  create {email}  role={role.value}  password={password}")


def main() -> None:
    print("Seeding demo accounts...")
    with Session(engine) as session:
        for email, password, role, phone in SEED_USERS:
            seed_user(session, email, password, role, phone)
    print("Done. Log in via POST /v1/auth/login with any of the emails above.")


if __name__ == "__main__":
    main()