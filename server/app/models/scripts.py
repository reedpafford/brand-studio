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
