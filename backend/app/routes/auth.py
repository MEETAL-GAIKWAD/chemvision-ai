from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import TokenResponse, UserCreate, UserLogin


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        field_of_study=payload.field_of_study,
        institution=payload.institution,
        learning_focus=payload.learning_focus,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(str(user.id)), "user": user}


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive.")
    return {"access_token": create_access_token(str(user.id)), "user": user}
