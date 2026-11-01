"""A clean take approves itself (DECISIONS rule 21, take check slice 3): once every check on
a clip's picked take has ended and found nothing, the clip is approved, marked "Approved by
the check". It never picks or ranks a take, never approves a flagged, checking or unchecked
one, and stays out of a take a person un-approved. It runs when a check ends, when a take is
picked and on Looks fine (QA-3: re-picking a clean take, or clearing its last note, approves
it too). "Approved by the check" only ever shows on the approved, picked take."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clip_prompts, item_checks, looks, video_settings
from app.db import utcnow
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project

BY_CHECK = "check"
YES, NO = "yes", "no"  # what a person said on a take


def verdict(db: Session, take_id: int) -> str:
    """The take's verdict from all its checks (item_checks.verdict)."""
    found = [item_checks.latest(db, t, [take_id]).get(take_id) for t in ("take", "words")]
    return item_checks.verdict([item_checks.shown(db, r) for r in found])


def after_check(db: Session, take_id: int) -> None:
    """A check on this take ended, it was picked or a note was cleared: approve its clip if
    the take is now clean."""
    take = db.get(ClipTake, take_id)
    clip = db.get(ProjectClip, take.clip_id) if take else None
    if not clip or not item_checks.on() or clip.picked_take_id != take.id or clip.approved:
        return
    said = (take.made_with or {}).get("person")
    if said and said != YES:  # a person said no on this take (True: before yes/no was kept)
        return
    project = db.get(Project, clip.project_id)
    newest = db.scalar(select(BreakdownVersion).where(BreakdownVersion.project_id == project.id)
                       .order_by(BreakdownVersion.id.desc()).limit(1))  # fmt: skip
    if (
        clip_prompts.is_stale(db, clip, newest)
        or clip_prompts.take_stale(clip)
        or looks.take_other(db, project, clip)
        or video_settings.take_stale(db, project, clip)
    ):
        return
    if verdict(db, take.id) == "clean":
        clip.approved = True
        if not said:  # a person's earlier yes stays theirs
            take.made_with = {**(take.made_with or {}), "approved_by": BY_CHECK,
                              "approved_at": utcnow().isoformat()}  # fmt: skip


def unmark(db: Session, clip: ProjectClip) -> None:
    """The clip's approval changed hands (a pick, ✓, un-approve, Approve all): no take of it
    says "Approved by the check" any more."""
    for take in db.scalars(select(ClipTake).where(ClipTake.clip_id == clip.id)):
        if "approved_by" in (take.made_with or {}):
            take.made_with = {k: v for k, v in take.made_with.items() if k != "approved_by"}


def by_person(clip: ProjectClip, db: Session, said: str) -> None:
    """A person approved (YES) or un-approved (NO) the picked take: it's theirs from now on;
    after a no, the check stays out of that take."""
    unmark(db, clip)
    take = db.get(ClipTake, clip.picked_take_id) if clip.picked_take_id else None
    if take:
        take.made_with = {**(take.made_with or {}), "person": said}
