"""A project's clips: one video prompt per clip of the breakdown (Claude writes it, the editor
can edit it), and later the generated video."""

from datetime import datetime

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
    # the one-pass director couldn't make it: why. The cut is made without it, and delivery
    # says so, until it has a take (app/one_pass.py, Reed 13 Nov: "MINIMAL dead ends")
    left_out: Mapped[str | None] = mapped_column(Text)
    # P3: wording fixed in code ({before, after, fixed: [what], undone}); Undo puts `before` back
    auto_fix: Mapped[dict | None] = mapped_column(JSON)
    # Song ads: {start, end, sung_shots} of the video's song this clip covers, from its
    # breakdown row (song_breakdown.slice_of); None for a story video
    song_slice: Mapped[dict | None] = mapped_column(JSON)
    # OR3: the prompts before the one in hand, newest first, at most 10 (n13)
    prompt_history: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # v6 F (n38): the clip's own model when the director chose one, {id, why, by}; null: the
    # video's (app/model_map.py)
    model: Mapped[dict | None] = mapped_column(JSON)


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
    # What it was made with (VS1, n09): {video_model, aspect_ratio, products}; {} = before n09
    made_with: Mapped[dict] = mapped_column(JSON, default=dict)
    # The director's watch (n39, app/take_watch): {state, found, faults, did, action, …}
    watch: Mapped[dict | None] = mapped_column(JSON)


class FinalVideo(Entity, Base):
    """A cut of the video (Cut 1, Cut 2, …: app/cut.py), made free from the picked takes and the
    cut's edits. Out of date once a pick, an edit or anything laid over a take changes."""

    __tablename__ = "final_videos"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int] = mapped_column(default=1)  # Cut 1, Cut 2, … within the video (n42)
    edit_ids: Mapped[list[int]] = mapped_column(JSON, default=list)  # the edits it was made with
    timeline: Mapped[dict | None] = mapped_column(JSON)  # where each piece sat (cut.timeline)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"))
    take_ids: Mapped[list[int]] = mapped_column(JSON)
    cut_ins: Mapped[list[str]] = mapped_column(JSON, default=list)  # "c1/1.2" for each one used
    song_take_id: Mapped[int | None] = mapped_column(ForeignKey("song_takes.id"))  # laid under
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    off_media_at: Mapped[datetime | None]  # the owner took it off Media; its video keeps it
    seconds: Mapped[float | None]  # its length, kept when it's made (Media shows it)


class CutEdit(Entity, Base):
    """One edit to the cut (app/cut.py): a trim, a re-time to the words, a split, a B-roll swap,
    the presenter's side, size or hiding over a span, or the music. Edits replay in order over
    the picked takes; Undo marks one undone (any one: the director's edits each have Undo)."""

    __tablename__ = "cut_edits"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    director: Mapped[bool] = mapped_column(default=False)  # made by the director's move
    kind: Mapped[str] = mapped_column(String(20))  # trim, retime, split, swap, presenter, music
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    said: Mapped[str] = mapped_column(Text, default="")  # "Clip 9 re-timed to the words"
    at: Mapped[float] = mapped_column(default=0)  # where in the cut, seconds ("0:24")
    undone_at: Mapped[datetime | None]


class HostPiece(Entity, Base):
    """A presenter video's host (app/host.py): number 0 is the host's still on green, 1, 2, …
    the pieces that lip-sync its narration from `start` to `end` (seconds). Each is made by
    its newest job (input host_piece_id); a remake keeps the one before in `earlier`."""

    __tablename__ = "host_pieces"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    take_id: Mapped[int] = mapped_column(ForeignKey("song_takes.id"))  # the narration
    number: Mapped[int]
    start: Mapped[float] = mapped_column(default=0)
    end: Mapped[float] = mapped_column(default=0)
    audio_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # its narration
    file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # once made
    earlier: Mapped[list[int]] = mapped_column(JSON, default=list)  # earlier makes' files
    how: Mapped[str | None] = mapped_column(String(20))  # n38: talks or corner (app/host.how)
    watch: Mapped[dict | None] = mapped_column(JSON)  # the director's watch (n39, app/host_watch)
