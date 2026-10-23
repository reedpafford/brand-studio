"""First-run setup, login, logout, accepting an invite, and "who am I"."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import (
    check_password,
    current_user,
    end_session,
    hash_password,
    hash_token,
    start_session,
)
from app.db import get_db, utcnow
from app.models.accounts import Invite, Role, User, Workspace
from app.schemas import Email, Name, Password

router = APIRouter(prefix="/auth", tags=["auth"])


class Me(BaseModel):
    id: int
    email: str
    name: str
    role: Role
    workspace_id: int


class SetupIn(BaseModel):
    setup_token: str
    workspace_name: Name
    email: Email
    name: Name
    password: Password


class LoginIn(BaseModel):
    email: Email
    password: str


class AcceptIn(BaseModel):
    token: str
    name: Name
    password: Password


@router.post("/setup", response_model=Me, status_code=201)
def setup(body: SetupIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create the workspace and its owner. Works once, and only with the server's setup token."""
    expected = request.app.state.settings.setup_token
    if not expected or not secrets.compare_digest(body.setup_token, expected):
        raise HTTPException(403, "Setup is not allowed.")
    if db.scalar(select(func.count(User.id))):
        raise HTTPException(409, "Already set up.")
    workspace = Workspace(name=body.workspace_name)
    user = User(
        workspace=workspace,
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role=Role.owner,
    )
    db.add(user)
    db.commit()
    start_session(db, request, response, user)
    return user


@router.post("/login", response_model=Me)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email, User.active))
    if not check_password(user, body.password):
        raise HTTPException(401, "Wrong email or password.")
    start_session(db, request, response, user)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    end_session(db, request, response)


@router.get("/me", response_model=Me)
def me(user: User = Depends(current_user)):
    return user


@router.post("/accept-invite", response_model=Me, status_code=201)
def accept_invite(
    body: AcceptIn, request: Request, response: Response, db: Session = Depends(get_db)
):
    invite = db.scalar(
        select(Invite).where(
            Invite.token_hash == hash_token(body.token),
            Invite.accepted_at.is_(None),
            Invite.expires_at > utcnow(),
        )
    )
    if not invite:
        raise HTTPException(400, "This invite link is not valid any more.")
    if db.scalar(select(User).where(User.email == invite.email)):
        raise HTTPException(409, "That email already has an account.")
    user = User(
        workspace_id=invite.workspace_id,
        email=invite.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role=invite.role,
    )
    invite.accepted_at = utcnow()
    db.add(user)
    db.commit()
    start_session(db, request, response, user)
    return user
