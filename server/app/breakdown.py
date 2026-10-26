"""Breakdown: Claude turns the working script into scenes, shots and clips. The answer is
checked (`check.breakdown`) and saved with its problems so the editor sees what to fix."""

from inspect import signature

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.catalogue import CatalogueModel, catalogue
from app.enhance import escape, escape_block, project_context, project_screens
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.scripts import ScriptVersion
from app.prompts import check
from app.prompts.schemas import Breakdown


def video_model() -> CatalogueModel:
    """The video model clips are planned for (one per project, FIT row 23: the default)."""
    return next(m for m in catalogue().values() if m.kind == "video" and m.default)


def video_model_block(m: CatalogueModel) -> str:
    return (
        f"<video_model>{m.name}: {m.duration.min}–{m.duration.max} s per clip, up to "
        f"{m.max_reference_images} reference images (prefer "
        f"{m.recommended_reference_images or m.max_reference_images} or fewer), "
        f"{m.max_reference_audios} audios</video_model>"
    )


def _places(db: Session, project: Project) -> str:
    items = db.scalars(
        select(LibraryItem).where(
            LibraryItem.workspace_id == project.workspace_id,
            LibraryItem.kind == Kind.place,
            LibraryItem.archived.is_(False),
        )
    )
    lines = [
        f"place:{p.id} | {p.name} | {p.notes}"
        for p in items
        if any(b.id == project.brand_id for b in p.brands)
    ]
    return "\n".join(lines)


def job_input(db: Session, project: Project, version: ScriptVersion) -> dict:
    system, context = project_context(db, project, "breakdown")
    if project.script_draft_id:  # from the library: its unlocked slots, cast at Assets
        from app import script_preview
        from app.models.script_library import ScriptDraft

        draft = db.get(ScriptDraft, project.script_draft_id)
        context = script_preview.with_slots(db, draft.script_id, context, project.slot_cast)
    parts = [context, f"<places>\n{escape(_places(db, project))}\n</places>"]
    parts.append(video_model_block(video_model()))
    if project.reference_breakdown:
        ref = prompts.reference_block(project.reference_breakdown, project.reference_replace)
        parts.append(escape_block(ref))
    parts.append(f"<script>\n{escape(prompts.number_lines(version.text))}\n</script>")
    return {
        "step": "breakdown",
        "project_id": project.id,
        "script_version": version.version,
        "system": system,
        "prompt": "\n".join(parts),
        "max_tokens": 32000,
    }


def problems(db: Session, project: Project, script: str, bd: Breakdown) -> list[str]:
    screens = {f"screen:{s.id}": s.default_for for s in project_screens(db, project)}
    m = video_model()
    brand = db.get(Brand, project.brand_id)
    # The Director's check takes the brand's end line (#107); older checks don't yet.
    params = signature(check.breakdown).parameters
    extra = {"end_line": brand.end_line} if "end_line" in params else {}
    if "brand" in params:
        extra["brand"] = brand.name
    if "approved" in params:  # a video from the library is made from an approved version
        extra["approved"] = project.script_draft_id is not None
    found = check.breakdown(script, bd, screens, m.duration.min, m.duration.max, **extra)
    from app.advice import names, plain
    from app.storyboard import assets

    found += unknown_ids(db, project, bd) + cast_problems(db, project, script, bd)
    return plain(found, names(assets(db, project)))


def cast_problems(db: Session, project: Project, script: str, bd: Breakdown) -> list[str]:
    """Shots that show the wrong person for a role their lines name. They stop stills until
    fixed ("Put the right cast in each shot", free) or kept anyway."""
    from app.advice import CAST
    from app.cast_roles import mismatches

    def who(ref: str) -> str:
        item = db.get(LibraryItem, int(ref[5:])) if ref.startswith("char:") else None
        return item.name if item else "no look yet"

    out = []
    for shot, missing, wrong in mismatches(db, project, script, bd):
        roles = " and ".join(role for role, _ in missing)
        should = " and ".join(who(c) for _, c in missing if c.startswith("char:"))
        shown = " and ".join(f"{who(c)} ({role})" for role, c in wrong)
        out.append(
            f"{CAST}shot {shot.id}: the script has {roles} here, but the shot shows {shown}"
            + (f" instead of {should}" if should else "")
        )
    return out


def unknown_ids(db: Session, project: Project, bd: Breakdown) -> list[str]:
    """Characters, places and screens a shot names that aren't this project's (cast, the
    brand's places, the brand's screens). Clips use these ids to attach pictures."""
    from app.storyboard import assets

    known = assets(db, project)
    return [
        f"shot {shot.id}: unknown {asset}"
        for scene in bd.scenes
        for shot in scene.shots
        for asset in [*shot.character_ids, shot.place_id, *shot.screen_ids]
        if asset and asset not in known
    ]


def record_length(project: Project, bd: Breakdown) -> None:
    """The newest breakdown sets the length when none was set (its clips added up)."""
    project.breakdown_seconds = sum(clip.seconds for clip in bd.clips) or None


def as_roles(db: Session, project: Project, bd: Breakdown) -> Breakdown:
    from app.cast_roles import as_roles as roles

    return roles(db, project, bd)


def save_breakdown(db: Session, job: Job) -> None:
    """Store Claude's breakdown (with its problems) as the project's newest breakdown, or on
    the library version it previews (workflow v2)."""
    if draft_id := job.input.get("script_draft_id"):
        from app import script_preview
        from app.models.script_library import Script, ScriptDraft

        draft = db.get(ScriptDraft, draft_id)
        stand_in = script_preview.stand_in_project(db, db.get(Script, draft.script_id), draft)
        script_preview.save(
            db,
            draft,
            as_roles(db, stand_in, Breakdown.model_validate(job.output)),
            job.created_by_id,
            job.input.get("script_text"),
        )
        return
    project = db.get(Project, job.input["project_id"])
    version = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.project_id == project.id,
            ScriptVersion.version == job.input["script_version"],
        )
    )
    bd = as_roles(db, project, Breakdown.model_validate(job.output))
    record_length(project, bd)
    db.add(
        BreakdownVersion(
            project_id=project.id,
            script_version=version.version,
            source="claude",
            job_id=job.id,
            data=bd.model_dump(),
            problems=problems(db, project, version.text, bd),
            created_by_id=job.created_by_id,
        )
    )
    from app import clip_prompts
    from app.models.accounts import User

    db.flush()  # stale clip prompts are rewritten, within budget (follow commits first)
    clip_prompts.follow(db, project, db.get(User, job.created_by_id))
