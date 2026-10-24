"""Launch brands (fomo, Iron Paws) and import of their real screens from the repo assets.

Runs on first setup. To import screens later: `python -m app.seed <folder> [brand-slug]`.
After a manifest change (new screens, moments, tags), bring live databases up to date with
`python -m app.seed refresh`: every workspace's launch brands get the new screens, and screens
named in a manifest take its tags, moments and product/variant.
A folder may hold `screens.json`:
{"file.png": {"name": "...", "tags": [...], "default_for": [...]}}.
Without it, tags come from words in the filename (e.g. `trading-chart-up-mobile.png`).
"""

import hashlib
import json
import logging
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.filetypes import matches
from app.models.accounts import Workspace
from app.models.brands import Brand, BrandScreen
from app.models.files import StoredFile
from app.routes.screens import COMMON_TAGS
from app.schemas import slugify
from app.storage import Storage

log = logging.getLogger(__name__)
# Launch brands and their folder under assets/brands/ (screens in <folder>/screens).
LAUNCH_BRANDS = {"fomo": "fomo", "Iron Paws": "ironpaws"}
# Reed, 2026-10-23: every fomo video ends on this (Iron Paws' closing line comes from the brief).
END_LINES = {"fomo": "Want to trade like me? Download fomo through the link in my bio."}
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def seed_brands(db: Session, workspace_id: int, storage: Storage, assets_dir: str = "") -> None:
    """Create the launch brands, then import each one's screens, logo and style board from
    `assets_dir/<folder>/screens` when that folder exists."""
    for name in LAUNCH_BRANDS:
        slug = slugify(name)
        brand = db.scalar(
            select(Brand).where(Brand.workspace_id == workspace_id, Brand.slug == slug)
        )
        if brand and not brand.end_line and END_LINES.get(name):
            brand.end_line = END_LINES[name]  # a brand made before end lines existed
        if not brand:
            db.add(
                Brand(
                    workspace_id=workspace_id,
                    name=name,
                    slug=slug,
                    end_line=END_LINES.get(name, ""),
                )
            )
    db.commit()
    for name, folder in LAUNCH_BRANDS.items():
        screens = Path(assets_dir) / folder / "screens" if assets_dir else None
        if screens and screens.is_dir():
            brand = db.scalar(
                select(Brand).where(Brand.workspace_id == workspace_id, Brand.slug == slugify(name))
            )
            import_screens(db, storage, brand, screens)


def _guess(stem: str) -> dict:
    slug = slugify(stem)
    tags = [t for t in COMMON_TAGS if t in slug]
    return {"tags": tags, "default_for": ["trading"] if "trading" in tags else []}


def _store(storage: Storage, workspace_id: int, path: Path) -> StoredFile | None:
    """Copy one image file into storage, or None if it isn't really the image it claims."""
    content_type = IMAGE_TYPES.get(path.suffix.lower())
    data = path.read_bytes() if content_type else b""
    if not content_type or not matches(content_type, data[:16]):
        log.warning("Skipping %s: not an allowed image.", path.name)
        return None
    key = f"{workspace_id}/{uuid.uuid4().hex}"
    storage.put(key, data)
    return StoredFile(
        workspace_id=workspace_id,
        key=key,
        filename=path.name,
        content_type=content_type,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def import_screens(db: Session, storage: Storage, brand: Brand, folder: Path) -> int:
    """Add each image in `folder` as a screen. Skips names the brand already has.
    Also fills the brand's logo and style board from `logo.png` / `style-board.png` in the
    folder above, if the brand has none yet."""
    manifest_path = folder / "screens.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    existing = set(db.scalars(select(BrandScreen.name).where(BrandScreen.brand_id == brand.id)))
    added = 0
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in IMAGE_TYPES:
            continue
        meta = manifest.get(path.name) or _guess(path.stem)
        name = meta.get("name") or path.stem
        if name in existing:
            if path.name in manifest:
                _refresh(db, brand, name, meta)  # the manifest changed since it was imported
            continue
        stored = _store(storage, brand.workspace_id, path)
        if stored is None:
            continue
        db.add(
            BrandScreen(
                brand_id=brand.id,
                name=name,
                file=stored,
                tags=sorted(set(meta.get("tags", []))),
                default_for=sorted(set(meta.get("default_for", []))),
                product=meta.get("product", ""),
                variant=meta.get("variant", ""),
            )
        )
        existing.add(name)
        added += 1
    for field, filename in (
        ("logo_file_id", "logo.png"),
        ("style_board_file_id", "style-board.png"),
    ):
        path = folder.parent / filename
        if getattr(brand, field) is None and path.exists():
            stored = _store(storage, brand.workspace_id, path)
            if stored:
                db.add(stored)
                db.flush()
                setattr(brand, field, stored.id)
    db.commit()
    return added


def _refresh(db: Session, brand: Brand, name: str, meta: dict) -> None:
    screen = db.scalar(
        select(BrandScreen).where(BrandScreen.brand_id == brand.id, BrandScreen.name == name)
    )
    if screen:
        screen.tags = sorted(set(meta.get("tags", [])))
        screen.default_for = sorted(set(meta.get("default_for", [])))
        screen.product, screen.variant = meta.get("product", ""), meta.get("variant", "")


def main(folder: str, slug: str = "fomo") -> None:
    from app.db import make_sessionmaker
    from app.settings import get_settings
    from app.storage import LocalStorage

    settings = get_settings()
    storage = LocalStorage(settings.storage_dir)
    with make_sessionmaker(settings.database_url)() as db:
        if folder == "refresh":
            for workspace_id in db.scalars(select(Workspace.id)).all():
                seed_brands(db, workspace_id, storage, settings.brand_assets_dir)
            print("Launch brands brought up to date from the manifests.")
            return
        brand = db.scalar(select(Brand).where(Brand.slug == slug))
        if not brand:
            sys.exit(f"No {slug} brand yet. Run first-time setup first.")
        count = import_screens(db, storage, brand, Path(folder))
        print(f"Imported {count} screens into {slug}.")


if __name__ == "__main__":
    main(*sys.argv[1:3])
