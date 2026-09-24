

from typing import Optional
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.core.security import get_password_hash, verify_password
from app.domains.auth.models import User, Member, UserRegister, UserRole


def get_user_by_email(session: Session, email: str) -> Optional[User]:
 
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def create_user_account(session: Session, user_data: UserRegister) -> User:

    existing_user = get_user_by_email(session, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )

    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role=UserRole.DONOR.value


    )
    session.add(user)
    session.commit()
    session.refresh(user)


    member = Member(
        user_id=user.id,
        phone=user_data.phone,
        bio=user_data.bio
    )
    session.add(member)
    session.commit()

    return user


def authenticate_user(session: Session, email: str, password: str) -> User:

    user = get_user_by_email(session, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user