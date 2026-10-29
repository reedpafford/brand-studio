"""A project's clips: one video prompt per clip of the breakdown (Claude writes it, the editor
can edit it), and later the generated video."""

from sqlalchemy import JSON, ForeignKey, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class ProjectClip(Entity, Base):
    __tablename__ = "project_clips"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    breakdown_id: Mapped[int] = mapped_column(ForeignKey("breakdowns.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))  # the Claude call
    clip_id: Mapped[str] = mapped_column(String(20))  # c1, c2, …
    seconds: Mapped[int]
    prompt: Mapped[str] = mapped_column(Text)
    references: Mapped[list[dict]] = mapped_column(JSON, default=list)  # {kind, id, role}
    problems: Mapped[list[str]] = mapped_column(JSON, default=list)
    kept: Mapped[list[str]] = mapped_column(JSON, default=list)  # "Advice: …" kept anyway
    file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # the picked take's video
    picked_take_id: Mapped[int | None] = mapped_column(ForeignKey("clip_takes.id", use_alter=True))
    approved: Mapped[bool] = mapped_column(default=False)  # the picked take looks good
    prompt_ok: Mapped[bool] = mapped_column(default=False)  # its prompt was read: Looks good
    # Insert shot id -> "Use the real image" as the editor set it (else the default, cut_in.py)
    real_images: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict)
    change: Mapped[dict | None] = mapped_column(JSON)  # the last note: app/change.py
    # Fix this clip's prompt's free Claude rewrite was used for this prompt (once per prompt
    # version): cleared when the prompt changes any other way (`same_fix` keeps it).
    free_fix_used: Mapped[bool] = mapped_column(default=False)
    # Song ads: {start, end, sung_shots} of the video's song this clip covers, from its
    # breakdown row (song_breakdown.slice_of); None for a story video
    song_slice: Mapped[dict | None] = mapped_column(JSON)


@event.listens_for(ProjectClip.prompt, "set")
def _new_prompt(clip: ProjectClip, value, old, _initiator) -> None:
    """A prompt changed by any route but the free fix (or its Undo) can be fixed free again."""
    if value != old and not getattr(clip, "same_fix", False):
        clip.free_fix_used = False


class ClipTake(Entity, Base):
    """One generated video for a clip. Every redo adds a take; one is picked for the video."""

    __tablename__ = "clip_takes"
    clip_id: Mapped[int] = mapped_column(ForeignKey("project_clips.id"), index=True)
    number: Mapped[int]  # 1, 2, … within the clip
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"))
    prompt: Mapped[str | None] = mapped_column(Text)  # what it was made from; picked back with it
    look: Mapped[str] = mapped_column(String(40), default="house")  # the video's look then (VS1)


class FinalVideo(Entity, Base):
    """The picked takes stitched in order (free). Out of date once any pick changes."""

    __tablename__ = "final_videos"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"))
    take_ids: Mapped[list[int]] = mapped_column(JSON)
    cut_ins: Mapped[list[str]] = mapped_column(JSON, default=list)  # "c1/1.2" for each one used
    song_take_id: Mapped[int | None] = mapped_column(ForeignKey("song_takes.id"))  # laid under
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
