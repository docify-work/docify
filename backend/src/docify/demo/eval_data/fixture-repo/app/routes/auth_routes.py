from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.db import get_session
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str


@router.post("/signup", status_code=201)
def signup(body: Credentials, db: Session = Depends(get_session)):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return {"id": user.id}


@router.post("/login")
def login(body: Credentials, db: Session = Depends(get_session)):
    user = db.query(User).filter_by(email=body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}
