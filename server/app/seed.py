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


def plain_stored(db: Session) -> int:
    """Problems saved before they were said in plain words ("c3: char:3 …"): the clip id
    dropped and every id named, kept advice too, so a kept one stays kept. Free; running it
    again changes nothing."""
    from app import clip_prompts, storyboard
    from app.advice import names, plain
    from app.cast_roles import short
    from app.models.breakdowns import BreakdownVersion
    from app.models.clips import ProjectClip
    from app.models.projects import Project
    from app.models.script_library import ScriptCastSlot, ScriptDraft
    from app.models.storyboards import StoryboardFrame

    changed, called = 0, {}

    def fix(row, problems: str, kept: str, n: dict) -> int:
        old = (getattr(row, problems) or [], getattr(row, kept) or [])
        new = (plain(old[0], n), plain(old[1], n))
        if new == old:
            return 0
        setattr(row, problems, new[0])
        setattr(row, kept, new[1])
        return 1

    for model, assets in ((BreakdownVersion, storyboard.assets),
                          (StoryboardFrame, storyboard.assets),
                          (ProjectClip, clip_prompts.assets)):  # fmt: skip
        for row in db.scalars(select(model)):
            if row.problems or row.kept:
                key = (assets, row.project_id)
                if key not in called:
                    called[key] = names(assets(db, db.get(Project, row.project_id)))
                changed += fix(row, "problems", "kept", called[key])
    for draft in db.scalars(select(ScriptDraft)):
        if draft.breakdown_problems or draft.breakdown_kept:
            slots = db.scalars(
                select(ScriptCastSlot).where(ScriptCastSlot.script_id == draft.script_id)
            )
            n = {f"slot:{s.id}": short(s.role) or s.role for s in slots}
            changed += fix(draft, "breakdown_problems", "breakdown_kept", n)
    db.commit()
    return changed


def rewrite_owner_clips(db: Session) -> int:
    """Reed's current video, whose clips went stale before Clips could rewrite them (Reed,
    2026-10-26, #503): of the videos an owner made, the one edited most recently (its newest
    breakdown change) with stale clips gets its stale clip prompts rewritten once, free to
    him (one real Claude call, at most 3 credits' worth, charged to no budget or week; its
    dollars are in Usage). Only that one video, only once ever, and never while clip prompts
    or a take are being made on it. Others get the button, or the rewrite on their next
    change. How many videos were queued (0 or 1)."""
    from app import clip_prompts
    from app.job_brand import brand_for
    from app.models.accounts import Role, User
    from app.models.jobs import Job, JobStatus
    from app.models.projects import Project

    jobs = db.scalars(select(Job).where(Job.input["step"].as_string() == "clip_prompts"))
    if any(j.input.get("repair") for j in jobs):
        return 0  # done once already
    owners = {u.id: u for u in db.scalars(select(User).where(User.role == Role.owner))}
    candidates = []
    for project in db.scalars(select(Project).where(Project.created_by_id.in_(owners))):
        bd = clip_prompts.newest(db, project)
        if project.archived_at is None and bd and clip_prompts.to_rewrite(db, project):
            candidates.append((bd.id, project))
    if not candidates:
        return 0
    _, project = max(candidates, key=lambda c: c[0])  # the latest breakdown change
    mine = db.scalars(select(Job).where(Job.project_id == project.id))
    steps = {j.input.get("step") for j in mine if j.status in clip_prompts.WAITING}
    if steps & {"clip_prompts", "clip_take"}:
        return 0  # something is being made on it: the next deploy tries again
    bd = clip_prompts.newest(db, project)
    ids = clip_prompts.to_rewrite(db, project)
    data = {**clip_prompts.job_input(db, project, bd), "clip_ids": ids, "repair": True}
    owner = owners[project.created_by_id]
    db.add(Job(workspace_id=project.workspace_id, created_by_id=owner.id,
               approved_by_id=owner.id, kind="write-claude", provider="claude", input=data,
               project_id=project.id, brand_id=brand_for(db, project, data),
               credits=0, status=JobStatus.queued))  # fmt: skip
    db.commit()
    return 1


QA_OWNER = "QA Owner"  # the live test's owner account (Reed, 2026-10-26: remove it)


def remove_qa_owner(db: Session) -> bool:
    """Remove the QA test owner: only an owner named exactly "QA Owner", and never a
    workspace's last active owner. With nothing of its own it's deleted; otherwise it's
    removed as Team's Remove does (it can't sign in, its sessions and the invites it sent are
    gone) so the work it made keeps its history. True when there was something to do;
    running it again changes nothing."""
    from sqlalchemy import delete, func

    from app.db import Base
    from app.models.accounts import Invite, LoginSession, Role, User

    found = False
    for user in db.scalars(select(User).where(User.name == QA_OWNER, User.role == Role.owner)):
        others = select(func.count(User.id)).where(
            User.workspace_id == user.workspace_id,
            User.role == Role.owner,
            User.active.is_(True),
            User.id != user.id,
        )
        if not db.scalar(others):
            continue  # never a workspace's last active owner: nobody could run it
        sessions = delete(LoginSession).where(LoginSession.user_id == user.id)
        invites = delete(Invite).where(
            Invite.invited_by_id == user.id, Invite.accepted_at.is_(None)
        )
        changed = bool(db.execute(sessions).rowcount + db.execute(invites).rowcount)
        uses = [
            db.scalar(select(func.count()).select_from(table).where(column == user.id))
            for table in Base.metadata.sorted_tables
            for column in table.columns
            for fk in column.foreign_keys
            if fk.column.table.name == "users" and table.name != "login_sessions"
        ]
        if not any(uses):
            db.delete(user)
            changed = True
        elif user.active:
            user.active, changed = False, True
        found = found or changed
    db.commit()
    return found


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
            print(f"Gave {repair_frames(db)} frames their characters' sheets.")
            print(f"Gave {repair_clips(db)} clips their characters' sheets.")
            print(f"Said {plain_stored(db)} saved checks in plain words.")
            if rewrite_owner_clips(db):
                print("Rewrote clip prompts on 1 video.")
            if remove_qa_owner(db):
                print("Removed the QA test owner.")
            return
        brand = db.scalar(select(Brand).where(Brand.slug == slug))
        if not brand:
            sys.exit(f"No {slug} brand yet. Run first-time setup first.")
        count = import_screens(db, storage, brand, Path(folder))
        print(f"Imported {count} screens into {slug}.")


if __name__ == "__main__":
    main(*sys.argv[1:3])
