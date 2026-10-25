"""The team: list members, invite people, remove people. Changes are owner-only."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import current_user, new_token, owner_only
from app.db import get_db, utcnow
from app.models.accounts import Invite, LoginSession, Role, User
from app.schemas import Email

router = APIRouter(prefix="/team", tags=["team"])


class MemberOut(BaseModel):
    id: int
    email: str
    name: str
    role: Role


class InviteIn(BaseModel):
    email: Email
    role: Role = Role.editor


class InviteOut(BaseModel):
    id: int
    email: str
    role: Role
    expires_at: datetime


class NewInviteOut(InviteOut):
    token: str  # shown once; the owner shares the link with the person


@router.get("/members", response_model=list[MemberOut])
def members(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(User).where(User.workspace_id == user.workspace_id, User.active).order_by(User.id)
    ).all()


@router.delete("/members/{member_id}", status_code=204)
def remove_member(
    member_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)
) -> None:
    member = db.get(User, member_id)
    if not member or member.workspace_id != owner.workspace_id or not member.active:
        raise HTTPException(404, "No such member.")
    if member.id == owner.id:
        raise HTTPException(400, "You can't remove yourself.")
    member.active = False
    db.execute(delete(LoginSession).where(LoginSession.user_id == member.id))
    db.commit()


@router.get("/invites", response_model=list[InviteOut])
def invites(owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    return db.scalars(
        select(Invite).where(
            Invite.workspace_id == owner.workspace_id,
            Invite.accepted_at.is_(None),
            Invite.expires_at > utcnow(),
        )
    ).all()


@router.post("/invites", response_model=NewInviteOut, status_code=201)
def create_invite(
    body: InviteIn,
    request: Request,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    if db.scalar(select(User).where(User.email == body.email, User.active)):
        raise HTTPException(409, "That email already has an account.")
    raw, digest = new_token()
    days = request.app.state.settings.invite_days
    invite = Invite(
        workspace_id=owner.workspace_id,
        email=body.email,
        role=body.role,
        token_hash=digest,
        invited_by_id=owner.id,
        expires_at=utcnow() + timedelta(days=days),
    )
    db.add(invite)
    db.commit()
    return NewInviteOut(
        id=invite.id, email=invite.email, role=invite.role, expires_at=invite.expires_at, token=raw
    )


@router.post("/invites/{invite_id}/link", response_model=NewInviteOut)
def new_invite_link(
    invite_id: int,
    request: Request,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """A fresh link for a waiting invite (only a hash of the old one is kept, so it can't be
    shown again). The old link stops working; the new one lasts the usual days."""
    invite = db.get(Invite, invite_id)
    if not invite or invite.workspace_id != owner.workspace_id or invite.accepted_at:
        raise HTTPException(404, "No such invite.")
    raw, invite.token_hash = new_token()
    invite.expires_at = utcnow() + timedelta(days=request.app.state.settings.invite_days)
    db.commit()
    return NewInviteOut(
        id=invite.id, email=invite.email, role=invite.role, expires_at=invite.expires_at, token=raw
    )


@router.delete("/invites/{invite_id}", status_code=204)
def cancel_invite(
    invite_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)
) -> None:
    invite = db.get(Invite, invite_id)
    if not invite or invite.workspace_id != owner.workspace_id or invite.accepted_at:
        raise HTTPException(404, "No such invite.")
    db.delete(invite)
    db.commit()
