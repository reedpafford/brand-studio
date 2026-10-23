"""Launch brands (fomo, Iron Paws) and import of fomo's real UI screens from a folder.

Runs on first setup. To import screens later: `python -m app.seed <folder>`.
A folder may hold `screens.json`: {"file.png": {"tags": [...], "default_for": [...]}}.
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
from app.models.brands import Brand, BrandScreen
from app.models.files import StoredFile
from app.routes.screens import COMMON_TAGS
from app.schemas import slugify
from app.storage import Storage

log = logging.getLogger(__name__)
LAUNCH_BRANDS = ["fomo", "Iron Paws"]
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def seed_brands(db: Session, workspace_id: int, storage: Storage, fomo_dir: str = "") -> None:
    for name in LAUNCH_BRANDS:
        slug = slugify(name)
        if not db.scalar(
            select(Brand).where(Brand.workspace_id == workspace_id, Brand.slug == slug)
        ):
            db.add(Brand(workspace_id=workspace_id, name=name, slug=slug))
    db.commit()
    if fomo_dir:
        fomo = db.scalar(
            select(Brand).where(Brand.workspace_id == workspace_id, Brand.slug == "fomo")
        )
        import_screens(db, storage, fomo, Path(fomo_dir))


def _guess(stem: str) -> dict:
    slug = slugify(stem)
    tags = [t for t in COMMON_TAGS if t in slug]
    return {"tags": tags, "default_for": ["trading"] if "trading" in tags else []}


def import_screens(db: Session, storage: Storage, brand: Brand, folder: Path) -> int:
    """Add each image in `folder` as a screen. Skips names the brand already has."""
    manifest_path = folder / "screens.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    existing = set(db.scalars(select(BrandScreen.name).where(BrandScreen.brand_id == brand.id)))
    added = 0
    for path in sorted(folder.iterdir()):
        content_type = IMAGE_TYPES.get(path.suffix.lower())
        if not content_type or path.stem in existing:
            continue
        data = path.read_bytes()
        if not matches(content_type, data[:16]):
            log.warning("Skipping %s: contents don't match its extension.", path.name)
            continue
        key = f"{brand.workspace_id}/{uuid.uuid4().hex}"
        storage.put(key, data)
        stored = StoredFile(
            workspace_id=brand.workspace_id,
            key=key,
            filename=path.name,
            content_type=content_type,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
        meta = manifest.get(path.name) or _guess(path.stem)
        db.add(
            BrandScreen(
                brand_id=brand.id,
                name=path.stem,
                file=stored,
                tags=sorted(set(meta.get("tags", []))),
                default_for=sorted(set(meta.get("default_for", []))),
            )
        )
        added += 1
    db.commit()
    return added


def main(folder: str) -> None:
    from app.db import make_sessionmaker
    from app.settings import get_settings
    from app.storage import LocalStorage

    settings = get_settings()
    with make_sessionmaker(settings.database_url)() as db:
        fomo = db.scalar(select(Brand).where(Brand.slug == "fomo"))
        if not fomo:
            sys.exit("No fomo brand yet. Run first-time setup first.")
        count = import_screens(db, LocalStorage(settings.storage_dir), fomo, Path(folder))
        print(f"Imported {count} screens into fomo.")


if __name__ == "__main__":
    main(sys.argv[1])
