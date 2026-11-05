"""Brands, their kit, and their screens (real app UI images that must appear exactly)."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, Entity
from app.models.files import StoredFile


class Brand(Entity, Base):
    __tablename__ = "brands"
    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120))
    archived: Mapped[bool] = mapped_column(default=False)
    hidden: Mapped[bool] = mapped_column(default=False)  # a freestyle's own (app/hidden.py)

    # Brand kit (v6 S8-05, S-gaps-05 L1): the rest is the script's and the director's
    logo_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    colours: Mapped[list[str]] = mapped_column(JSON, default=list)
    tone_notes: Mapped[str] = mapped_column(Text, default="")  # "Tone and rules"


class BrandScreen(Entity, Base):
    __tablename__ = "brand_screens"
    __table_args__ = (UniqueConstraint("brand_id", "name"),)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"))
    file: Mapped[StoredFile] = relationship()
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)  # e.g. trading, chart-up, mobile
    # Moments this screen is attached to by default, e.g. ["trading"] for fomo.
    default_for: Mapped[list[str]] = mapped_column(JSON, default=list)
    # A picture of a library product (v6 S8-06: the product is the record; its pictures link
    # to it). A product with several (e.g. "bag": "Chicken" / "Peanut butter") has a variant
    # each: each project picks one variant per product, and only that one is used.
    product_id: Mapped[int | None] = mapped_column(ForeignKey("library_items.id"), index=True)
    product_item = relationship("LibraryItem")
    variant: Mapped[str] = mapped_column(String(60), default="")
    balance: Mapped[str] = mapped_column(String(40), default="")  # as printed on it, if any
    # Where a shot's figure is written on it (screen_figures.py): {"box": [x0, y0, x1, y1]
    # cleared, "at": [x, y] of the number, "size": its px, "chart": [x0, y0, x1, y1] or none}.
    figure_spot: Mapped[dict | None] = mapped_column(JSON, default=None)
    deleted_at: Mapped[datetime | None]  # deleted, kept for Undo; never used while set

    @property
    def product(self) -> str:
        """The physical product it pictures, by name; "" for an app's screen (S-gaps-05 L1: an
        app is a product too, but its screens are drawn on and never checked as a pack)."""
        item = self.product_item
        return item.name if item is not None and item.product_type != "app" else ""
