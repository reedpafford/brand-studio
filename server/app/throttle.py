"""Failed-login throttling, stored in the database so it holds across server processes.

Note: behind a proxy, `request.client.host` is the proxy; configure uvicorn's
--proxy-headers / --forwarded-allow-ips so it is the real client address."""

from datetime import timedelta

from fastapi import HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.accounts import LoginFailure


def _keys(request: Request, scope: str, email: str | None) -> dict[str, int]:
    settings = request.app.state.settings
    ip = request.client.host if request.client else "unknown"
    keys = {f"{scope}:ip:{ip}": settings.login_max_failures_per_ip}
    if email:
        keys[f"{scope}:email:{email}"] = settings.login_max_failures
    return keys


def check(db: Session, request: Request, scope: str, email: str | None = None) -> None:
    """Raise 429 if this email or IP has failed too often recently."""
    minutes = request.app.state.settings.login_window_minutes
    since = utcnow() - timedelta(minutes=minutes)
    for key, limit in _keys(request, scope, email).items():
        count = db.scalar(
            select(func.count(LoginFailure.id)).where(
                LoginFailure.key == key, LoginFailure.created_at > since
            )
        )
        if count >= limit:
            raise HTTPException(429, f"Too many tries. Please wait {minutes} minutes.")


def failed(db: Session, request: Request, scope: str, email: str | None = None) -> None:
    minutes = request.app.state.settings.login_window_minutes
    db.execute(
        delete(LoginFailure).where(LoginFailure.created_at < utcnow() - timedelta(minutes=minutes))
    )
    db.add_all(LoginFailure(key=key) for key in _keys(request, scope, email))
    db.commit()


def succeeded(db: Session, scope: str, email: str) -> None:
    """Reset the email's counter. The IP counter is left alone, so one good account
    can't be used to reset guessing from that address."""
    db.execute(delete(LoginFailure).where(LoginFailure.key == f"{scope}:email:{email}"))
    db.commit()
