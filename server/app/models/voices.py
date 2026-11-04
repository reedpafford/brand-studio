"""Voices (v6 S8-04, Library › Presenters & voices): the voices a brand made its own (Reed,
4 Nov: only voices uploaded or cloned for it). A row is a voice cloned from a sample
(`cloned`: MiniMax, its `provider_voice_id` spoken through `speech_model`), or a voice
described in words (`described`: what Omni is told, since its voice can't be ours).
`brand_id` null: a style's own voice for every brand (`look`, e.g. Dr. Pickle's clone). A
cloned voice may be deleted by MiniMax after 7 days unused (`last_used_at`); `lost_at` is
when MiniMax said it's gone. The app's own voices aren't rows: they're listed from
app/narration.py."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class Voice(Entity, Base):
    __tablename__ = "voices"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), index=True)
    look: Mapped[str | None] = mapped_column(String(40))  # a style's own voice
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # cloned | described
    provider: Mapped[str] = mapped_column(String(20))  # elevenlabs | minimax | omni
    provider_voice_id: Mapped[str | None] = mapped_column(String(120))
    speech_model: Mapped[str | None] = mapped_column(String(60))  # a catalogue id
    description: Mapped[str] = mapped_column(Text, default="")
    sample_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    preview_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))  # the clone's job
    cloned_at: Mapped[datetime | None]
    last_used_at: Mapped[datetime | None]
    lost_at: Mapped[datetime | None]
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[datetime | None]
