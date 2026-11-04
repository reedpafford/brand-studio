"""Folders (flows OR1, v6 S0-01): a brand's free folders of video ideas, scripts and quick
clips; a folder can sit inside another (`parent_id`, null: at the top). The table is "folders"
because a video is already a project here. A deleted one is kept (deleted_at), with the
folders inside it, so Undo brings them back with their items; until then an item filed in one
reads as Unsorted. Items link by folder_id (null: Unsorted, v5's "No project")."""

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, object_session

from app.db import Base, Entity


class Folder(Entity, Base):
    __tablename__ = "folders"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    deleted_at: Mapped[datetime | None]


class Filed:
    """An item that can be filed in a folder: `live_folder_id` is its folder, or None for
    Unsorted (none, or a deleted one)."""

    @property
    def live_folder_id(self) -> int | None:
        if not self.folder_id:
            return None
        folder = object_session(self).get(Folder, self.folder_id)
        return folder.id if folder is not None and folder.deleted_at is None else None
