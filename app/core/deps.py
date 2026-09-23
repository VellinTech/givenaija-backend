from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import InvalidTokenError
from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session
from app.domains.auth.models import User

# Simple "paste a Bearer token" scheme — matches our JSON-body login endpoint,
# unlike OAuth2PasswordBearer which expects a form-encoded username/password
# login (the wrong shape for POST /auth/login's {"email": ..., "password": ...}).
bearer_scheme = HTTPBearer()


def get_current_user(
    session: Session = Depends(get_session),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        # Decode token using application secret and algorithm
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    # Query user record from PostgreSQL
    user = session.get(User, user_id)
    if user is None:
        raise credentials_exception

    return user


def require_roles(allowed_roles: List[str]):

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this role"
            )
        return current_user

    return role_checker