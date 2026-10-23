"""Credits and project budgets.

1 credit = 1 second of 480p video. Each job kind has a rate in credits per unit (second,
image, ...). A project's budget is 2x its 480p estimate; going over needs the owner."""

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity

BUDGET_MULTIPLIER = 2


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
