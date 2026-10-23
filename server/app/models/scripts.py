"""A project's script. Every change is a new version; the newest is the working script."""

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class ScriptVersion(Entity, Base):
    __tablename__ = "script_versions"
    __table_args__ = (UniqueConstraint("project_id", "version"),)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    # paste | upload | draft (Claude wrote it) | enhance (suggestions applied)
    source: Mapped[str] = mapped_column(String(20))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Suggestion(Entity, Base):
    """One Enhance mark on a script version. The editor accepts or rejects it; accepted marks
    are applied together to make the next version."""

    __tablename__ = "script_suggestions"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    script_version: Mapped[int]
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    key: Mapped[str] = mapped_column(String(20))  # s1, s2, ... as Claude numbered them
    kind: Mapped[str] = mapped_column(String(20))
    line: Mapped[int]
    quote: Mapped[str] = mapped_column(Text)
    start: Mapped[int]  # character offsets of the quote in the script version
    end: Mapped[int]
    placement: Mapped[str] = mapped_column(String(10))  # before | after | replace
    text: Mapped[str] = mapped_column(Text)
    screen_id: Mapped[int | None] = mapped_column(ForeignKey("brand_screens.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # accepted | rejected
