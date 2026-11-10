from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, Entity
from app.models.folders import Filed


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


class MediaUpload(Filed, Entity, Base):
    """A picture or clip someone added to a brand's Media (v5 C_Media): free, checked by its
    contents. The owner can take it off Media (`removed_at`)."""

    __tablename__ = "media_uploads"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"))
    seconds: Mapped[float | None]  # a clip's length; null for a picture
    removed_at: Mapped[datetime | None]
    # Brand footage (Reed, 9 Nov, app/footage.py): a real clip on the library's Footage tab,
    # given to the director; what it shows and which product, two frames (the first its
    # thumbnail), and the AI description's job while it's being written
    footage: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str] = mapped_column(Text, default="")
    product_id: Mapped[int | None] = mapped_column(ForeignKey("library_items.id"))
    frame_file_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    describe_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    describe_note: Mapped[str] = mapped_column(Text, default="")  # why the AI's words aren't in
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"), index=True)
