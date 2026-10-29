"""A video's scene plan (flows.md 1b, P1/P2): the script's lines grouped into scenes, each with
its place, cast, one action per line and the ★ product moments, approved before the shots
(the breakdown) are made from it. The plan keeps line numbers only, never the words (rule 19).

`projects.plan` holds the Director's ScenePlan plus our fields (data.md): version, source,
approved_at, approved_by_id, job_id, made_for_text_hash. A video made before plans existed has
none stored: its plan is read from its breakdown the first time anyone asks (`current`), free
and approved, so it's never blocked."""

import hashlib
import re
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.credits import estimate
from app.db import utcnow
from app.enhance import escape, escape_block, project_context
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.scripts import ScriptVersion
from app.prompts import check
from app.prompts.schemas import Breakdown, ScenePlan

STEP = "plan"
KIND = "write-claude"
HISTORY = 10  # Earlier plans kept
LIMIT = timedelta(minutes=10)  # a plan still not back after this is stopped, uncharged
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
SLOW = "The plan took too long and was stopped. Nothing was charged."
FAILED = "The plan didn't finish. Nothing was charged."
STILL = "The plan still left out or repeated script lines after one more try: "
PLAN_FIRST = "Approve the plan first."


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def script(db: Session, project: Project) -> ScriptVersion | None:
    """The words the plan is for: the video's newest script, or a script version's own words
    for the owner's plan (S6, a stand-in project that is never saved)."""
    from app.routes.scripts import latest

    if project.id is None and project.script_draft_id:
        from app.models.script_library import ScriptDraft

        draft = db.get(ScriptDraft, project.script_draft_id)
        return ScriptVersion(text=draft.text, version=0)  # never added to the session
    return latest(db, project)


def for_version(db: Session, script, draft) -> Project:
    """The owner's plan on a script version (S6): the version's stand-in project, holding the
    version's plan, so every plan function works on it. `keep_version` writes it back."""
    from app.script_preview import stand_in_project

    stand = stand_in_project(db, script, draft)
    stand.plan, stand.plan_history = draft.plan, []
    return stand


def keep_version(draft, stand: Project) -> None:
    draft.plan = stand.plan


def copy_to_video(project: Project, draft) -> None:
    """Make this version: the owner's approved plan is the video's start, approved ("From
    Reed's plan"); each video's plan is its own from here."""
    if draft.plan and draft.plan.get("approved_at"):
        project.plan = {**draft.plan, "source": "owner", "version": 1}


def preview_follows(draft) -> bool:
    """The version's saved preview may start its video: there's no approved owner plan, or the
    preview was made from it. One made before ("Made for an older plan") is made again from the
    plan, paid, so the shots never silently skip Reed's plan (Flow-QA)."""
    plan = draft.plan or {}
    if not plan.get("approved_at"):
        return True
    return (draft.breakdown or {}).get("plan_version") == plan.get("version")


def _newest_breakdown(db: Session, project: Project) -> BreakdownVersion | None:
    return db.scalar(select(BreakdownVersion).where(BreakdownVersion.project_id == project.id)
                     .order_by(BreakdownVersion.id.desc()).limit(1))  # fmt: skip


def current(db: Session, project: Project) -> dict | None:
    """The video's plan. A video with a breakdown and no plan (made before plans) gets one
    read from that breakdown, in code and free, marked approved; it's saved the first time.
    Every "is the plan approved?" goes through here (`status`)."""
    if project.plan:
        return project.plan
    row = _newest_breakdown(db, project)
    if row is None:
        return None
    plan = prompts.plan_from_breakdown(Breakdown.model_validate(row.data)).model_dump()
    version = script(db, project)
    made_for = _hash(version.text if version else "")
    project.plan = {**plan, "version": 1, "source": "from_breakdown",
                    "approved_at": row.created_at.isoformat(), "approved_by_id": None,
                    "job_id": None, "made_for_text_hash": made_for,
                    "made_at": row.created_at.isoformat()}  # fmt: skip
    return project.plan


def status(db: Session, project: Project) -> str:
    """ "none", "ready" (made, not approved) or "approved"."""
    plan = current(db, project)
    if not plan:
        return "none"
    return "approved" if plan.get("approved_at") else "ready"


def require_approved(db: Session, project: Project) -> None:
    if status(db, project) != "approved":
        raise HTTPException(409, PLAN_FIRST)


def _fmt(db: Session, project: Project) -> str:
    from app.models.script_library import Script, ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    kind = db.get(Script, draft.script_id).kind if draft else "story"
    return {"song": "song", "narrated": "narrated"}.get(kind, "dialogue")


def _tag(message: str, name: str) -> str:
    found = re.search(rf"<{name}>\n?(.*?)\n?</{name}>", message, re.S)
    return found.group(1) if found else ""


def _stars(db: Session, project: Project) -> list[str]:
    from app.enhance import project_screens

    return [f"screen:{s.id}" for s in project_screens(db, project)]


def job_input(db: Session, project: Project, version: ScriptVersion, note: str = "") -> dict:
    """The plan call (the Director's plan step), with what the free check needs to read it."""
    from app.breakdown import _places, video_model

    system, context = project_context(db, project, STEP)
    if project.script_draft_id:  # from the library: its roles, as the breakdown reads them
        from app import script_preview
        from app.models.script_library import ScriptDraft

        draft = db.get(ScriptDraft, project.script_draft_id)
        context = script_preview.with_slots(db, draft.script_id, context, project)
    cast = [x for x in _tag(context, "cast").splitlines() if x.strip()]
    model = video_model()
    reference = ""
    if project.reference_breakdown:
        reference = prompts.reference_block(project.reference_breakdown, project.reference_replace)
    message = prompts.plan_input(
        _tag(context, "brief"), cast, escape(version.text), _fmt(db, project),
        f"{model.name}: up to {model.duration.max} s a clip",
        places=[x for x in escape(_places(db, project)).splitlines() if x],
        reference=escape_block(reference) if reference else "", note=escape(note),
    )  # fmt: skip
    return {"step": STEP, "project_id": project.id, "script_version": version.version,
            "system": system, "prompt": message, "max_tokens": 16000,
            "script": version.text, "fmt": _fmt(db, project),
            "cast_ids": re.findall(r"^((?:char|slot):\d+)", "\n".join(cast), re.M),
            "stars": _stars(db, project), "max_seconds": model.duration.max}  # fmt: skip


def price(db: Session, project: Project) -> Decimal:
    """What Make the plan charges: the same estimate `enqueue` takes for it."""
    return estimate(db, project.workspace_id, KIND, Decimal(1), {})


def checked(job_input: dict, output: dict) -> tuple[dict, list[str]]:
    """The Director's free check: fixes (a line missing, twice, out of order, a ★ that isn't
    the brand's) and Advice (kept for the cards)."""
    plan = ScenePlan.model_validate(output)
    found = check.plan(job_input["script"], plan, job_input["cast_ids"], job_input["stars"],
                       job_input["fmt"], job_input["max_seconds"])  # fmt: skip
    return plan.model_dump(), [p for p in found if not p.startswith(check.ADVICE)]


def again(job_input: dict, fixes: list[str]) -> dict:
    """The one rewrite inside the same job (charged once): the same ask, with what to fix."""
    said = "\n".join(f"- {f}" for f in fixes)
    fix = f"<fix>\nYour last plan can't be used:\n{said}\nWrite the whole plan again.\n</fix>"
    return {**job_input, "prompt": f"{job_input['prompt']}\n{fix}"}


def _keep(project: Project) -> None:
    """The plan in hand goes to Earlier plans (newest first, at most HISTORY)."""
    if project.plan:
        project.plan_history = [project.plan, *(project.plan_history or [])][:HISTORY]


def _next(project: Project) -> int:
    """The next plan version, above the plan in hand and every Earlier plan, so shots made
    from any other version read as older (Flow-QA)."""
    every = [project.plan or {}, *(project.plan_history or [])]
    return max(p.get("version", 0) for p in every) + 1


def _set(project: Project, plan: dict, source: str, job_id: int | None, text: str) -> dict:
    version = _next(project)
    _keep(project)
    project.plan = {**plan, "version": version, "source": source, "approved_at": None,
                    "approved_by_id": None, "job_id": job_id,
                    "made_for_text_hash": _hash(text), "made_at": utcnow().isoformat()}  # fmt: skip
    return project.plan


def _holder(db: Session, job: Job) -> tuple[Project | None, object | None]:
    """The video a plan job is for, or the script version's stand-in (S6) and its draft."""
    if draft_id := job.input.get("script_draft_id"):
        from app.models.script_library import Script, ScriptDraft

        draft = db.get(ScriptDraft, draft_id)
        script = db.get(Script, draft.script_id) if draft else None
        if not draft or script.published:  # final once published (rule 31)
            return None, None
        return for_version(db, script, draft), draft
    project = db.get(Project, job.input["project_id"])
    return (None, None) if project is None or project.archived_at is not None else (project, None)


def save(db: Session, job: Job) -> None:
    """A made plan lands, ready to check; the one before goes to Earlier plans."""
    project, draft = _holder(db, job)
    if project is None:
        return
    _set(project, ScenePlan.model_validate(job.output).model_dump(), "made", job.id,
         job.input["script"])  # fmt: skip
    if draft is not None:
        keep_version(draft, project)


def by_hand(db: Session, project: Project, version: ScriptVersion) -> dict:
    """Write it myself (free): one empty card per scene of the script (its headings), every
    line once, in order."""
    lines = prompts.plan_lines(version.text)
    words = dict(enumerate(version.text.splitlines(), 1))
    heads = [n for n, x in words.items() if x.strip().startswith(prompts.HEADING)]
    scenes: list[dict] = []
    for n in lines:
        head = max((h for h in heads if h < n), default=0)
        if not scenes or scenes[-1]["_head"] != head:
            place = words.get(head, "").strip() if head else ""
            scenes.append({"id": len(scenes) + 1, "part": "", "place": place, "cast": [],
                           "lines": [], "_head": head})  # fmt: skip
        scenes[-1]["lines"].append({"line": n, "action": "", "product": None})
    for s in scenes:
        s.pop("_head")
    plan = {"structure": {"name": "Your own plan", "parts": [], "based_on": "pattern"},
            "cast": [], "scenes": scenes}  # fmt: skip
    ScenePlan.model_validate(plan)
    return _set(project, plan, "by_hand", None, version.text)


def edit(project: Project, version: ScriptVersion, plan: ScenePlan) -> dict:
    """An edit (place, actions, ★, cast, a line moved, a split or a join): free, every line
    still once and in order. An approved plan goes back to "ready" (Undo is the plan before,
    sent back)."""
    used = [x.line for s in plan.scenes for x in s.lines]
    if used != prompts.plan_lines(version.text):
        raise HTTPException(422, "Every script line must be in exactly one scene, in order.")
    keep = {k: v for k, v in (project.plan or {}).items() if k not in ScenePlan.model_fields}
    project.plan = {**keep, **plan.model_dump(), "approved_at": None, "approved_by_id": None,
                    "source": keep.get("source", "by_hand"),
                    "version": _next(project)}  # shots made before read older  # fmt: skip
    return project.plan


def approve(project: Project, user_id: int) -> None:
    project.plan = {**project.plan, "approved_at": utcnow().isoformat(),
                    "approved_by_id": user_id}  # fmt: skip


def use_earlier(project: Project, index: int) -> dict:
    """Earlier plans: one press brings one back (free); the plan in hand takes its place."""
    history = list(project.plan_history or [])
    if not 0 <= index < len(history):
        raise HTTPException(404, "That earlier plan is no longer here.")
    chosen = history.pop(index)
    version = _next(project)
    project.plan_history = ([project.plan] if project.plan else []) + history
    project.plan = {**chosen, "approved_at": None, "approved_by_id": None, "version": version}
    return project.plan


def advice(job_input: dict, plan: dict) -> list[str]:
    found = check.plan(job_input["script"], ScenePlan.model_validate(plan),
                       job_input["cast_ids"], job_input["stars"], job_input["fmt"],
                       job_input["max_seconds"])  # fmt: skip
    return [p for p in found if p.startswith(check.ADVICE)]


def latest_job(db: Session, project: Project) -> Job | None:
    if project.id is None:  # a script version's plan (S6): its own jobs
        jobs = db.scalars(select(Job).where(Job.project_id.is_(None), Job.kind == KIND)
                          .order_by(Job.id.desc()))  # fmt: skip
        mine = project.script_draft_id
        return next((j for j in jobs if j.input.get("step") == STEP
                     and j.input.get("script_draft_id") == mine), None)  # fmt: skip
    jobs = db.scalars(select(Job).where(Job.project_id == project.id, Job.kind == KIND)
                      .order_by(Job.id.desc()))  # fmt: skip
    return next((j for j in jobs if j.input.get("step") == STEP), None)


def job_state(db: Session, project: Project) -> dict | None:
    """The plan call in hand: {id, status, reason, started_at}; None when idle, done or
    stopped by a person. Past the time limit it's stopped here, uncharged."""
    from app.routes.jobs import stop_jobs

    job = latest_job(db, project)
    if not job or job.status == JobStatus.succeeded:
        return None
    if job.status == JobStatus.running and utcnow() - (job.started_at or utcnow()) > LIMIT:
        stop_jobs(db, Job.id == job.id)
        job.error = SLOW
    if job.status == JobStatus.cancelled and job.error != SLOW:
        return None  # Stop: nothing to say
    if job.status in (JobStatus.failed, JobStatus.cancelled):
        return {"id": job.id, "status": "failed", "reason": job.error or FAILED,
                "started_at": job.started_at}  # fmt: skip
    state = "running" if job.status == JobStatus.running else "queued"
    return {"id": job.id, "status": state, "reason": None, "started_at": job.started_at}


def stop(db: Session, project: Project) -> None:
    """Stop the plan in hand, queued or running: nothing is charged and nothing it made is
    kept; the plan before stays."""
    from app.routes.jobs import stop_jobs

    job = latest_job(db, project)
    if not job or job.status not in WAITING:
        raise HTTPException(409, "No plan is being made.")
    stop_jobs(db, Job.id == job.id)


def out_of_date(db: Session, project: Project, plan: dict) -> bool:
    """The script's words changed after the plan was made ("Made for older words")."""
    version = script(db, project)
    return (
        bool(version)
        and plan.get("source") != "from_breakdown"
        and plan.get("made_for_text_hash") != _hash(version.text)
    )


def block(db: Session, project: Project, version: ScriptVersion) -> tuple[str, int] | None:
    """The approved plan as the breakdown reads it (P2), with its version; None without one."""
    plan = current(db, project)
    if not plan or not plan.get("approved_at") or plan.get("source") == "from_breakdown":
        return None
    rule, tag, rest = prompts.plan_block(ScenePlan.model_validate(plan), version.text).partition(
        "<plan>"
    )  # the Director's rule first, then the <plan> block: only its inside is escaped
    return f"{rule}{escape_block(tag + rest)}", plan["version"]


def shots_checked(job_input: dict, output: dict) -> tuple[dict, list[str]]:
    """The Director's check that the shots follow the approved plan (#892): fixes for a
    breakdown scene that mixes plan scenes, or a ★ line whose shot doesn't show its product."""
    plan = ScenePlan.model_validate(job_input["plan"])
    return output, check.follows_plan(plan, Breakdown.model_validate(output))


def shots_again(job_input: dict, fixes: list[str]) -> dict:
    said = "\n".join(f"- {f}" for f in fixes)
    fix = f"<fix>\nYour shots don't follow the approved plan:\n{said}\nWrite them again.\n</fix>"
    return {**job_input, "prompt": f"{job_input['prompt']}\n{fix}"}


def older(db: Session, project: Project, row: BreakdownVersion) -> bool:
    """A breakdown made from an earlier plan than the one in hand ("Made for an older plan")."""
    made = (row.data or {}).get("plan_version")
    plan = project.plan or {}
    return bool(made) and made < plan.get("version", 0)


def after(db: Session, project: Project) -> dict | None:
    """What an edit to an approved plan puts out of date: its shots and the clips after them
    ("The breakdown goes out of date (3 shots, 2 clips after it)"); None without shots."""
    row = _newest_breakdown(db, project)
    if row is None:
        return None
    shots = sum(len(sc.get("shots", [])) for sc in row.data.get("scenes", []))
    return {"shots": shots, "clips": len(row.data.get("clips", []))}
