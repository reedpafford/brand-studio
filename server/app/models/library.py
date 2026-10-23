"""Brand libraries: characters, places and props. An item can belong to several brands.
Every edit saves the previous state as a version, so changes can be undone."""

from enum import StrEnum

from sqlalchemy import JSON, Column, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, Entity
from app.models.brands import Brand


class Kind(StrEnum):
    character = "character"
    place = "place"
    prop = "prop"


item_brands = Table(
    "library_item_brands",
    Base.metadata,
    Column("item_id", ForeignKey("library_items.id", ondelete="CASCADE"), primary_key=True),
    Column("brand_id", ForeignKey("brands.id", ondelete="CASCADE"), primary_key=True),
)


class LibraryItem(Entity, Base):
    __tablename__ = "library_items"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    kind: Mapped[Kind] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    image_file_ids: Mapped[list[int]] = mapped_column(JSON, default=list)  # sheet / reference
    # Characters only: [{"name": "Gym kit", "file_ids": [..]}], and a voice sample.
    outfits: Mapped[list[dict]] = mapped_column(JSON, default=list)
    voice_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    version: Mapped[int] = mapped_column(default=1)
    archived: Mapped[bool] = mapped_column(default=False)

    brands: Mapped[list[Brand]] = relationship(secondary=item_brands)


class LibraryItemVersion(Entity, Base):
    __tablename__ = "library_item_versions"
    item_id: Mapped[int] = mapped_column(
        ForeignKey("library_items.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int]
    snapshot: Mapped[dict] = mapped_column(JSON)
    saved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
