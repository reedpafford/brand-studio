"""The advisory check on a still or take (1b, P4): Advice only, never a block."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class ItemCheck(Entity, Base):
    """One still or take compared with the cast's sheets and the starred product. It never
    touches an approval and never redoes anything."""

    __tablename__ = "item_checks"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    target: Mapped[str] = mapped_column(String(10))  # frame or take
    target_id: Mapped[int]
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    status: Mapped[str] = mapped_column(String(12), default="checking")  # done, failed, skipped
    # [{kind: face/outfit/product, role, text, change_note}]
    findings: Mapped[list[dict]] = mapped_column(JSON, default=list)
    dismissed: Mapped[list[dict]] = mapped_column(JSON, default=list)  # [{index, by_id, at}]
