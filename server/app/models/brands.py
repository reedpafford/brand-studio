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

    # Brand kit
    logo_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    style_board_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    end_card_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    colours: Mapped[list[str]] = mapped_column(JSON, default=list)
    fonts: Mapped[list[str]] = mapped_column(JSON, default=list)
    tone_notes: Mapped[str] = mapped_column(Text, default="")
    never_say: Mapped[list[str]] = mapped_column(JSON, default=list)
    legal_line: Mapped[str] = mapped_column(Text, default="")
    end_line: Mapped[str] = mapped_column(
        Text, default=""
    )  # the default call to action every video ends on (Current rules 18)
    # Brand setup (flows BR1, n08). `never_say` and `end_line` stay until the move to main
    # and are written through (app/brand_setup.sync): never_say = dont_list, end_line = the
    # default CTA line's text. Next reads the new fields.
    audience: Mapped[str] = mapped_column(Text, default="")
    do_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    dont_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    cta_lines: Mapped[list[dict]] = mapped_column(
        JSON, default=list
    )  # {id, text, default, deleted_at}
    default_cast: Mapped[list[int]] = mapped_column(JSON, default=list)  # library character ids
    music_style: Mapped[str] = mapped_column(Text, default="")  # prefills new song versions
    default_language: Mapped[str] = mapped_column(String(10), default="en")
    default_look: Mapped[str] = mapped_column(String(40), default="house")  # new scripts' look


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
    # A product with several versions (e.g. product "bag", variant "Chicken" / "Peanut butter"):
    # each project picks one variant per product, and only that one is used.
    product: Mapped[str] = mapped_column(String(60), default="")
    variant: Mapped[str] = mapped_column(String(60), default="")
    balance: Mapped[str] = mapped_column(String(40), default="")  # as printed on it, if any
    deleted_at: Mapped[datetime | None]  # deleted, kept for Undo; never used while set
