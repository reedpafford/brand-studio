"""Song ads: a version's song takes. Each take is one song from the music service (one job),
then its free timing read; the Preferred take is the one the video is timed to."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class SongTake(Entity, Base):
    __tablename__ = "song_takes"
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("script_drafts.id", ondelete="CASCADE"), index=True
    )
    # A video's own take (rule 31: its script is final); null for the script's own.
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int]  # Take 1, 2, … within its version (or video)
    kind: Mapped[str] = mapped_column(String(20), default="song")  # or "narration"
    voice: Mapped[str] = mapped_column(String(60), default="")  # a narration's voice
    trimmed: Mapped[bool] = mapped_column(default=False)  # its pauses trimmed (letters matched)
    music_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # its music bed
    music_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    track: Mapped[int] = mapped_column(default=0)  # which of its request's 2 songs
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))  # the song (the latest try)
    # What it sings: only a take of the version's current words can be Preferred
    lyrics: Mapped[str] = mapped_column(Text)
    style_line: Mapped[str] = mapped_column(Text)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # once made
    timing_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    timing: Mapped[dict | None] = mapped_column(JSON)  # app/song_timing.measure, once read
    seconds: Mapped[float | None]
    trim_to: Mapped[float | None]  # "Use the first 0:55" when the whole song is over the cap
    timing_guessed: Mapped[bool] = mapped_column(default=False)  # spread evenly, not heard
    advice: Mapped[list[str]] = mapped_column(JSON, default=list)  # e.g. "Timing guessed"
    preferred: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None]  # removed; Undo brings it back
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
