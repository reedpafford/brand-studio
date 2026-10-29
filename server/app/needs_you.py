"""Which videos wait on their editor (audit M6, the Videos home's Needs you group): the one
thing to do first, in plain words. Free and read-only, in a fixed handful of queries for the
whole list. In order: a run that didn't finish, a look to approve, work ready to check, then
a step out of date."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame

NAMES = {  # what a failed run was, as the editor knows it; a step not named here is left out
    "breakdown": "The shot plan", "song_breakdown": "The shot plan",
    "narrated_breakdown": "The shot plan", "plan": "The scene plan", "plan_scene": "A scene",
    "sheet": "A look", "storyboard": "The storyboard", "frame": "A still",
    "clip_prompts": "The clip prompts", "clip_take": "A clip", "change": "A change",
    "song_take": "The song", "song_timing": "The song's timing",
}  # fmt: skip
KINDS = {"speech": "The narration", "narration_timing": "The narration's timing"}  # N1
ADVISORY = "check-claude"  # a picture check that only advises: its failure never flags a video


def _count(n: int, one: str, many: str) -> str:
    return f"1 {one}" if n == 1 else f"{n} {many}"


def waiting_on(db: Session, projects: list[Project], old: set[int]) -> dict[int, str]:
    """Video id -> what it waits on its editor for; videos with nothing to do are left out.
    `old`: the finished videos whose clips changed since (project_clips.out_of_date)."""
    ids = [p.id for p in projects if not p.archived_at]
    if not ids:
        return {}
    newest_job = dict(db.execute(select(Job.project_id, func.max(Job.id))
                                 .where(Job.project_id.in_(ids), Job.kind != ADVISORY)
                                 .group_by(Job.project_id)).all())  # fmt: skip
    failed = {j.project_id: j for j in db.scalars(select(Job).where(
        Job.id.in_(newest_job.values()), Job.status == JobStatus.failed))}  # fmt: skip
    looks = dict(db.execute(select(LibraryItem.owner_project_id, func.count())
                            .where(LibraryItem.owner_project_id.in_(ids),
                                   LibraryItem.sheet_file_id.is_not(None),
                                   LibraryItem.sheet_approved.is_(False),
                                   LibraryItem.archived.is_(False))
                            .group_by(LibraryItem.owner_project_id)).all())  # fmt: skip
    plan = dict(db.execute(select(BreakdownVersion.project_id, func.max(BreakdownVersion.id))
                           .where(BreakdownVersion.project_id.in_(ids))
                           .group_by(BreakdownVersion.project_id)).all())  # fmt: skip
    ready, behind = {}, set()  # current work to check; work made for an older plan
    for model, made in ((StoryboardFrame, StoryboardFrame.file_id),
                        (ProjectClip, ProjectClip.picked_take_id)):  # fmt: skip
        rows = db.execute(select(model.project_id, model.breakdown_id, model.approved)
                          .where(model.project_id.in_(ids), made.is_not(None))).all()  # fmt: skip
        for pid, bd, approved in rows:
            if bd != plan.get(pid):
                behind.add(pid)
            elif not approved:
                ready.setdefault(pid, {}).setdefault(model, 0)
                ready[pid][model] += 1
    out = {}
    for pid in ids:
        job = failed.get(pid)
        if job and (name := KINDS.get(job.kind) or NAMES.get(job.input.get("step", ""))):
            out[pid] = f"{name} didn't finish"
        elif looks.get(pid):
            out[pid] = f"Approve {_count(looks[pid], 'look', 'looks')}"
        elif counts := ready.get(pid):
            kinds = ((StoryboardFrame, "still", "stills"), (ProjectClip, "clip", "clips"))
            parts = [_count(counts[m], one, many) for m, one, many in kinds if m in counts]
            out[pid] = f"{' and '.join(parts)} ready to check"
        elif pid in behind or pid in old:
            out[pid] = "Changes are waiting: bring it up to date"
    return out
