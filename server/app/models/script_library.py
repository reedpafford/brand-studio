"""The Script Library (workflow v2): a brand's scripts, each with up to three versions (the
original and up to two variations) and its cast slots, each optionally locked to a character.
Producing a version makes a project (`Project.script_draft_id`, one per version)."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint, event, select
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class Script(Entity, Base):
    __tablename__ = "scripts"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="story")  # story | song (song ads)
    look: Mapped[str] = mapped_column(String(40), default="house")  # how pictures are drawn (ST1)
    language: Mapped[str] = mapped_column(String(10), default="en")  # its videos read it (VS1)
    description: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    reference_id: Mapped[str | None] = mapped_column(String(80))  # a GET /references reel
    reference_replace: Mapped[str] = mapped_column(Text, default="")
    # Reel import (docs/design/reel-import-server.md): the reel's own breakdown, wins over
    # reference_id; `reel` holds the video, transcript and cuts; the latest import job.
    reference_breakdown: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    reel: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    reel_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    new_lines: Mapped[bool] = mapped_column(default=False)  # "Write new lines in the same style"
    published: Mapped[bool] = mapped_column(default=False)  # editors see others' once published
    archived: Mapped[bool] = mapped_column(default=False)  # removed: deleted, undoable
    deleted_at: Mapped[datetime | None]  # when; purged for good 30 days on (not built yet)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # Roles kept apart for good ("They're different"): [[slot id, slot id], …] (merge-roles.md)
    cast_apart: Mapped[list] = mapped_column(JSON, default=list)


@event.listens_for(Script, "before_insert")
def _language(mapper, connection, script: Script) -> None:
    """A new script is written in its brand's language unless one was given (VS1, BR1)."""
    if script.language is None:
        from app.models.brands import Brand

        found = connection.scalar(select(Brand.default_language)
                                  .where(Brand.id == script.brand_id))  # fmt: skip
        script.language = found or "en"


class ScriptDraft(Entity, Base):
    """One version of a script: slot 0 is the original, 1 and 2 are variations. Its words can
    change only while it is a draft; once approved they never change."""

    __tablename__ = "script_drafts"
    __table_args__ = (UniqueConstraint("script_id", "slot"),)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), index=True)
    slot: Mapped[int]
    text: Mapped[str] = mapped_column(Text, default="")  # a song's lyrics
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved
    # Song ads: the music style line, and the song directions offered for it
    # ([{title, concept, lyrics, style_line, visual_concept, recommended, unchecked_claims}])
    style_line: Mapped[str] = mapped_column(Text, default="")
    song_directions: Mapped[list[dict]] = mapped_column(JSON, default=list)
    song_study: Mapped[dict | None] = mapped_column(JSON)  # flows S3a, app/song_study.py
    singer: Mapped[str] = mapped_column(String(120), default="")  # a cast role; "": nobody seen
    plan: Mapped[dict | None] = mapped_column(JSON)  # 1b: the owner's plan, each video's start
    # Rule 18: an end line spoken over the song's last seconds (music lowered), at the stitch
    spoken_end_line: Mapped[str] = mapped_column(Text, default="")
    approved_at: Mapped[datetime | None]
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    target_seconds: Mapped[int | None]  # null: the breakdown decides the length
    # Variations (from the Director's schema): a short title and what changed.
    title: Mapped[str] = mapped_column(String(200), default="")
    premise: Mapped[str] = mapped_column(Text, default="")
    changes: Mapped[list[str]] = mapped_column(JSON, default=list)
    problems: Mapped[list[str]] = mapped_column(JSON, default=list)  # from check.variations
    # Adapting a reel: the lines Claude rewrote for the brand swap (the screens mark them).
    changed_lines: Mapped[list[str]] = mapped_column(JSON, default=list)
    rewritten: Mapped[list[dict]] = mapped_column(
        JSON, default=list
    )  # "Was:" marks (app/rewritten)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))  # the job that wrote it
    # Optional breakdown preview, saved with the version; the editor starts from it.
    breakdown: Mapped[dict | None] = mapped_column(JSON)
    breakdown_problems: Mapped[list[str]] = mapped_column(JSON, default=list)
    breakdown_kept: Mapped[list[str]] = mapped_column(JSON, default=list)  # advice kept anyway
    breakdown_text: Mapped[str | None] = mapped_column(Text)  # the words it was planned from
    breakdown_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # who planned it
    reserved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # producing it


class ScriptDraftText(Entity, Base):
    """An earlier text of a version, kept when its words were replaced (by hand or by a
    variations run), so it can be brought back while the version is a draft."""

    __tablename__ = "script_draft_texts"
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("script_drafts.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(20))  # edit | variations | write | enhance
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


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
    kind: Mapped[str] = mapped_column(String(20), default="Main")  # Main, Helper, Rival, Family
    appears_in: Mapped[list[int]] = mapped_column(JSON, default=list)  # version slots, from a read
    # Which of age, gender and occupation (the description's lead) the cast read inferred
    guessed: Mapped[list[str]] = mapped_column(JSON, default=list)
    library_item_id: Mapped[int | None] = mapped_column(ForeignKey("library_items.id"))
    sheet_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # when locked
    locked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # The cast read's "may be the same person as" this other role (word for word), or ""
    may_be_same_as: Mapped[str] = mapped_column(String(120), default="")


class CastMerge(Entity, Base):
    """What a role merge changed, so its Undo puts it all back (merge-roles.md §1)."""

    __tablename__ = "cast_merges"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))  # a video's own
    data: Mapped[dict] = mapped_column(JSON)


class SeededScript(Entity, Base):
    """A script draft file from the repo already imported into a workspace (app/seed_drafts.py),
    kept even if Reed deletes the script, so a deploy never brings it back."""

    __tablename__ = "seeded_scripts"
    __table_args__ = (UniqueConstraint("workspace_id", "key"),)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"))
    key: Mapped[str] = mapped_column(String(300))  # "<reference_id>/<file name>"
