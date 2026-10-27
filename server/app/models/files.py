from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity


class StoredFile(Entity, Base):
    """An uploaded or generated file. The bytes live in storage under `key`."""

    __tablename__ = "files"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    key: Mapped[str] = mapped_column(String(200), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class VideoUpload(Entity, Base):
    """A video uploaded for Bulk create before its draft exists (reel-import.md §8). It is
    `used` once a draft takes it; unused ones are removed after a day (purge.py)."""

    __tablename__ = "video_uploads"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"))
    seconds: Mapped[float]
    used: Mapped[bool] = mapped_column(default=False)
