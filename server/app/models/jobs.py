"""Background jobs (model calls) and the usage rows they produce."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity
from app.models.folders import Filed


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"  # handed to the provider (or about to be)
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    needs_owner_approval = "needs_owner_approval"  # would go over the project budget


# Not finished yet: a press waits for these (one at a time), and a stop stops them
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class Job(Filed, Entity, Base):
    __tablename__ = "jobs"
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"), index=True)  # OR1
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(40))  # e.g. video, image, watch, write
    provider: Mapped[str] = mapped_column(String(40))
    input: Mapped[dict] = mapped_column(JSON)
    status: Mapped[JobStatus] = mapped_column(String(30), index=True, default=JobStatus.queued)
    provider_ref: Mapped[str | None] = mapped_column(String(200))  # provider's id for the work
    output: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str] = mapped_column(Text, default="")  # plain message, safe for everyone
    error_detail: Mapped[str] = mapped_column(Text, default="")  # raw provider text: owner only
    attempts: Mapped[int] = mapped_column(default=0)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    # The brand it's charged to (Usage); null when it can't belong to one brand.
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), index=True)
    # Estimated at queue time; replaced by the real amount when the job succeeds.
    credits: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # over budget
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    removed_at: Mapped[datetime | None]  # a Quick clip off the history (still counted)
    # P3: the one automatic retry of a refused or busy take, and the job it retries
    retry_of_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    auto: Mapped[bool] = mapped_column(default=False)


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
    estimated: Mapped[bool] = mapped_column(default=False)  # amount not reported by provider


class ChargeRefund(Entity, Base):
    """The owner gave one job's credits back (e.g. a still with the wrong person). The
    job's credits are set to 0, so every count follows; this keeps who, why and how many.
    The provider's dollars were spent and still show. At most one per job."""

    __tablename__ = "charge_refunds"
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    credits: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
