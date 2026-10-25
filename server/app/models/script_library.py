"""The Script Library (workflow v2): a brand's scripts, each with up to three versions (the
original and up to two variations) and its cast slots, each optionally locked to a character.
Producing a version makes a project (`Project.script_draft_id`, one per version)."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class Script(Entity, Base):
    __tablename__ = "scripts"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    reference_id: Mapped[str | None] = mapped_column(String(80))  # a GET /references reel
    reference_replace: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[bool] = mapped_column(default=False)  # editors see others' once published
    archived: Mapped[bool] = mapped_column(default=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class ScriptDraft(Entity, Base):
    """One version of a script: slot 0 is the original, 1 and 2 are variations. Its words can
    change only while it is a draft; once approved they never change."""

    __tablename__ = "script_drafts"
    __table_args__ = (UniqueConstraint("script_id", "slot"),)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), index=True)
    slot: Mapped[int]
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved
    approved_at: Mapped[datetime | None]
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    target_seconds: Mapped[int | None]  # null: the breakdown decides the length
    # Variations (from the Director's schema): a short title and what changed.
    title: Mapped[str] = mapped_column(String(200), default="")
    premise: Mapped[str] = mapped_column(Text, default="")
    changes: Mapped[list[str]] = mapped_column(JSON, default=list)
    problems: Mapped[list[str]] = mapped_column(JSON, default=list)  # from check.variations
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))  # the job that wrote it
    # Optional breakdown preview, saved with the version; the editor starts from it.
    breakdown: Mapped[dict | None] = mapped_column(JSON)
    breakdown_problems: Mapped[list[str]] = mapped_column(JSON, default=list)
    reserved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # producing it


class ScriptCastSlot(Entity, Base):
    """A named or recurring role in a script (a main, a mentor, a rival, family), shared by
    every version. Optional; locked = a library character and its approved sheet at lock
    time, used as-is in every version. Unlocked slots are made at the editor's Assets step.
    Background people are never slots."""

    __tablename__ = "script_cast_slots"
    __table_args__ = (UniqueConstraint("script_id", "role"),)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), index=True)
    role: Mapped[str] = mapped_column(String(120))  # e.g. "Nate", "the coach"
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(default=0)
    library_item_id: Mapped[int | None] = mapped_column(ForeignKey("library_items.id"))
    sheet_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # when locked
    locked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
