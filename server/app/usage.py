"""The brand tracker's figures (DECISIONS #237; docs/design/redesign/phase3/screens/usage.md).
Owner only: these are dollars. Every figure is grouped by brand in one query, so a page of
brands never runs a query per brand; jobs with no brand (null) are "Not tied to one brand"."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.credits import week_start
from app.db import utcnow
from app.models.clips import ProjectClip
from app.models.jobs import Job, Usage
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft

PERIODS = ("week", "month", "all")


@dataclass
class Period:
    start: datetime | None  # None: all time
    end: datetime | None = None  # None: now

    def has(self, column):
        conds = []
        if self.start is not None:
            conds.append(column >= self.start)
        if self.end is not None:
            conds.append(column < self.end)
        return conds


def period(name: str) -> Period:
    if name == "week":
        return Period(week_start())
    if name == "month":
        return Period(utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    return Period(None)


def previous(name: str, now: Period) -> Period | None:
    """The period before (last week, last month); none for all time."""
    if now.start is None:
        return None
    if name == "week":
        return Period(now.start - timedelta(days=7), now.start)
    return Period((now.start - timedelta(days=1)).replace(day=1), now.start)


def money(value) -> float:
    return float(round(Decimal(value or 0), 2))


@dataclass
class Figures:
    """Per brand id (None = not tied to one brand)."""

    spend: dict
    estimated: dict
    finished: dict
    finished_spend: dict
    in_progress: dict
    scripts: dict
    versions_left: dict
    last_activity: dict

    def cost_per(self, brand_id) -> float | None:
        done = self.finished.get(brand_id, 0)
        return money(self.finished_spend.get(brand_id, 0) / done) if done else None


def _grouped(db: Session, query) -> dict:
    return {key: value for key, value in db.execute(query).all()}


def figures(db: Session, workspace_id: int, when: Period) -> Figures:
    charged = (
        select(
            Job.brand_id, func.sum(Usage.cost_usd), func.sum(case((Usage.estimated, 1), else_=0))
        )
        .join(Job, Job.id == Usage.job_id)
        .where(Usage.workspace_id == workspace_id, *when.has(Usage.created_at))
        .group_by(Job.brand_id)
    )
    spend, estimated = {}, {}
    for brand_id, total, guessed in db.execute(charged).all():
        spend[brand_id], estimated[brand_id] = Decimal(total or 0), bool(guessed)
    done = select(Project.id).where(
        Project.workspace_id == workspace_id, *when.has(Project.finished_at)
    )
    finished = _grouped(
        db,
        select(Project.brand_id, func.count())
        .where(Project.id.in_(done))
        .group_by(Project.brand_id),
    )
    finished_spend = _grouped(  # those videos' whole life, every take and redo
        db,
        select(Project.brand_id, func.sum(Usage.cost_usd))
        .join(Job, Job.id == Usage.job_id)
        .join(Project, Project.id == Job.project_id)
        .where(Project.id.in_(done))
        .group_by(Project.brand_id),
    )
    in_progress = _grouped(
        db,
        select(Project.brand_id, func.count())
        .where(Project.workspace_id == workspace_id, Project.finished_at.is_(None))
        .group_by(Project.brand_id),
    )
    scripts = _grouped(
        db,
        select(Script.brand_id, func.count())
        .where(Script.workspace_id == workspace_id, Script.archived.is_(False))
        .group_by(Script.brand_id),
    )
    versions_left = _grouped(
        db,
        select(Script.brand_id, func.count())
        .join(ScriptDraft, ScriptDraft.script_id == Script.id)
        .outerjoin(Project, Project.script_draft_id == ScriptDraft.id)
        .where(
            Script.workspace_id == workspace_id,
            Script.published.is_(True),
            Script.archived.is_(False),
            ScriptDraft.status == "approved",
            Project.id.is_(None),
        )
        .group_by(Script.brand_id),
    )
    last: dict = {}
    for query in (
        select(Job.brand_id, func.max(Job.created_at))
        .where(Job.workspace_id == workspace_id)
        .group_by(Job.brand_id),
        select(Project.brand_id, func.max(Project.created_at))
        .where(Project.workspace_id == workspace_id)
        .group_by(Project.brand_id),
        select(Script.brand_id, func.max(Script.created_at))
        .where(Script.workspace_id == workspace_id)
        .group_by(Script.brand_id),
    ):
        for brand_id, at in db.execute(query).all():
            if at and (brand_id not in last or at > last[brand_id]):
                last[brand_id] = at
    return Figures(
        spend, estimated, finished, finished_spend, in_progress, scripts, versions_left, last
    )


def editors_active(db: Session, brand_id: int, when: Period) -> int:
    """How many people made videos for the brand in the period (jobs on its videos)."""
    return db.scalar(
        select(func.count(func.distinct(Job.created_by_id))).where(
            Job.brand_id == brand_id, Job.project_id.is_not(None), *when.has(Job.created_at)
        )
    )


# --- Lists (spec items 6-8): a brand's videos and scripts, and every charge ---

STEPS = {
    "script_draft": "Script drafts",
    "enhance": "Script suggestions",
    "breakdown": "Breakdown",
    "storyboard": "Storyboard",
    "frame": "Storyboard still",
    "clip_prompts": "Clip prompts",
    "clip_take": "Clip take",
    "variations": "Script variations",
    "cast_slots": "Reading the cast",
    "improve": "Improve a prompt",
    "sheet": "A look",
}
LETTERS = "ABC"


def video_title(db: Session, project: Project) -> tuple[str, int | None, str | None]:
    """'{script title} · {letter}' for a video from the library, else its own name;
    with the script id and letter (None for an earlier-style video)."""
    if project.script_draft_id:
        draft = db.get(ScriptDraft, project.script_draft_id)
        script = db.get(Script, draft.script_id)
        letter = LETTERS[draft.slot]
        return f"{script.title} · {letter}", script.id, letter
    return project.name, None, None


def what(db: Session, job: Job) -> str:
    """A charge in plain words: 'Clip take · Bo tries salmon · B', 'Quick clip'."""
    step = job.input.get("step")
    if job.project_id is not None:
        title, _, _ = video_title(db, db.get(Project, job.project_id))
        clip = db.get(ProjectClip, job.input.get("project_clip_id") or 0)
        if step == "clip_take" and clip:
            return f"Clip {clip.clip_id.lstrip('c')} take · {title}"
        return f"{STEPS.get(step, 'Video')} · {title}"
    if job.input.get("script_id"):
        script = db.get(Script, job.input["script_id"])
        return f"{STEPS.get(step, 'Script')} · {script.title}" if script else STEPS.get(step, "")
    if job.input.get("script_draft_id"):
        draft = db.get(ScriptDraft, job.input["script_draft_id"])
        script = db.get(Script, draft.script_id) if draft else None
        return f"Breakdown preview · {script.title}" if script else "Breakdown preview"
    return STEPS.get(step, "Quick clip")


def project_totals(db: Session, project_ids: list[int]) -> tuple[dict, dict, dict, dict]:
    """Per project: lifetime dollars, whether any is estimated, credits, last job time."""
    from app.credits import COUNTED

    spend, guessed, credits, last = {}, {}, {}, {}
    if not project_ids:
        return spend, guessed, credits, last
    rows = db.execute(
        select(
            Job.project_id, func.sum(Usage.cost_usd), func.sum(case((Usage.estimated, 1), else_=0))
        )
        .join(Job, Job.id == Usage.job_id)
        .where(Job.project_id.in_(project_ids))
        .group_by(Job.project_id)
    ).all()
    for pid, total, est in rows:
        spend[pid], guessed[pid] = Decimal(total or 0), bool(est)
    rows = db.execute(
        select(
            Job.project_id,
            func.sum(case((Job.status.in_(COUNTED), Job.credits), else_=0)),
            func.max(Job.created_at),
        )
        .where(Job.project_id.in_(project_ids))
        .group_by(Job.project_id)
    ).all()
    for pid, total, at in rows:
        credits[pid], last[pid] = Decimal(total or 0), at
    return spend, guessed, credits, last


def video_statuses(db: Session, projects: list[Project]) -> dict[int, str]:
    """The library's words per video, in one query: done, failed (its last job failed),
    or in_production."""
    ids = [p.id for p in projects]
    last = (
        select(Job.project_id, func.max(Job.id).label("id"))
        .where(Job.project_id.in_(ids))
        .group_by(Job.project_id)
        .subquery()
    )
    failed = set(
        db.scalars(
            select(Job.project_id).join(last, last.c.id == Job.id).where(Job.status == "failed")
        )
    )
    return {
        p.id: "done" if p.finished_at else "failed" if p.id in failed else "in_production"
        for p in projects
    }


def script_spends(db: Session, brand_id: int) -> dict[int, tuple[Decimal, bool]]:
    """Per script of the brand, in one pass: writing it (its own jobs) plus every video made
    from its versions, lifetime dollars and whether any is an estimate."""
    draft_script = dict(
        db.execute(
            select(ScriptDraft.id, ScriptDraft.script_id)
            .join(Script, Script.id == ScriptDraft.script_id)
            .where(Script.brand_id == brand_id)
        ).all()
    )
    project_script = {
        pid: draft_script[did]
        for pid, did in db.execute(
            select(Project.id, Project.script_draft_id).where(
                Project.script_draft_id.in_(list(draft_script))
            )
        ).all()
    }
    rows = db.execute(
        select(Job.project_id, Job.input, Usage.cost_usd, Usage.estimated)
        .join(Usage, Usage.job_id == Job.id)
        .where(Job.brand_id == brand_id)
    ).all()
    out: dict[int, tuple[Decimal, bool]] = {}
    for project_id, data, cost, est in rows:
        if project_id is not None:
            script_id = project_script.get(project_id)
        else:
            script_id = data.get("script_id") or draft_script.get(data.get("script_draft_id"))
        if script_id is None:
            continue
        total, guessed = out.get(script_id, (Decimal(0), False))
        out[script_id] = (total + Decimal(cost or 0), guessed or bool(est))
    return out
