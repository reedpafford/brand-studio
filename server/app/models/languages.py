"""Languages (flows VS1): an owner's switch for each language. With no row, the list's own
`on` applies (English alone). A language is switched on for editors only once its sample
test was read and approved (app/language_samples.py)."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class LanguageSwitch(Entity, Base):
    __tablename__ = "language_switches"
    __table_args__ = (UniqueConstraint("workspace_id", "language_id"),)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    language_id: Mapped[str] = mapped_column(String(8))  # app/languages.py LANGUAGES
    on: Mapped[bool] = mapped_column(default=False)
    sample_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))  # the newest test
    rejected: Mapped[bool] = mapped_column(default=False)  # its sample was read and rejected
    was_on: Mapped[bool] = mapped_column(default=False)  # On when rejected: Undo puts it back
    switched_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    switched_at: Mapped[datetime | None]
