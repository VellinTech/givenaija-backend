

from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from app.core.deps import get_session, get_current_user
from app.core.security import create_access_token
from app.domains.auth.models import UserRegister, UserLogin, UserRead, Token, User
from app.domains.auth import service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, session: Session = Depends(get_session)):
  
    user = service.create_user_account(session, user_in)
    return user


@router.post("/login", response_model=Token)
def login(user_in: UserLogin, session: Session = Depends(get_session)):
  
    user = service.authenticate_user(session, user_in.email, user_in.password)
    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
   
    return current_user