"""The team: list members, invite people, change a role, remove people and bring them back.
Changes are owner-only."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import current_user, new_token, owner_only
from app.db import get_db, utcnow
from app.models.accounts import Invite, LoginSession, Role, User
from app.schemas import Email, UtcTime

router = APIRouter(prefix="/team", tags=["team"])


class MemberOut(BaseModel):
    id: int
    email: str
    name: str
    role: Role


class RoleIn(BaseModel):
    role: Role


class InviteIn(BaseModel):
    email: Email
    role: Role = Role.editor


class InviteOut(BaseModel):
    id: int
    email: str
    role: Role
    expires_at: UtcTime


class NewInviteOut(InviteOut):
    token: str  # shown once; the owner shares the link with the person


@router.get("/members", response_model=list[MemberOut])
def members(
    removed: bool = False,  # true: the removed members instead, to bring back (owner only)
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if removed and not user.is_owner:
        raise HTTPException(403, "Only the owner can do that.")
    found = select(User).where(User.workspace_id == user.workspace_id, User.active.is_(not removed))
    hide = not user.is_owner  # editors see Reed's name, not his email (Producer's default)
    return [MemberOut(id=u.id, email="" if hide and u.is_owner else u.email, name=u.name,
                      role=u.role) for u in db.scalars(found.order_by(User.id))]  # fmt: skip


def _member(db: Session, owner: User, member_id: int, active: bool = True) -> User:
    member = db.get(User, member_id)
    if not member or member.workspace_id != owner.workspace_id or member.active != active:
        raise HTTPException(404, "No such member.")
    return member


@router.patch("/members/{member_id}", response_model=MemberOut)
def change_role(
    member_id: int, body: RoleIn, owner: User = Depends(owner_only), db: Session = Depends(get_db)
):
    """Make someone an owner or an editor. You can't change your own role, so there is
    always at least one owner."""
    member = _member(db, owner, member_id)
    if member.id == owner.id:
        raise HTTPException(400, "You can't change your own role.")
    member.role = body.role
    db.commit()
    return member


@router.post("/members/{member_id}/restore", response_model=MemberOut)
def restore_member(
    member_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)
):
    """Undo a remove: they can sign in again, with the role they had."""
    member = _member(db, owner, member_id, active=False)
    member.active = True
    db.commit()
    return member


@router.delete("/members/{member_id}", status_code=204)
def remove_member(
    member_id: int, owner: User = Depends(owner_only), db: Session = Depends(get_db)
) -> None:
    member = _member(db, owner, member_id)
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
