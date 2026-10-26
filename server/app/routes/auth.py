"""First-run setup, login, logout, accepting an invite, and "who am I"."""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import throttle
from app.auth import (
    check_password,
    current_user,
    end_session,
    hash_password,
    hash_token,
    start_session,
)
from app.credits import seed_rates
from app.db import get_db, utcnow
from app.models.accounts import Invite, Role, SetupDone, User, Workspace
from app.schemas import Email, Name, Password
from app.seed import seed_brands

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)


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
    throttle.check(db, request, "setup")
    expected = request.app.state.settings.setup_token
    if not expected or not secrets.compare_digest(body.setup_token, expected):
        throttle.failed(db, request, "setup")
        raise HTTPException(403, "Setup is not allowed.")
    if db.get(SetupDone, 1):
        raise HTTPException(409, "Already set up.")
    workspace = Workspace(name=body.workspace_name)
    user = User(
        workspace=workspace,
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role=Role.owner,
    )
    db.add_all([SetupDone(id=1), user])
    try:
        db.commit()
    except IntegrityError:  # another setup request won the race
        db.rollback()
        raise HTTPException(409, "Already set up.") from None
    state = request.app.state
    try:
        seed_rates(db, workspace.id)
        seed_brands(db, workspace.id, state.storage, state.settings.brand_assets_dir)
    except Exception:  # never leave a half-set-up server: log it; the import can be re-run
        db.rollback()
        log.exception("Seeding launch brands failed; run `python -m app.seed <folder>` later.")
    start_session(db, request, response, user)
    return user


@router.post("/login", response_model=Me)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle.check(db, request, "login", body.email)
    user = db.scalar(select(User).where(User.email == body.email, User.active))
    if not check_password(user, body.password):
        throttle.failed(db, request, "login", body.email)
        raise HTTPException(401, "Wrong email or password.")
    throttle.succeeded(db, "login", body.email)
    start_session(db, request, response, user)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    end_session(db, request, response)


@router.get("/me", response_model=Me)
def me(user: User = Depends(current_user)):
    return user


INVALID_INVITE = "This invite link is not valid any more."


def _open_invite(db: Session, token: str) -> Invite | None:
    return db.scalar(
        select(Invite).where(
            Invite.token_hash == hash_token(token),
            Invite.accepted_at.is_(None),
            Invite.expires_at > utcnow(),
        )
    )


class InviteLookupIn(BaseModel):
    token: str


class InviteOut(BaseModel):
    workspace_name: str
    invited_by_name: str
    owner_name: str  # "Join {owner}'s studio" when the studio's name looks like a slug
    email: str
    role: Role


@router.post("/invite", response_model=InviteOut)
def read_invite(body: InviteLookupIn, db: Session = Depends(get_db)):
    """What an invite link is for, before signing up (no login). The token is sent in the body,
    not the URL, so it never lands in access logs."""
    invite = _open_invite(db, body.token)
    if not invite:
        raise HTTPException(404, INVALID_INVITE)
    inviter = db.get(User, invite.invited_by_id)
    return InviteOut(
        workspace_name=db.get(Workspace, invite.workspace_id).name,
        invited_by_name=inviter.name if inviter else "",
        owner_name=db.scalar(
            select(User.name).where(
                User.workspace_id == invite.workspace_id, User.role == Role.owner, User.active
            )
        )
        or "",
        email=invite.email,
        role=invite.role,
    )


@router.post("/accept-invite", response_model=Me, status_code=201)
def accept_invite(
    body: AcceptIn, request: Request, response: Response, db: Session = Depends(get_db)
):
    invite = _open_invite(db, body.token)
    if not invite:
        raise HTTPException(400, INVALID_INVITE)
    user = db.scalar(select(User).where(User.email == invite.email))
    if user and user.active:
        raise HTTPException(409, "That email already has an account.")
    # A removed member who is invited again comes back with the new name, password and role.
    user = user or User(email=invite.email)
    user.workspace_id = invite.workspace_id
    user.name = body.name
    user.password_hash = hash_password(body.password)
    user.role = invite.role
    user.active = True
    invite.accepted_at = utcnow()
    db.add(user)
    db.commit()
    start_session(db, request, response, user)
    return user
