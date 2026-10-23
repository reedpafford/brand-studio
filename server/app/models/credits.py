"""Credits and project budgets.

1 credit = 1 second of 480p video. Each job kind has a rate in credits per unit (second,
image, ...). A project's budget is 2x its 480p estimate; going over needs the owner."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity

BUDGET_MULTIPLIER = 2
# Placeholders until the Producer/Reed confirm: 5 min and 1 min of 480p video.
DEFAULT_EDITOR_MAX_ESTIMATE = Decimal(300)
DEFAULT_MAX_JOB_WITHOUT_PROJECT = Decimal(60)


class CreditRate(Entity, Base):
    __tablename__ = "credit_rates"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # matches Job.kind, e.g. video-480p
    unit: Mapped[str] = mapped_column(String(20))  # second, image, ...
    credits_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 4))


class Project(Entity, Base):
    __tablename__ = "projects"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    estimate_credits: Mapped[Decimal] = mapped_column(Numeric(12, 3))  # the 480p estimate

    @property
    def budget_credits(self) -> Decimal:
        return self.estimate_credits * BUDGET_MULTIPLIER


class CreditLimits(Entity, Base):
    """Owner-set limits, one row per workspace (defaults apply until the owner saves one)."""

    __tablename__ = "credit_limits"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), unique=True)
    # Largest estimate an editor may give a new project; above it only the owner can.
    editor_max_estimate_credits: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=DEFAULT_EDITOR_MAX_ESTIMATE
    )
    # Largest job outside a project (e.g. a quick clip) before it waits for the owner.
    max_job_credits_without_project: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=DEFAULT_MAX_JOB_WITHOUT_PROJECT
    )
