"""Projects: a brief, a budget, and (later) script, breakdown, storyboard and clips."""

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity
from app.models.credits import BUDGET_MULTIPLIER

PRE_BREAKDOWN_SECONDS = 15  # before any breakdown: a 30-credit budget for the Claude steps


class ProjectStatus(StrEnum):
    active = "active"
    needs_owner_approval = "needs_owner_approval"  # planned length over the editor limit


class Project(Entity, Base):
    __tablename__ = "projects"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    planned_seconds: Mapped[int | None]  # a set length; null: the breakdown decides
    breakdown_seconds: Mapped[int | None]  # the newest breakdown's clips added up
    status: Mapped[ProjectStatus] = mapped_column(String(30), default=ProjectStatus.active)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # The library version this video is made from (each version is produced once).
    script_draft_id: Mapped[int | None] = mapped_column(
        ForeignKey("script_drafts.id", use_alter=True), unique=True
    )

    # Brief
    goal: Mapped[str] = mapped_column(Text, default="")
    platform: Mapped[str] = mapped_column(String(40), default="")  # e.g. tiktok, youtube
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="9:16")
    format: Mapped[str] = mapped_column(String(120), default="")  # optional named format
    cast_ids: Mapped[list[int]] = mapped_column(JSON, default=list)  # library characters
    reference_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # a video
    # A reference reel to adapt: its breakdown (app/reference.py shape) and what to rebuild.
    product_variants: Mapped[dict] = mapped_column(JSON, default=dict)  # product -> variant
    reference_breakdown: Mapped[dict | None] = mapped_column(JSON)
    reference_replace: Mapped[str] = mapped_column(Text, default="")

    @property
    def estimate_credits(self) -> Decimal:
        """480p costs 1 credit per second: a set length wins, else the newest breakdown's,
        else a small amount that lets the project reach its breakdown."""
        seconds = self.planned_seconds or self.breakdown_seconds or PRE_BREAKDOWN_SECONDS
        return Decimal(seconds)

    @property
    def budget_credits(self) -> Decimal:
        return self.estimate_credits * BUDGET_MULTIPLIER
