"""Background jobs (model calls) and the usage rows they produce."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"  # handed to the provider (or about to be)
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class Job(Entity, Base):
    __tablename__ = "jobs"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(40))  # e.g. video, image, watch, write
    provider: Mapped[str] = mapped_column(String(40))
    input: Mapped[dict] = mapped_column(JSON)
    status: Mapped[JobStatus] = mapped_column(String(30), index=True, default=JobStatus.queued)
    provider_ref: Mapped[str | None] = mapped_column(String(200))  # provider's id for the work
    output: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class Usage(Entity, Base):
    """What a job consumed, with its real dollar cost. Owner-only: never sent to editors."""

    __tablename__ = "usage"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(40))
    units: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(20))  # e.g. second, image, token
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4))
