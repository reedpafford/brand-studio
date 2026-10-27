"""Launch brands (fomo, Iron Paws) and import of their real screens from the repo assets.

Runs on first setup. To import screens later: `python -m app.seed <folder> [brand-slug]`.
After a manifest change (new screens, moments, tags), bring live databases up to date with
`python -m app.seed refresh`: every workspace's launch brands get the new screens, and screens
named in a manifest take its tags, moments and product/variant. New script draft files
(docs/references/**/DRAFT-<brand>.json) are added to the library once (app/seed_drafts.py).
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

from sqlalchemy import func, select
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
                balance=meta.get("balance", ""),
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
        screen.balance = meta.get("balance", "")


def repair_frames(db: Session) -> int:
    """Frames saved before every shot's people got their sheets (Reed's live test): fixed
    for free, with no model call; running it again changes nothing."""
    from app.models.projects import Project
    from app.models.storyboards import StoryboardFrame
    from app.storyboard import repair

    ids = db.scalars(select(StoryboardFrame.project_id).distinct()).all()
    changed = sum(repair(db, db.get(Project, pid)) for pid in ids)
    db.commit()
    return changed


def repair_clips(db: Session) -> int:
    """Clips saved before the server attached their characters' sheets (Reed: a look read
    as not approved): fixed for free, with no model call; running it again changes nothing."""
    from app.clip_prompts import repair
    from app.models.clips import ProjectClip
    from app.models.projects import Project

    ids = db.scalars(select(ProjectClip.project_id).distinct()).all()
    changed = sum(repair(db, db.get(Project, pid)) for pid in ids)
    db.commit()
    return changed


def repair_missing_roles(db: Session) -> list[str]:
    """Every speaker in a script is a role, and every role is in its shots (Reed, 2026-10-27,
    "Marriage Rejection": made before the cast read, its groom was never a role): every
    script still in use gets the speakers it's missing, and every video `complete_cast`.
    Free, no model call. One plain line per script or video changed, then always a summary
    (the live log has to show it ran); running it again changes nothing."""
    from app import breakdown
    from app.models.projects import Project
    from app.models.script_library import Script, ScriptDraft

    out, scripts, videos = [], 0, 0
    live = select(Script).where(Script.deleted_at.is_(None), Script.archived.is_(False))
    for script in (checked := db.scalars(live).all()):
        added = breakdown.add_speakers(db, script)
        out += [f"{script.title}: added {name} to the cast" for name in added]
        scripts += bool(added)
    made = select(Project).where(Project.script_draft_id.in_(select(ScriptDraft.id)))
    for project in (projects := db.scalars(made).all()):
        lines = breakdown.complete_cast(db, project)
        out += [line for line in lines if not line.endswith(" to the cast")]
        videos += any(not line.endswith(" to the cast") for line in lines)
    db.commit()
    unlinked = db.scalar(
        select(func.count()).select_from(Project).where(Project.script_draft_id.is_(None))
    )
    return [*out, f"Missing roles: gave {scripts} of {len(checked)} scripts their speakers and "
            f"{videos} of {len(projects)} videos the roles in their shots ({unlinked} older "
            "videos have no library script, so they have no roles to add)."]  # fmt: skip


def repair_unknown_cast(db: Session) -> tuple[int, list[str]]:
    """Saved breakdowns (videos' newest, and library plans) that name someone the video
    doesn't have, like a deleted look still cast in a role (Kel's empty chair): landed again
    for free (breakdown.land), so the shot shows that role and its look is made at Assets.
    Returns how many were fixed and one plain line per change or per video still naming
    someone (none expected). Running it again changes nothing."""
    from app import breakdown, script_preview
    from app.models.breakdowns import BreakdownVersion
    from app.models.projects import Project
    from app.models.script_library import Script, ScriptDraft
    from app.prompts.schemas import Breakdown
    from app.routes.scripts import latest

    fixed, still = 0, []
    for project in db.scalars(select(Project)).all():
        row = db.scalar(
            select(BreakdownVersion)
            .where(BreakdownVersion.project_id == project.id)
            .order_by(BreakdownVersion.id.desc())
            .limit(1)
        )
        if row is None:
            continue
        bd, removed = breakdown.land(db, project, Breakdown.model_validate(row.data))
        if removed:
            script = latest(db, project)
            row.data = bd.model_dump()
            row.problems = breakdown.problems(db, project, script.text if script else "", bd)
            row.problems += removed
            fixed += 1
            still += [f"{project.name}: {n.removeprefix('Advice: ')}" for n in removed]
        if breakdown.unknown_ids(db, project, bd):
            still.append(f"Still names someone it doesn't have: {project.name}")
    for draft in db.scalars(select(ScriptDraft).where(ScriptDraft.breakdown.is_not(None))).all():
        if not draft.breakdown:  # a deleted plan is stored as JSON null, which passes the filter
            continue
        script = db.get(Script, draft.script_id)
        stand_in = script_preview.stand_in_project(db, script, draft)
        also = script_preview.live_looks(db, script)
        bd, removed = breakdown.land(db, stand_in, Breakdown.model_validate(draft.breakdown), also)
        if removed:
            draft.breakdown = bd.model_dump()
            draft.breakdown_problems = script_preview.problems(db, script, draft, bd) + removed
            fixed += 1
    db.commit()
    return fixed, still


def main(folder: str, slug: str = "fomo") -> None:
    from app.credits import seed_rates
    from app.db import make_sessionmaker
    from app.seed_drafts import import_drafts
    from app.settings import get_settings
    from app.storage import LocalStorage

    settings = get_settings()
    storage = LocalStorage(settings.storage_dir)
    with make_sessionmaker(settings.database_url)() as db:
        if folder == "refresh":
            for workspace_id in db.scalars(select(Workspace.id)).all():
                seed_brands(db, workspace_id, storage, settings.brand_assets_dir)
                seed_rates(db, workspace_id)  # a new kind (the look check) gets its rate
            print("Launch brands brought up to date from the manifests.")
            made = import_drafts(db, settings.references_dir)
            print(f"Imported {made} new script drafts into the library.")
            for line in repair_missing_roles(db):  # before the frames and clips get sheets
                print(line)
            print(f"Gave {repair_frames(db)} frames their characters' sheets.")
            print(f"Gave {repair_clips(db)} clips their characters' sheets.")
            fixed, said = repair_unknown_cast(db)
            print(f"Fixed who's in the shots of {fixed} saved breakdowns.")
            for line in said:
                print(line)
            return
        brand = db.scalar(select(Brand).where(Brand.slug == slug))
        if not brand:
            sys.exit(f"No {slug} brand yet. Run first-time setup first.")
        count = import_screens(db, storage, brand, Path(folder))
        print(f"Imported {count} screens into {slug}.")


if __name__ == "__main__":
    main(*sys.argv[1:3])
