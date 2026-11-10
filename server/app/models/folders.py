"""Folders (flows OR1, v6 S0-01): a brand's free folders of video ideas, scripts and quick
clips; a folder can sit inside another (`parent_id`, null: at the top). The table is "folders"
because a video is already a project here. A deleted one is kept (deleted_at), with the
folders inside it, so Undo brings them back with their items; until then an item filed in one
reads as Unsorted. Items link by folder_id (null: Unsorted, v5's "No project"). A brand's
footage has a tree of its own (`footage`, Reed 10 Nov), apart from the video and script one;
a clip in a deleted footage folder reads as one level up, until Undo puts it back."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, func, text
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
    footage: Mapped[bool] = mapped_column(default=False)  # a folder of the brand's footage


# One live footage folder of a name in its place, whatever the case: two uploads making the
# same folder path at once make it once (app.folders.made; QA on #1514).
LIVE_FOOTAGE = text("footage AND deleted_at IS NULL")
Index("uq_folders_footage_name", Folder.brand_id, func.coalesce(Folder.parent_id, 0),
      func.lower(Folder.name), unique=True, sqlite_where=LIVE_FOOTAGE,
      postgresql_where=LIVE_FOOTAGE)  # fmt: skip


class Filed:
    """An item that can be filed in a folder: `live_folder_id` is its folder, or None for
    Unsorted (none, or a deleted one; footage: the first live folder it's inside, or the top)."""

    @property
    def live_folder_id(self) -> int | None:
        db = object_session(self)
        folder = db.get(Folder, self.folder_id) if self.folder_id else None
        while folder is not None and folder.deleted_at is not None and folder.footage:
            folder = db.get(Folder, folder.parent_id) if folder.parent_id else None
        return folder.id if folder is not None and folder.deleted_at is None else None
