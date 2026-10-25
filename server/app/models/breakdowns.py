"""A project's breakdown (scenes → shots → clips) of one script version. Claude writes the
first; every edit by the editor is saved as a new row, and the newest one is the working one."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class BreakdownVersion(Entity, Base):
    __tablename__ = "breakdowns"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    script_version: Mapped[int]
    source: Mapped[str] = mapped_column(String(20))  # claude | edit
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    data: Mapped[dict] = mapped_column(JSON)  # app.prompts.schemas.Breakdown
    problems: Mapped[list[str]] = mapped_column(JSON, default=list)  # from check.breakdown
    kept: Mapped[list[str]] = mapped_column(JSON, default=list)  # "Advice: …" kept anyway
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
