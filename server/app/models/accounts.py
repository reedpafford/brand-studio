"""Workspace, users, login sessions and invites."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, Entity


class Role(StrEnum):
    owner = "owner"  # sees dollars, approves over-budget work, manages the team
    editor = "editor"  # sees credits and % of budget only


class Workspace(Entity, Base):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(120))


class User(Entity, Base):
    __tablename__ = "users"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(default=True)

    workspace: Mapped[Workspace] = relationship()

    @property
    def is_owner(self) -> bool:
        return self.role == Role.owner


class LoginSession(Entity, Base):
    __tablename__ = "login_sessions"
    # Only a hash of the cookie token is stored, so a database leak can't be replayed.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime]


class Invite(Entity, Base):
    __tablename__ = "invites"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[Role] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]


class SetupDone(Base):
    """At most one row (id=1). Inserting it in the setup transaction makes setup run once,
    even if two requests arrive at the same moment."""

    __tablename__ = "setup_done"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)


class LoginFailure(Entity, Base):
    """One failed login or setup attempt, keyed by email or IP. Used for throttling."""

    __tablename__ = "login_failures"
    key: Mapped[str] = mapped_column(String(300), index=True)
