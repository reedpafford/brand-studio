"""Projects: a brief, a budget, and (later) script, breakdown, storyboard and clips."""

import math
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, object_session

from app.db import Base, Entity
from app.models.folders import Filed

PRE_BREAKDOWN_SECONDS = 15  # before any breakdown: the length the budget plans for


class ProjectStatus(StrEnum):
    active = "active"
    needs_owner_approval = "needs_owner_approval"  # planned length over the editor limit


class Project(Filed, Entity, Base):
    __tablename__ = "projects"
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"), index=True)  # OR1
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    # How its pictures are drawn (ST1): its script's at Make this version, then its own (VS1)
    look: Mapped[str] = mapped_column(String(40), default="house")
    # Video settings (VS1, n09): the models it's made with; null is Auto (the catalogue default)
    video_model: Mapped[str | None] = mapped_column(String(40))
    image_model: Mapped[str | None] = mapped_column(String(40))
    # Song shot ids a no-lip-sync video model turned to B-roll; a lip-sync one flips them back
    sung_flipped: Mapped[list[str]] = mapped_column(JSON, default=list)
    planned_seconds: Mapped[int | None]  # a set length; null: the breakdown decides
    breakdown_seconds: Mapped[int | None]  # the newest breakdown's clips added up
    # "Video done": the first final video, or the first full download of the picked takes.
    # Set once, never cleared (Usage counts a video as finished on that day).
    finished_at: Mapped[datetime | None]
    archived_at: Mapped[datetime | None]  # put away (or its version released); Undo clears it
    # Released from this library version (it went back to Ready to make); Restore relinks it.
    released_draft_id: Mapped[int | None] = mapped_column(
        ForeignKey("script_drafts.id", use_alter=True)
    )
    status: Mapped[ProjectStatus] = mapped_column(String(30), default=ProjectStatus.active)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # The library version this video is made from (each version is produced once).
    script_draft_id: Mapped[int | None] = mapped_column(
        ForeignKey("script_drafts.id", use_alter=True), unique=True
    )

    # Song ads: the take this video is timed to (starts as its version's Preferred, rule 31)
    song_take_id: Mapped[int | None] = mapped_column(ForeignKey("song_takes.id", use_alter=True))
    singer: Mapped[str | None] = mapped_column(String(120))  # null: the version's singer
    # 1b (P1): the scene plan (docs/next/data.md: line numbers only, never the words) and
    # earlier plans, newest first, at most 10. Null: read from the breakdown, or none yet.
    plan: Mapped[dict | None] = mapped_column(JSON)
    plan_history: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # OR3: the storyboards before the one in hand, newest first, at most 10 (n13)
    storyboard_history: Mapped[list[dict]] = mapped_column(JSON, default=list)

    # Assets step: unlocked cast slot id (as text) -> the library character the editor gave it.
    slot_cast: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    slot_looks: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)  # slot -> own look
    # n12: every own look made for a role here, per look ({slot: {look: item}}), so switching
    # back re-casts the role to the one it has in that look (VS1 Undo), never made again
    own_looks: Mapped[dict[str, dict[str, int]]] = mapped_column(JSON, default=dict)
    # ST2: a locked role's library character -> this video's own copy drawn in its look ("Make
    # a {look} look for this video"). Not slot_looks, which is for unlocked roles' own looks.
    look_copies: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    # Roles merged into another on this video's Assets only: slot -> the role kept
    slot_merged: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    # Role pairs kept apart on this video's Assets ("They're different"): [[a, b], ...]
    cast_apart: Mapped[list] = mapped_column(JSON, default=list)
    # The last still redraw after a cast change: {"redrawn_for_cast": {count, credits}} or
    # {"redraw_refused": {count, credits, reason}} (for the Storyboard note).
    cast_redraw: Mapped[dict | None] = mapped_column(JSON)

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
        else a song video's song (it decides the length, spec §1, as its quote and take card
        say), else a small amount that lets the project reach its breakdown."""
        seconds = self.planned_seconds or self.breakdown_seconds or self._song_seconds()
        return Decimal(seconds or PRE_BREAKDOWN_SECONDS)

    def _song_seconds(self) -> int:
        from app.models.songs import SongTake

        db = object_session(self)
        take = db.get(SongTake, self.song_take_id) if db and self.song_take_id else None
        return math.ceil(take.trim_to or take.seconds or 0) if take else 0

    @property
    def budget_credits(self) -> Decimal:
        """Twice its whole estimate, every step included (rule 3): `credits.budget`."""
        from app.credits import budget

        return budget(object_session(self), self)
