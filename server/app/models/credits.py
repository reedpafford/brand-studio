"""Credits, project budgets and owner-set limits.

1 credit = $0.1028 of real cost = 1 second of 480p video. Rates per job kind give the
estimate when a job is queued; when it finishes, its real dollar cost is converted back to
credits. A project's budget is 2x the 480p estimate of its planned length."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity

USD_PER_CREDIT = Decimal("0.1028")  # Seedance 2.5 480p, per second
BUDGET_MULTIPLIER = 2
DEFAULT_MAX_PLANNED_SECONDS = 180  # editors can plan up to this without the owner
DEFAULT_WEEKLY_QUICK_CLIP_CREDITS = Decimal(150)  # per editor, Mon-Sun (UTC)


class CreditRate(Entity, Base):
    __tablename__ = "credit_rates"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # matches Job.kind, e.g. video-480p
    unit: Mapped[str] = mapped_column(String(20))  # second, image, call
    credits_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 4))


class CreditLimits(Entity, Base):
    """Owner-set limits, one row per workspace (defaults apply until the owner saves one)."""

    __tablename__ = "credit_limits"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), unique=True)
    max_planned_seconds: Mapped[int] = mapped_column(default=DEFAULT_MAX_PLANNED_SECONDS)
    weekly_quick_clip_credits: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=DEFAULT_WEEKLY_QUICK_CLIP_CREDITS
    )
