"""A clean take approves itself (DECISIONS rule 21, take check slice 3): once every check on
a clip's picked take has ended and found nothing, the clip is approved, marked "Approved by
the check". It never picks or ranks a take, never approves a flagged, checking or unchecked
one, and stays out of a take a person has approved or un-approved themselves."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clip_prompts, item_checks, looks, video_settings
from app.db import utcnow
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project

BY_CHECK = "check"


def verdict(db: Session, take_id: int) -> str:
    """The take's verdict from all its checks (item_checks.verdict)."""
    found = [item_checks.latest(db, t, [take_id]).get(take_id) for t in ("take", "words")]
    return item_checks.verdict([item_checks.shown(db, r) for r in found])


def after_check(db: Session, take_id: int) -> None:
    """A check on this take just ended: approve its clip if the take is now clean."""
    take = db.get(ClipTake, take_id)
    clip = db.get(ProjectClip, take.clip_id) if take else None
    if not clip or not item_checks.on() or clip.picked_take_id != take.id or clip.approved:
        return
    if (take.made_with or {}).get("person"):  # a person said yes or no on this take
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
        take.made_with = {**(take.made_with or {}), "approved_by": BY_CHECK,
                          "approved_at": utcnow().isoformat()}  # fmt: skip


def by_person(clip: ProjectClip, db: Session) -> None:
    """✓ or un-approve pressed on the picked take: the check stays out of it from now on."""
    take = db.get(ClipTake, clip.picked_take_id) if clip.picked_take_id else None
    if take:
        made = {k: v for k, v in (take.made_with or {}).items() if k != "approved_by"}
        take.made_with = {**made, "person": True}
