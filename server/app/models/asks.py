"""The director's questions and the money OKs a video waits on (v6 piece B, S4-01 to S4-04):
one row per card. A question's `state` is kept here (open, uploading, answered, not_needed);
generating, ready, failed and held are read from its options' jobs, and a money card's from
its held jobs (app/asks.py)."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class Ask(Entity, Base):
    __tablename__ = "asks"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    run: Mapped[str | None] = mapped_column(String(40))  # the director run that asked
    kind: Mapped[str] = mapped_column(String(20))  # app/asks.py KINDS
    topic: Mapped[str] = mapped_column(String(80), default="")  # "The husband", for the bar
    subject: Mapped[str] = mapped_column(String(120), default="")  # the role as the script says
    question: Mapped[str] = mapped_column(Text, default="")
    why: Mapped[str] = mapped_column(Text, default="")
    describe: Mapped[str] = mapped_column(Text, default="")  # what Generate options draws
    choices: Mapped[list[dict]] = mapped_column(JSON, default=list)  # a story choice's {key,…}
    pick: Mapped[str | None] = mapped_column(String(120))  # the director's pick: an option id
    decide_at: Mapped[datetime | None]  # a story choice: past it, the director takes its pick
    state: Mapped[str] = mapped_column(String(20), default="open")
    answer: Mapped[dict | None] = mapped_column(JSON)  # {how, option, file_id, text, choice}
    answered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    answered_at: Mapped[datetime | None]
    rounds: Mapped[list[dict]] = mapped_column(JSON, default=list)  # Generate: {jobs, like, …}
    job_ids: Mapped[list[int]] = mapped_column(JSON, default=list)  # a money card's held jobs
    closed: Mapped[str] = mapped_column(Text, default="")  # no longer needed: why
