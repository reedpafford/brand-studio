"""Storyboard frames: one still per clip (or per shot) of a breakdown. Claude writes each
frame's image prompt and picks its references; the editor can edit both."""

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class StoryboardFrame(Entity, Base):
    __tablename__ = "storyboard_frames"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    breakdown_id: Mapped[int] = mapped_column(ForeignKey("breakdowns.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))  # the Claude call
    clip_id: Mapped[str] = mapped_column(String(20))
    shot_id: Mapped[str] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    reference_ids: Mapped[list[str]] = mapped_column(JSON, default=list)  # "char:5", "screen:2"
    problems: Mapped[list[str]] = mapped_column(JSON, default=list)
    kept: Mapped[list[str]] = mapped_column(JSON, default=list)  # "Advice: …" kept anyway
    file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # the rendered still
    approved: Mapped[bool] = mapped_column(default=False)  # cleared on edit or a new still
