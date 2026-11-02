"""Freestyle (Reed's v4): a video made from a pasted script and a chat, outside any brand's
videos. `chat` is the thread's messages, each {by, text, at, job}: `job` is the job that send
started (None when it started none). Its status is read from those jobs."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class Freestyle(Entity, Base):
    __tablename__ = "freestyles"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20))  # dialogue, song, narrated or one_clip
    look: Mapped[str] = mapped_column(String(40))
    shape: Mapped[str] = mapped_column(String(10))  # 9:16, 1:1 or 16:9
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"))
    chat: Mapped[list[dict]] = mapped_column(JSON, default=list)
    stopped_at: Mapped[datetime | None]
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))  # its hidden video
    up_to: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))  # the price the OK covers
