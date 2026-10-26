"""Clip prompts: Claude writes one Seedance prompt per clip of the newest breakdown, with its
references (storyboard frame, cast, place, screens, voice samples). Saved per clip with the
problems `check.clip_prompts` finds; the editor can edit them before generating."""

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.advice import names, plain
from app.breakdown import video_model, video_model_block
from app.enhance import escape, project_context
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts import check
from app.prompts.schemas import Breakdown, ClipPrompt, ClipPrompts
from app.storyboard import assets as picture_assets

# asset id -> (line for the prompt, kind for Seedance, its file ids)
Assets = dict[str, tuple[str, str, list[int]]]


def assets(db: Session, project: Project) -> Assets:
    """Pictures (as for the storyboard), each clip's rendered storyboard frame, and the cast's
    voice samples."""
    out: Assets = {
        k: (line, "image", files) for k, (line, files) in picture_assets(db, project).items()
    }
    frames = db.scalars(
        select(StoryboardFrame).where(
            StoryboardFrame.project_id == project.id, StoryboardFrame.file_id.is_not(None)
        )
    )
    for f in frames:
        key = f"frame:{f.clip_id}"
        out.setdefault(key, (f"{key} | storyboard frame | clip {f.clip_id}", "image", [f.file_id]))
    for char_id in project.cast_ids:
        item = db.get(LibraryItem, char_id)
        if item and item.voice_file_id:
            key = f"voice:{item.id}"
            out[key] = (f"{key} | voice sample | {item.name}", "audio", [item.voice_file_id])
    return out


def job_input(db: Session, project: Project, bd: BreakdownVersion) -> dict:
    system, _ = project_context(db, project, "clip_prompts")
    lines = "\n".join(dict.fromkeys(line for line, _, _ in assets(db, project).values()))
    prompt = "\n".join(
        [
            video_model_block(video_model()),
            f"<assets>\n{escape(lines)}\n</assets>",
            f"<breakdown>\n{escape(json.dumps(bd.data, ensure_ascii=False))}\n</breakdown>",
        ]
    )
    return {
        "step": "clip_prompts",
        "project_id": project.id,
        "breakdown_id": bd.id,
        "system": system,
        "prompt": prompt,
        "max_tokens": 32000,
    }


def clip_problems(db: Session, project: Project, bd: Breakdown, clip: ClipPrompt) -> list[str]:
    m = video_model()
    problems = check.clip_prompts(
        bd, ClipPrompts(clips=[clip]), m.max_reference_images, m.max_reference_audios
    )
    known = assets(db, project)
    for ref in clip.references:
        if ref.id not in known:
            problems.append(f"{clip.clip_id}: unknown reference {ref.id}")
        elif known[ref.id][1] != ref.kind:
            kind = {"image": "a picture", "audio": "a sound"}.get(ref.kind, f"a {ref.kind}")
            problems.append(f"{clip.clip_id}: {ref.id} is attached as {kind} but isn't one")
    return plain(problems, names(known))


def save_clip_prompts(db: Session, job: Job) -> None:
    """Claude's new prompts, written into the clips they're for (Reed, 2026-10-26: Clips never
    dead-ends): matched by clip id, a clip gets its new prompt, references and problems for the
    new breakdown, and its takes stay as earlier takes (each keeps the prompt it was made
    from). Only the clips the job is for (`clip_ids`, e.g. the stale ones) change; a clip the
    new breakdown no longer has is removed (its take files stay in storage); a new one is
    added. Approval and "Looks good" are cleared on every rewritten clip."""
    project = db.get(Project, job.input["project_id"])
    bd_row = db.get(BreakdownVersion, job.input["breakdown_id"])
    bd = Breakdown.model_validate(bd_row.data)
    result = ClipPrompts.model_validate(job.output)
    only = job.input.get("clip_ids")  # None: every clip
    mine = select(ProjectClip).where(ProjectClip.project_id == project.id)
    rows = {r.clip_id: r for r in db.scalars(mine)}
    wanted = {c.id for c in bd.clips}
    for clip_id, row in rows.items():
        if clip_id not in wanted:  # gone from the breakdown: its takes' files stay
            row.picked_take_id = None
            db.flush()
            db.execute(delete(ClipTake).where(ClipTake.clip_id == row.id))
            db.delete(row)
    for c in result.clips:
        if c.clip_id not in wanted or (only is not None and c.clip_id not in only):
            continue
        row = rows.get(c.clip_id)
        if row is None:
            row = ProjectClip(project_id=project.id, clip_id=c.clip_id)
            db.add(row)
        else:
            for take in db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id)):
                take.prompt = take.prompt if take.prompt is not None else row.prompt
        row.breakdown_id, row.job_id, row.seconds = bd_row.id, job.id, c.seconds
        row.prompt, row.references = c.prompt, [r.model_dump() for r in c.references]
        row.problems, row.kept = clip_problems(db, project, bd, c), []
        row.approved, row.prompt_ok, row.change = False, False, None


WAITING = ("queued", "running", "needs_owner_approval")


def newest(db: Session, project: Project) -> BreakdownVersion | None:
    return db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )


def is_stale(db: Session, row: ProjectClip, latest_bd: BreakdownVersion | None) -> bool:
    """Made from an older breakdown, or the breakdown is for an older script version."""
    from app.routes.scripts import latest

    working = latest(db, db.get(Project, row.project_id))
    return (
        not latest_bd
        or row.breakdown_id != latest_bd.id
        or bool(working and latest_bd.script_version != working.version)
    )


def to_rewrite(db: Session, project: Project, clip_id: str | None = None) -> list[str]:
    """The clips a rewrite is for: one clip, or every stale clip and any clip the newest
    breakdown has that doesn't exist yet. [] when there's nothing to rewrite."""
    bd = newest(db, project)
    if bd is None:
        return []
    rows = list(db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)))
    ids = [c.id for c in Breakdown.model_validate(bd.data).clips]
    if clip_id is not None:
        return [clip_id] if clip_id in ids else []
    have = {r.clip_id for r in rows}
    stale = {r.clip_id for r in rows if is_stale(db, r, bd)}
    return [i for i in ids if i in stale or i not in have] if rows else []


def rewrite_price(db: Session, project: Project) -> Decimal:
    """One clip-prompts call, whatever it rewrites; never charged above it (worker)."""
    from app.credits import estimate

    return estimate(db, project.workspace_id, "write-claude", Decimal(1))


def _waiting(db: Session, project: Project) -> set[str]:
    jobs = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    return {j.input.get("step") for j in jobs}


def queue_rewrite(db: Session, user, project: Project, clip_ids: list[str] | None) -> Job:
    """The clip-prompts call (paid) for `clip_ids` (None: every clip)."""
    from app.routes.jobs import enqueue

    bd = newest(db, project)
    if bd is None:
        raise HTTPException(409, "Make a breakdown first.")
    waiting = _waiting(db, project)
    if "clip_take" in waiting:  # a take on its way would land on a rewritten or removed clip
        raise HTTPException(409, "Wait for the clips being made to finish first.")
    if "clip_prompts" in waiting:
        raise HTTPException(409, "Clip prompts are already being written for this project.")
    data = {**job_input(db, project, bd), "clip_ids": clip_ids}
    return enqueue(db, user, "write-claude", data, project=project, provider="claude")


def follow(db: Session, project: Project, user) -> Job | None:
    """After a breakdown change: stale clip prompts are rewritten by themselves (Reed,
    2026-10-26), like frames. Paid, so only within the video's budget or the editor's week
    (the owner's work too, as for looks Assets makes); past it, or while a take is being
    made, nothing is queued and Clips keeps its Rewrite button. Never blocks the change."""
    from app.credits import fits

    ids = to_rewrite(db, project)
    if not ids or "clip_take" in _waiting(db, project) or not user:
        return None
    if fits(db, project, user, rewrite_price(db, project)):
        return None
    db.commit()  # a refusal rolls back: never take the breakdown change with it
    try:
        return queue_rewrite(db, user, project, ids)
    except HTTPException:
        return None
