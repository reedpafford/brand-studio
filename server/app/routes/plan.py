"""The Plan step's scenes (flows.md 1b, P1): make, check, edit and approve a video's scene
plan; approving it also makes the shots (the breakdown), at the breakdown's price (#848)."""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import breakdown, credits, plans, prompts
from app.advice import names
from app.auth import current_user, user_name
from app.db import get_db
from app.models.accounts import User
from app.prompts import check
from app.prompts.schemas import PlanLine, PlanScene, ScenePlan, Structure
from app.routes.breakdown import queue as queue_shots
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project, video_writer
from app.schemas import UtcTime

router = APIRouter(
    prefix="/projects/{project_id}/plan", tags=["plan"], dependencies=[Depends(video_writer)]
)
SOURCES = {"made": "claude", "owner": "owner", "from_breakdown": "breakdown", "by_hand": "hand"}


class LineOut(BaseModel):
    n: int  # the script line's number
    text: str  # its words, read only (the plan keeps numbers only, rule 19)
    section: str = ""  # a song's: the tag above it ("Chorus")
    action: str
    star: bool  # ★: a key product moment
    product: str | None = None  # what the ★ shows (screen:N)


class SceneOut(BaseModel):
    id: str
    part: str
    place: str
    time: str  # "NIGHT", from the place's "— NIGHT"
    cast_ids: list[str]
    lines: list[LineOut]


class AdviceOut(BaseModel):
    scene_id: str | None  # None: about the whole plan
    kind: str  # two_places, no_product, not_in_cast, too_long
    text: str


class JobState(BaseModel):
    id: int
    status: str  # queued, running or failed
    reason: str | None
    started_at: UtcTime | None


class EarlierOut(BaseModel):
    id: int  # what Use this plan sends
    version: int
    source: str
    made_at: str | None


class Who(BaseModel):
    id: int
    name: str


class Cast(BaseModel):
    ref_id: str
    name: str


class PlanOut(BaseModel):
    status: str  # ready or approved
    approved_by: Who | None = None
    approved_at: str | None = None
    source: str  # claude, owner, breakdown or hand
    structure: dict | None = None  # {label, from: reel | study | pattern}
    cast: list[Cast] = []
    scenes: list[SceneOut] = []
    summary: str | None = None
    advice: list[AdviceOut] = []
    job: JobState | None = None
    estimate_credits: int  # Make the plan / Make a new plan
    approve_credits: int  # Approve the plan · makes the shots (the breakdown's price)
    change_scene_credits: int = 0  # Change this scene… (one small call)
    stop: str | None = None  # why the paid presses are off (the week, the budget)
    out_of_date: bool = False  # made for older words
    version: int = 0
    earlier: list[EarlierOut] = []  # Earlier plans, newest first; `id` is the list position
    after: dict | None = None  # {shots, clips} an edit would put out of date; None: no shots yet


class NoteIn(BaseModel):
    note: str = Field("", max_length=500)


class LineIn(BaseModel):
    n: int
    action: str = Field("", max_length=500)
    star: bool = False
    product: str | None = None


class SceneIn(BaseModel):
    part: str = Field("", max_length=80)
    place: str = Field("", max_length=200)
    time: str = Field("", max_length=40)
    cast_ids: list[str] = []
    lines: list[LineIn]


class PlanIn(BaseModel):
    scenes: list[SceneIn]
    cast_ids: list[str] | None = None  # the plan's cast; unchanged when left out


class ApproveOut(BaseModel):
    plan: PlanOut
    job: JobOut | None  # the shots being made; None when they come from the owner's preview


def _kind(text: str) -> str:
    low = text.lower()
    for word, kind in (("two places", "two_places"), ("product", "no_product"),
                       ("cast", "not_in_cast"), ("runs about", "too_long")):  # fmt: skip
        if word in low:
            return kind
    return "advice"


def _advice(found: list[str]) -> list[AdviceOut]:
    out = []
    for p in found:
        text = p.removeprefix(check.ADVICE)
        m = re.match(r"scene (\d+)[: ]", text)
        out.append(AdviceOut(scene_id=m[1] if m else None, kind=_kind(text), text=text))
    return out


def _split(place: str) -> tuple[str, str]:
    head, _, time = place.rpartition(" — ")
    return (head, time) if head else (place, "")


def _out(db: Session, user: User, project) -> PlanOut | None:
    from app.storyboard import assets

    version = plans.script(db, project)
    job = plans.job_state(db, project)
    plans.read_again(db, project)  # after the job: a plan saved with it is never missed
    plan = plans.current(db, project)
    db.commit()  # a plan read from the breakdown, or a plan stopped for taking too long
    if plan is None and job is None:
        return None
    price = credits.price(plans.price(db, project))
    if project.id is None:  # a script version's plan (S6): script work, never on the week
        stop = None
    else:
        stop = credits.fits(db, project, user, plans.price(db, project)) or None
        stop = f"Making the plan {stop}" if stop else None
    shots = price if project.id is None else credits.price(breakdown.make_price(db, project))
    base = PlanOut(status="ready", source="claude", job=job, estimate_credits=price,
                   approve_credits=shots, change_scene_credits=price, stop=stop)  # fmt: skip
    if plan is None:
        return base
    known = names(assets(db, project))
    words = dict(enumerate((version.text if version else "").splitlines(), 1))
    parts = prompts.sections(version.text) if version and plans.song(db, project) else {}
    shape = plan.get("structure") or {}
    based = shape.get("based_on") == "reference"
    label = " → ".join(shape.get("parts") or [])
    label = f"{label} ({shape.get('name', '')})" if label else shape.get("name", "")
    found = []
    if version and plan.get("source") != "from_breakdown":
        given = plans.job_input(db, project, version)
        found = plans.advice(given, {k: plan[k] for k in ScenePlan.model_fields})
    by = plan.get("approved_by_id")
    return base.model_copy(update={
        "status": "approved" if plan.get("approved_at") else "ready",
        "approved_by": Who(id=by, name=user_name(db, by)) if by else None,
        "approved_at": plan.get("approved_at"),
        "source": SOURCES.get(plan.get("source"), "claude"),
        "structure": {"label": label, "from": ("reel" if project.reference_breakdown
                                               else "study") if based else "pattern"},
        "cast": [Cast(ref_id=c, name=known.get(c, c)) for c in plan.get("cast", [])],
        "scenes": [SceneOut(id=str(s["id"]), part=s["part"], place=_split(s["place"])[0],
                            time=_split(s["place"])[1], cast_ids=s["cast"],
                            lines=[LineOut(n=x["line"], text=words.get(x["line"], "").strip(),
                                           section=parts.get(x["line"], ""),
                                           action=x["action"], star=bool(x["product"]),
                                           product=x["product"]) for x in s["lines"]])
                   for s in plan.get("scenes", [])],
        "advice": _advice(found),
        "out_of_date": plans.out_of_date(db, project, plan),
        "version": plan.get("version", 0),
        "after": plans.after(db, project),
        "earlier": [EarlierOut(id=i, version=p.get("version", 0),
                               source=SOURCES.get(p.get("source"), "claude"),
                               made_at=p.get("made_at"))
                    for i, p in enumerate(project.plan_history or [])],
    })  # fmt: skip


def _working(db: Session, user: User, project_id: int):
    project = get_project(db, user, project_id)
    version = plans.script(db, project)
    if not version:
        raise HTTPException(409, "Add a script first.")
    return project, version


@router.get("", response_model=PlanOut)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The plan, or 404 when there's none and none is being made (E)."""
    out = _out(db, user, get_project(db, user, project_id))
    if out is None:
        raise HTTPException(404, "This video has no plan yet.")
    return out


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def make(
    project_id: int,
    body: NoteIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Make the plan, or Make a new plan (the one in hand goes to Earlier plans): one paid
    Claude call at the price shown."""
    project, version = _working(db, user, project_id)
    _one_at_a_time(db, project)
    data = plans.job_input(db, project, version, body.note if body else "")
    return enqueue(db, user, plans.KIND, data, project=project, provider="claude")


@router.post(
    "/update", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)]
)
def update(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Update the plan (made for older words): a new plan that keeps the scenes whose lines
    didn't change, at the plan's price; the one in hand goes to Earlier plans."""
    project, version = _working(db, user, project_id)
    plan = plans.current(db, project)
    if plan is None or not plans.out_of_date(db, project, plan):
        raise HTTPException(409, "The plan is up to date with the script.")
    _one_at_a_time(db, project)
    data = plans.job_input(db, project, version, plans.update_note(plan))
    return enqueue(db, user, plans.KIND, data, project=project, provider="claude")


@router.post("/scenes/{scene_id}/change", response_model=JobOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def change_scene(
    project_id: int,
    scene_id: int,
    body: NoteIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Change this scene…: a note rewrites only that scene's actions (its lines stay), one
    small paid call; the plan before goes to Earlier plans."""
    project, version = _working(db, user, project_id)
    if not body.note.strip():
        raise HTTPException(422, "Say what to change in this scene.")
    if plans.current(db, project) is None:
        raise HTTPException(404, "This video has no plan yet.")
    _one_at_a_time(db, project)
    data = plans.scene_input(db, project, version, scene_id, body.note)
    return enqueue(db, user, plans.KIND, data, project=project, provider="claude")


def _one_at_a_time(db: Session, project) -> None:
    job = plans.latest_job(db, project)
    if job and job.status in plans.WAITING:
        raise HTTPException(409, "A plan is already being made.")


@router.post("/stop", status_code=204)
def stop(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Stop the plan being made: nothing charged, the plan before stays."""
    plans.stop(db, get_project(db, user, project_id))
    db.commit()


@router.post("/by-hand", response_model=PlanOut)
def by_hand(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Write it myself: an empty card per scene of the script, free."""
    project, version = _working(db, user, project_id)
    plans.by_hand(db, project, version)
    db.commit()
    return _out(db, user, project)


@router.put("", response_model=PlanOut)
def edit(
    project_id: int,
    body: PlanIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Every edit (place, actions, ★, cast, a line moved, Split here, Join with next) sends
    the whole scene list; free. Undo is the scenes from before, sent back."""
    project, version = _working(db, user, project_id)
    apply_edit(db, project, version, body)
    db.commit()
    return _out(db, user, project)


def apply_edit(db: Session, project, version, body: PlanIn) -> None:
    """A whole-scene-list edit on a video's plan or a script version's (S6)."""
    plan = plans.current(db, project)
    if plan is None:
        raise HTTPException(404, "There's no plan yet.")
    _one_at_a_time(db, project)  # a plan being made would overwrite the edit (Flow-QA)
    stars = plans.job_input(db, project, version)["stars"]
    if not stars and any(x.star and not x.product for s in body.scenes for x in s.lines):
        raise HTTPException(  # never drop a ★ silently (QA-2)
            409, "This brand has no product or screen to show yet. Add one to the brand first."
        )
    scenes = [PlanScene(id=i, part=s.part, place=" — ".join(x for x in (s.place, s.time) if x),
                        cast=s.cast_ids,
                        lines=[PlanLine(line=x.n, action=x.action,
                                        product=(x.product or (stars[0] if stars else None))
                                        if x.star else None) for x in s.lines])
              for i, s in enumerate(body.scenes, 1)]  # fmt: skip
    cast = body.cast_ids if body.cast_ids is not None else plan.get("cast", [])
    shape = Structure.model_validate(plan.get("structure"))
    plans.edit(db, project, version, ScenePlan(structure=shape, cast=cast, scenes=scenes))


@router.post("/approve", response_model=ApproveOut, dependencies=[Depends(generation_on)])
def approve(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Approve the plan · makes the shots: the plan is approved and its breakdown is made
    from it, at the breakdown's price. If the shots can't be paid for, nothing changes."""
    project, version = _working(db, user, project_id)
    plan = plans.current(db, project)
    if plan is None:
        raise HTTPException(404, "This video has no plan yet.")
    if plan.get("approved_at"):
        raise HTTPException(409, "This plan is already approved.")
    used = [x["line"] for s in plan["scenes"] for x in s["lines"]]
    if used != plans.lines(db, project, version.text):
        raise HTTPException(409, "The script changed since this plan: make the plan again.")
    if any(not x["action"].strip() for s in plan["scenes"] for x in s["lines"]):
        raise HTTPException(409, "Give every line an action first.")
    plans.approve(project, user.id)
    job = queue_shots(db, user, project, version)  # a refusal rolls the approval back too
    return ApproveOut(plan=_out(db, user, project), job=JobOut.model_validate(job))


@router.post("/earlier/{index}/use", response_model=PlanOut)
def use_earlier(
    project_id: int, index: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Bring an earlier plan back (free); the plan in hand goes to Earlier plans."""
    project = get_project(db, user, project_id)
    plans.use_earlier(project, index)
    db.commit()
    return _out(db, user, project)
