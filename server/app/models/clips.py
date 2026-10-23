"""A project's clips: one video prompt per clip of the breakdown (Claude writes it, the editor
can edit it), and later the generated video."""

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class ProjectClip(Entity, Base):
    __tablename__ = "project_clips"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    breakdown_id: Mapped[int] = mapped_column(ForeignKey("breakdowns.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))  # the Claude call
    clip_id: Mapped[str] = mapped_column(String(20))  # c1, c2, …
    seconds: Mapped[int]
    prompt: Mapped[str] = mapped_column(Text)
    references: Mapped[list[dict]] = mapped_column(JSON, default=list)  # {kind, id, role}
    problems: Mapped[list[str]] = mapped_column(JSON, default=list)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # the generated video
