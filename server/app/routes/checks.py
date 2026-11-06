"""The advisory check's presses (flows.md 1b, P4): Looks fine on a finding, and the video's
Review list ("3 items with Advice"). Advice only: nothing here blocks or approves anything.
And what the director's watch of each take found and did (rule 11, app/take_watch)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import credits, item_checks, watch_cut, watch_report
from app.auth import current_user
from app.db import get_db, utcnow
from app.item_checks import CheckOut
from app.models.accounts import User
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, ProjectClip
from app.models.storyboards import StoryboardFrame
from app.routes.project_clips import WatchOut
from app.routes.projects import get_project, video_writer

router = APIRouter(
    prefix="/projects/{project_id}/checks", tags=["checks"], dependencies=[Depends(video_writer)]
)


class FlaggedOut(BaseModel):
    kind: str  # still or take
    id: int  # the frame's id, or the take's
    clip_id: str  # c1, c2, …: where its card is
    label: str  # "Still 2.1", "Clip c3 · take 2"
    findings: int


class ReviewOut(BaseModel):
    on: bool  # checks run (the stand-in on the test site, or approved for real)
    credits_per_check: int  # one check, rounded up
    check_credits_per_video: int  # Video settings: "Checks: about N credits a video"
    paused: bool = False  # a current still or picked take was skipped at the budget (PL7)
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
    items, paused = [], False
    seen = item_checks.latest(db, "frame", [f.id for f in frames])
    paused |= any(r.status == "skipped" for r in seen.values())
    for f in frames:
        if (out := item_checks.shown(db, seen.get(f.id))) and out.findings:
            label, n = f"Still {f.shot_id}", len(out.findings)
            items.append(FlaggedOut(kind="still", id=f.id, clip_id=f.clip_id, label=label,
                                    findings=n))  # fmt: skip
    seen = item_checks.latest(db, "take", [t.id for t in takes])
    heard = item_checks.latest(db, "words", [t.id for t in takes])  # what each take says
    paused |= any(r.status == "skipped" for r in seen.values())
    for t in takes:
        found = [o for c in (seen, heard) if (o := item_checks.shown(db, c.get(t.id)))]
        if n := sum(len(o.findings) for o in found):
            clip = picked[t.id].clip_id
            items.append(FlaggedOut(kind="take", id=t.id, clip_id=clip,
                                    label=f"Clip {clip} · take {t.number}",
                                    findings=n))  # fmt: skip
    db.commit()  # a check whose job ended without an answer now reads "failed"
    each, whole = item_checks.price(db, project), item_checks.per_video(db, project)
    return ReviewOut(on=item_checks.on(), items=items, paused=paused,
                     credits_per_check=credits.price(each),
                     check_credits_per_video=credits.price(whole) if whole else 0)  # fmt: skip


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
    if row.target in ("take", "words"):  # its last note cleared: a clean take approves itself
        from app.take_approval import after_check

        db.flush()
        after_check(db, row.target_id)
    db.commit()
    return item_checks.shown(db, row)


@router.post("/{check_id}/findings/{index}/restore", response_model=CheckOut)
def restore(
    project_id: int,
    check_id: int,
    index: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo of Looks fine: the finding is back on the card (free)."""
    project = get_project(db, user, project_id)
    row = db.get(ItemCheck, check_id)
    if not row or row.project_id != project.id or not 0 <= index < len(row.findings or []):
        raise HTTPException(404, "That advice is no longer here.")
    row.dismissed = [d for d in row.dismissed or [] if d["index"] != index]
    db.commit()
    return item_checks.shown(db, row)


class LatestOut(WatchOut):
    clip_id: str  # c7
    take: int  # its number


class RedidOut(BaseModel):
    at: float  # where in the cut, in seconds ("0:14")
    clip_id: str
    take: int
    found: str | None
    did: str | None
    action: str  # redo, held, flagged or unsure


class TakesWatchedOut(BaseModel):
    watched: int  # "12 watched"
    watching: int
    redone: int  # "1 redone"
    held: int  # remakes waiting for the owner's OK
    flagged: int  # for the owner: remake or keep
    unsure: int  # a fault it couldn't confirm: told to the owner, never remade on its own
    latest: LatestOut | None  # "Clip 7: cartoon eyes landed on the stomach. Remaking it"


class WatchedOut(BaseModel):
    takes: TakesWatchedOut
    redid: list[RedidOut]  # the delivery note's "What I watched and redid", in cut order
    cut: dict  # the newest watch of the cut (watch_cut.state)


@router.get("/watch", response_model=WatchedOut)
def watched(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """What the director's watch found, take by take as each landed and in the cut, and
    what it did: the progress card, the delivery note and the Clips tab read it."""
    project = get_project(db, user, project_id)
    return WatchedOut(takes=watch_report.summary(db, project),
                      redid=watch_report.redid(db, project),
                      cut=watch_cut.state(db, project))  # fmt: skip
