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


def repair_cta_screens(db: Session) -> int:
    """Each video's newest breakdown whose end line's shot shows no screen gets the brand's
    balance (else home) screen and the hero, in place (breakdown.cta_screen); its frames
    and clips then attach it (repair_frames, repair_clips). Free; again changes nothing."""
    from app.breakdown import cta_screen
    from app.models.breakdowns import BreakdownVersion
    from app.models.projects import Project
    from app.prompts.schemas import Breakdown

    changed = 0
    for project in db.scalars(select(Project)).all():
        row = db.scalar(
            select(BreakdownVersion)
            .where(BreakdownVersion.project_id == project.id)
            .order_by(BreakdownVersion.id.desc())
            .limit(1)
        )
        if row is None or not row.data:  # JSON null passes SQL is_not(None)
            continue
        bd, notes = cta_screen(db, project, Breakdown.model_validate(row.data))
        if notes:
            row.data, row.problems = bd.model_dump(), [*(row.problems or []), *notes]
            changed += 1
    db.commit()
    return changed


def moment_problems(db: Session) -> int:
    """Saved checks that said "'fomo-mention' moment without its screen" as a block: said
    again with today's rule (advice, and any screen of the same kind counts: Reed,
    2026-10-27), so videos and plans lose the false blocker. Free; again changes nothing."""
    import re

    from app.enhance import project_screens
    from app.models.breakdowns import BreakdownVersion
    from app.models.projects import Project
    from app.models.script_library import Script, ScriptDraft
    from app.prompts.check import kinds_of, moment_screen
    from app.prompts.schemas import Breakdown
    from app.script_preview import stand_in_project

    said = re.compile(r"(?i)^(?:c\d+: )?shot (\S+): '.+' moment without its screen$")  # as saved

    def again(project: Project, data: dict, problems: list[str]) -> list[str] | None:
        if not any(said.match(p) for p in problems or []):
            return None
        shown = project_screens(db, project)
        screens = {f"screen:{s.id}": s.default_for for s in shown}
        kinds = kinds_of(shown)
        shots = {s.id: s for scene in Breakdown.model_validate(data).scenes for s in scene.shots}
        out = []
        for p in problems:
            m = said.match(p)
            out += [moment_screen(shots[m[1]], screens, kinds)] if m and m[1] in shots else [p]
        return [p for p in out if p]

    changed = 0
    for project in db.scalars(select(Project)).all():
        row = db.scalar(
            select(BreakdownVersion)
            .where(BreakdownVersion.project_id == project.id)
            .order_by(BreakdownVersion.id.desc())
            .limit(1)
        )
        if row and (new := again(project, row.data, row.problems)) is not None:
            row.problems, changed = new, changed + 1
    for draft in db.scalars(select(ScriptDraft)).all():
        if not draft.breakdown:  # a deleted plan is JSON null, which is_not(None) lets through
            continue
        stand_in = stand_in_project(db, db.get(Script, draft.script_id), draft)
        if (new := again(stand_in, draft.breakdown, draft.breakdown_problems)) is not None:
            draft.breakdown_problems, changed = new, changed + 1
    db.commit()
    return changed


def why(db: Session) -> list[str]:
    """What the two deploy repairs see, for someone to read on the live server (read-only,
    changes nothing): every saved brand-moment check as it's stored, and each video's
    end-line shot, whether it already shows a screen. `python -m app.seed why`"""
    from app.models.breakdowns import BreakdownVersion
    from app.models.projects import Project
    from app.models.script_library import ScriptDraft
    from app.prompts.check import ends_on
    from app.prompts.schemas import Breakdown

    out = []
    for draft in db.scalars(select(ScriptDraft)).all():
        for p in draft.breakdown_problems or []:
            if "moment without" in p.lower():
                out.append(f"Script {draft.script_id} version {draft.slot}: saved check {p!r}")
    for project in db.scalars(select(Project)).all():
        row = db.scalar(
            select(BreakdownVersion)
            .where(BreakdownVersion.project_id == project.id)
            .order_by(BreakdownVersion.id.desc())
            .limit(1)
        )
        if row is None or not row.data:
            continue
        name = f"Video {project.id} (plan {row.id})"
        out += [f"{name}: saved check {p!r}" for p in row.problems or []
                if "moment without" in p.lower()]  # fmt: skip
        brand = db.get(Brand, project.brand_id)
        if not brand.end_line.strip():
            continue
        shots = [s for sc in Breakdown.model_validate(row.data).scenes for s in sc.shots]
        said = [s for s in shots if s.line and ends_on(brand.end_line, s.line, brand.name) != "no"]
        if not said:
            last = next((s for s in reversed(shots) if s.line), None)
            out.append(f"{name}: no shot says the end line on its own; the last line is "
                       f"{last.line if last else None!r}")  # fmt: skip
        elif said[-1].screen_ids:
            out.append(f"{name}: end-line shot {said[-1].id} already shows {said[-1].screen_ids}")
        else:
            out.append(f"{name}: end-line shot {said[-1].id} shows no screen (would be fixed)")
    db.rollback()
    return out


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


def rewrite_owner_clips(db: Session) -> str:
    """Reed's current video, whose clips went stale before Clips could rewrite them (Reed,
    2026-10-26, #503): of the videos an owner made, the one edited most recently (its newest
    breakdown change) with stale clips gets its stale clip prompts rewritten once, free to
    him (one real Claude call, at most 3 credits' worth, charged to no budget or week; its
    dollars are in Usage). Only that one video, only once ever. A take waiting or held on a
    stale clip is cancelled first (it never started, so nothing was charged); one being made,
    or one on a clip that's up to date, waits for the next deploy. Others get the button, or
    the rewrite on their next change. One plain line for the deploy log, whatever happens."""
    from app import clip_prompts
    from app.job_brand import brand_for
    from app.models.accounts import Role, User
    from app.models.clips import ProjectClip
    from app.models.jobs import Job, JobStatus
    from app.models.projects import Project
    from app.routes.jobs import stop_jobs

    jobs = db.scalars(select(Job).where(Job.input["step"].as_string() == "clip_prompts"))
    if any(j.input.get("repair") for j in jobs):
        return "Clip prompts: already rewritten once."
    owners = {u.id: u for u in db.scalars(select(User).where(User.role == Role.owner))}
    candidates = []
    for project in db.scalars(select(Project).where(Project.created_by_id.in_(owners))):
        bd = clip_prompts.newest(db, project)
        if project.archived_at is None and bd and clip_prompts.to_rewrite(db, project):
            candidates.append((bd.id, project))
    if not candidates:
        return "Clip prompts: nothing to rewrite."
    _, project = max(candidates, key=lambda c: c[0])  # the latest breakdown change
    ids = clip_prompts.to_rewrite(db, project)
    waiting = [j for j in db.scalars(select(Job).where(Job.project_id == project.id))
               if j.status in clip_prompts.WAITING]  # fmt: skip
    if any(j.input.get("step") == "clip_prompts" for j in waiting):
        return f"Clip prompts: waiting, they're already being written on “{project.name}”."
    for take in (j for j in waiting if j.input.get("step") == "clip_take"):
        row = db.get(ProjectClip, take.input.get("project_clip_id") or 0)
        if take.status != JobStatus.running and (row is None or row.clip_id in ids):
            stop_jobs(db, Job.id == take.id)  # held only because its clip is out of date
        else:
            return f"Clip prompts: waiting, a take is still being made on “{project.name}”."
    bd = clip_prompts.newest(db, project)
    data = {**clip_prompts.job_input(db, project, bd), "clip_ids": ids, "repair": True}
    owner = owners[project.created_by_id]
    db.add(Job(workspace_id=project.workspace_id, created_by_id=owner.id,
               approved_by_id=owner.id, kind="write-claude", provider="claude", input=data,
               project_id=project.id, brand_id=brand_for(db, project, data),
               credits=0, status=JobStatus.queued))  # fmt: skip
    db.commit()
    return f"Rewrote clip prompts on “{project.name}”."


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
        if folder == "why":  # read-only
            print("\n".join(why(db)) or "Nothing to show.")
            return
        if folder == "refresh":
            for workspace_id in db.scalars(select(Workspace.id)).all():
                seed_brands(db, workspace_id, storage, settings.brand_assets_dir)
                seed_rates(db, workspace_id)  # a new kind (the look check) gets its rate
            print("Launch brands brought up to date from the manifests.")
            made = import_drafts(db, settings.references_dir)
            print(f"Imported {made} new script drafts into the library.")
            print(f"Said {moment_problems(db)} brand-moment checks as advice.")
            print(f"Gave {repair_cta_screens(db)} end-line shots the brand's screen.")
            print(f"Gave {repair_frames(db)} frames their characters' sheets.")
            print(f"Gave {repair_clips(db)} clips their characters' sheets.")
            print(f"Said {plain_stored(db)} saved checks in plain words.")
            print(rewrite_owner_clips(db))
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
