"""Password hashing, session tokens and the "who is calling" dependencies."""

import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advice import REQUEST
from app.db import get_db, utcnow
from app.models.accounts import LoginSession, User

COOKIE = "bs_session"
_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def check_password(user: User | None, password: str) -> bool:
    """Constant-ish time: always runs one verify, even for unknown emails."""
    try:
        return _hasher.verify(user.password_hash if user else _DUMMY_HASH, password) and bool(user)
    except VerificationError:
        return False


def new_token() -> tuple[str, str]:
    """Returns (raw token for the client, hash to store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def start_session(db: Session, request: Request, response: Response, user: User) -> None:
    settings = request.app.state.settings
    raw, digest = new_token()
    expires = utcnow() + timedelta(days=settings.session_days)
    db.add(LoginSession(token_hash=digest, user_id=user.id, expires_at=expires))
    db.commit()
    response.set_cookie(
        COOKIE,
        raw,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def end_session(db: Session, request: Request, response: Response) -> None:
    raw = request.cookies.get(COOKIE)
    if raw:
        session = db.scalar(select(LoginSession).where(LoginSession.token_hash == hash_token(raw)))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(COOKIE)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get(COOKIE)
    if raw:
        user = db.scalar(
            select(User)
            .join(LoginSession, LoginSession.user_id == User.id)
            .where(
                LoginSession.token_hash == hash_token(raw),
                LoginSession.expires_at > utcnow(),
                User.active,
            )
        )
        if user:
            if (asker := REQUEST.get()) is not None:
                asker["workspace_id"] = user.workspace_id  # names in messages: theirs only
                asker["owner"] = user.is_owner  # editors never see the owner's name (rule 4)
            return user
    raise HTTPException(401, "Please log in.")


def owner_only(user: User = Depends(current_user)) -> User:
    if not user.is_owner:
        raise HTTPException(403, "Only the owner can do that.")
    return user


def user_name(db: Session, user_id: int | None) -> str:
    """A teammate's name for lists ("asked by"), or "" if unknown."""
    return shown_name(db.get(User, user_id) if user_id else None)


def shown_name(user: User | None) -> str:
    """A person's name as this viewer may see it: to anyone but the owner, the owner is
    "the owner" (Current rules 4: editors never see Reed's name)."""
    if user is None:
        return ""
    return "the owner" if user.is_owner and not (REQUEST.get() or {}).get("owner") else user.name
