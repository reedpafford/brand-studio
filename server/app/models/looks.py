"""Looks (flows ST1, ST3): an owner's switch for each look. With no row, the look file's own
`on:` applies (House alone). A look is switched on for editors only once its sample exists."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class LookSwitch(Entity, Base):
    __tablename__ = "look_switches"
    __table_args__ = (UniqueConstraint("workspace_id", "look_id"),)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    look_id: Mapped[str] = mapped_column(String(40))  # a prompts/styles file (kind: look)
    on: Mapped[bool] = mapped_column(default=False)
    sample_still_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # ST3
    sample_clip_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    switched_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    switched_at: Mapped[datetime | None]
