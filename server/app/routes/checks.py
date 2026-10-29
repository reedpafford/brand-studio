"""The advisory check's presses (flows.md 1b, P4): Looks fine on a finding, and the video's
Review list ("3 items with Advice"). Advice only: nothing here blocks or approves anything."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import credits, item_checks
from app.auth import current_user
from app.db import get_db, utcnow
from app.item_checks import CheckOut
from app.models.accounts import User
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, ProjectClip
from app.models.storyboards import StoryboardFrame
from app.routes.projects import get_project

router = APIRouter(prefix="/projects/{project_id}/checks", tags=["checks"])


class FlaggedOut(BaseModel):
    kind: str  # still or take
    id: int  # the frame's id, or the take's
    clip_id: str  # c1, c2, …: where its card is
    label: str  # "Still 2.1", "Clip c3 · take 2"
    findings: int


class ReviewOut(BaseModel):
    on: bool  # checks run (the stand-in on the test site, or approved for real)
    credits_per_check: int  # one check, rounded up
    items: list[FlaggedOut]  # the current stills and takes with Advice not yet Looks fine


@router.get("", response_model=ReviewOut)
def review(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The video's items with Advice, in one place (Clips' header and Final cut)."""
    project = get_project(db, user, project_id)
    drawn = (StoryboardFrame.project_id == project.id) & StoryboardFrame.file_id.is_not(None)
    frames = list(db.scalars(select(StoryboardFrame).where(drawn)))
    rows = list(db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)))
    picked = {r.picked_take_id: r for r in rows if r.picked_take_id}
    takes = list(db.scalars(select(ClipTake).where(ClipTake.id.in_(picked))))
    items = []
    seen = item_checks.latest(db, "frame", [f.id for f in frames])
    for f in frames:
        if (out := item_checks.shown(db, seen.get(f.id))) and out.findings:
            label, n = f"Still {f.shot_id}", len(out.findings)
            items.append(FlaggedOut(kind="still", id=f.id, clip_id=f.clip_id, label=label,
                                    findings=n))  # fmt: skip
    seen = item_checks.latest(db, "take", [t.id for t in takes])
    for t in takes:
        if (out := item_checks.shown(db, seen.get(t.id))) and out.findings:
            clip = picked[t.id].clip_id
            items.append(FlaggedOut(kind="take", id=t.id, clip_id=clip,
                                    label=f"Clip {clip} · take {t.number}",
                                    findings=len(out.findings)))  # fmt: skip
    db.commit()  # a check whose job ended without an answer now reads "failed"
    return ReviewOut(on=item_checks.on(), items=items,
                     credits_per_check=credits.price(item_checks.price(db, project)))  # fmt: skip


@router.post("/{check_id}/findings/{index}/dismiss", response_model=CheckOut)
def looks_fine(
    project_id: int,
    check_id: int,
    index: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Looks fine: the finding goes from the card, kept in the item's history (who, when)."""
    project = get_project(db, user, project_id)
    row = db.get(ItemCheck, check_id)
    if not row or row.project_id != project.id or not 0 <= index < len(row.findings or []):
        raise HTTPException(404, "That advice is no longer here.")
    if index not in {d["index"] for d in row.dismissed or []}:
        said = {"index": index, "by_id": user.id, "at": utcnow().isoformat()}
        row.dismissed = [*(row.dismissed or []), said]
    db.commit()
    return item_checks.shown(db, row)
