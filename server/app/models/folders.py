"""Projects (flows OR1): a brand's folders of scripts, videos and quick clips. People only
ever see "Project"; the table is "folders" because a video is already a project here. A
deleted one is kept (deleted_at), so Undo brings it back with its items; until then an item
filed in it reads as No project. Items link by folder_id (null: No project)."""

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, object_session

from app.db import Base, Entity


class Folder(Entity, Base):
    __tablename__ = "folders"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    deleted_at: Mapped[datetime | None]


class Filed:
    """An item that can be filed in a project: `live_folder_id` is its folder, or None for
    No project (none, or a deleted one)."""

    @property
    def live_folder_id(self) -> int | None:
        if not self.folder_id:
            return None
        folder = object_session(self).get(Folder, self.folder_id)
        return folder.id if folder is not None and folder.deleted_at is None else None
