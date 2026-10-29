"""Video settings (flows VS1): a video's look, video model, picture model, shape and flavour,
each switched with one confirm ("To finish: about N credits (was M)") that names what goes out
of date. Nothing is deleted: a still or take keeps what it was made with (`made_with`), is
Out of date while that differs from the video's settings now, and is current again when the
video switches back. A model that can't lip-sync turns a song video's Sung shots to B-roll;
a lip-sync one turns them back, except a shot the editor changed in between.

Prices are the catalogue's (the same estimates `enqueue` charges); the look's rules are
app/looks.py, called here, never copied. Stills and takes made before n09 carry no
`made_with` and so never read as out of date."""

import hashlib
import json
from contextlib import contextmanager
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import looks
from app.catalogue import catalogue
from app.credits import credits_used, get_limits
from app.models.accounts import User
from app.models.brands import BrandScreen
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame

FIELDS = ("look", "video_model", "image_model", "aspect_ratio", "product_variants")
SHAPES = ("9:16", "1:1", "16:9", "4:3", "3:4", "21:9")
OVER_BUDGET = "That's more than this video's budget."
OVER_CAP = "Over the video limit ({} credits)."
ONE = "Change one setting at a time."
NOT_A_MODEL = "There's no such {} model."
OTHER = "{} made with other video settings. Make them again, then make the video."


# --- What a still or take was made with ------------------------------------------------------


def made_with(db: Session, project: Project, refs: list[str], model_id: str,
              sung_shots: list[str] | None = None) -> dict:  # fmt: skip
    """Recorded with the job when it's asked for (a switch while it runs doesn't change it):
    the model, the shape, the product variants it attached and, for a take, its Sung shots."""
    products = {}
    for ref in refs:
        if ref.startswith("screen:"):
            screen = db.get(BrandScreen, int(ref.split(":")[1]))
            if screen is not None and screen.product and screen.variant:
                products[screen.product] = screen.variant
    found = {"model": model_id, "aspect_ratio": project.aspect_ratio, "products": products}
    if sung_shots is not None:
        found["sung_shots"] = sorted(sung_shots)
    return found


def _stale(project: Project, made: dict, model_id: str, sung_now: list[str] | None) -> bool:
    if not made:  # made before n09: we can't tell
        return False
    chosen = project.product_variants or {}
    return (made.get("model") != model_id
            or made.get("aspect_ratio") != project.aspect_ratio
            or any(chosen.get(p, v) != v for p, v in made.get("products", {}).items())
            or ("sung_shots" in made and sorted(sung_now or []) != made["sung_shots"]))  # fmt: skip


def frame_stale(project: Project, frame: StoryboardFrame) -> bool:
    """A still made with another picture model, shape or flavour than the video's now."""
    from app.storyboard import image_model

    return bool(frame.file_id) and _stale(project, frame.made_with or {},
                                          image_model(project).id, None)  # fmt: skip


def take_stale(db: Session, project: Project, clip: ProjectClip) -> bool:
    """The clip's picked take made with another video model, shape, flavour or Sung shots."""
    from app.breakdown import video_model

    take = db.get(ClipTake, clip.picked_take_id) if clip.picked_take_id else None
    sung = (clip.song_slice or {}).get("sung_shots")
    return take is not None and _stale(project, take.made_with or {}, video_model(project).id,
                                       sung)  # fmt: skip


# --- Choices and prices ----------------------------------------------------------------------


def _models(kind: str) -> list:
    return [m for m in catalogue().values() if m.kind == kind]


def _check(db: Session, user: User, project: Project, values: dict) -> dict:
    """One setting, valid for this person; returns it as stored (Auto: None)."""
    from app.routes.projects import _check_variants

    if len(values) != 1:
        raise HTTPException(422, ONE)
    field, value = next(iter(values.items()))
    if field == "look":
        value = looks.pick(db, user, value)  # the look's own rules (Off for editors)
    elif field in ("video_model", "image_model"):
        kind = field.split("_")[0]
        if value is not None and value not in {m.id for m in _models(kind)}:
            raise HTTPException(422, NOT_A_MODEL.format("video" if kind == "video" else "picture"))
    elif field == "aspect_ratio" and value not in SHAPES:
        raise HTTPException(422, "Pick a shape: " + ", ".join(SHAPES) + ".")
    elif field == "product_variants":
        value = _check_variants(db, project.brand_id, value or {})
    return {field: value}


@contextmanager
def trying(db: Session, project: Project, values: dict):
    """The video as it would be with these settings, never written."""
    with db.no_autoflush:
        old = {k: getattr(project, k) for k in values}
        for k, v in values.items():
            setattr(project, k, v)
        try:
            yield project
        finally:
            for k, v in old.items():
                setattr(project, k, v)


def _frames(db: Session, project: Project) -> list[StoryboardFrame]:
    return list(db.scalars(select(StoryboardFrame).where(StoryboardFrame.project_id == project.id)))


def _clips(db: Session, project: Project) -> list[ProjectClip]:
    return list(db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)))


def out_of_date(db: Session, project: Project) -> tuple[list, list]:
    """The stills and clips out of date now: another look (app/looks.py) or other settings."""
    stills = [f for f in _frames(db, project)
              if looks.frame_other(project, f) or frame_stale(project, f)]  # fmt: skip
    clips = [c for c in _clips(db, project)
             if looks.take_other(db, project, c) or take_stale(db, project, c)]  # fmt: skip
    return stills, clips


def to_finish(db: Session, project: Project) -> Decimal:
    """Credits still to spend: the steps not done yet, plus redoing what's out of date."""
    from app import clip_takes, storyboard
    from app.routes.estimate import _stages

    stills, clips = out_of_date(db, project)
    left = sum(Decimal(str(s.credits)) for s in _stages(db, project))
    redo = len(stills) * storyboard.still_price(db, project)
    redo += sum((clip_takes.take_credits(db, project, c) for c in clips), Decimal(0))
    return (left + redo).quantize(Decimal("0.01"))


def lip_sync(project: Project) -> bool:
    from app.breakdown import video_model

    return video_model(project).lip_sync


def _newest(db: Session, project: Project) -> BreakdownVersion | None:
    return db.scalar(select(BreakdownVersion).where(BreakdownVersion.project_id == project.id)
                     .order_by(BreakdownVersion.id.desc()).limit(1))  # fmt: skip


def _sung(db: Session, project: Project) -> list[str]:
    row = _newest(db, project) if project.song_take_id else None
    song = (row.data.get("song") if row else None) or {}
    return [sid for sid, t in song.get("shots", {}).items() if t.get("sung")]


def preview(db: Session, user: User, project: Project, values: dict) -> dict:
    """The confirm: what this one switch costs to finish and what goes out of date."""
    values = _check(db, user, project, values)
    was = to_finish(db, project)
    stills_now, clips_now = out_of_date(db, project)
    flips = 0
    with trying(db, project, values):
        if lip_sync(project) is False and project.song_take_id:
            flips = len(_sung(db, project))
        stills, clips = out_of_date(db, project)
        now = to_finish(db, project)
    used = credits_used(db, project)
    cap = get_limits(db, project.workspace_id).per_video_max_credits
    over_cap = used + now > cap
    budget = project.budget_credits
    over_budget = bool(budget) and used + now > budget
    reason = OVER_CAP.format(cap) if over_cap else OVER_BUDGET if over_budget else ""
    return {
        "to_finish_credits": float(now), "was_credits": float(was),
        "stills_out_of_date": len({s.id for s in stills} - {s.id for s in stills_now}),
        "clips_out_of_date": len({c.id for c in clips} - {c.id for c in clips_now}),
        "sung_to_broll": flips, "over_budget": over_budget, "over_cap": over_cap,
        "reason": reason,
    }  # fmt: skip


# --- The switch -----------------------------------------------------------------------------


def _shot(data: dict, shot_id: str) -> dict | None:
    return next((s for scene in data.get("scenes", []) for s in scene.get("shots", [])
                 if s.get("id") == shot_id), None)  # fmt: skip


def _print(data: dict, shot_id: str) -> str:
    """A shot as the editor sees it (its plan and its time in the song), Sung aside: a shot
    whose print changed since the flip was edited, so it stays as the editor left it."""
    timed = {k: v for k, v in data["song"]["shots"].get(shot_id, {}).items() if k != "sung"}
    found = json.dumps([_shot(data, shot_id), timed], sort_keys=True, default=str)
    return hashlib.sha256(found.encode()).hexdigest()[:16]


def _set_sung(db: Session, project: Project, row: BreakdownVersion, sung: dict[str, bool]):
    """Sung or B-roll on the newest plan's song part (in place: the pictures don't change),
    and each of its clips' song slice follows."""
    from app.song_breakdown import slice_of

    shots = row.data["song"]["shots"]
    shots = {sid: ({**t, "sung": sung[sid]} if sid in sung else t) for sid, t in shots.items()}
    song = {**row.data["song"], "shots": shots}
    row.data = {**row.data, "song": song}
    for clip in db.scalars(select(ProjectClip).where(ProjectClip.breakdown_id == row.id)):
        clip.song_slice = slice_of(row.data, clip.clip_id)


def _follow_lip_sync(db: Session, project: Project, could: bool) -> int:
    """After a video-model switch on a song video: Sung shots to B-roll when the new model
    can't lip-sync (remembered), back when it can (unless the editor changed the shot)."""
    row = _newest(db, project) if project.song_take_id else None
    if row is None or not row.data.get("song"):
        return 0
    can = lip_sync(project)
    if could and not can:
        sung = _sung(db, project)
        project.sung_flipped = [{"shot": s, "print": _print(row.data, s)} for s in sung]
        _set_sung(db, project, row, dict.fromkeys(sung, False))
        return len(sung)
    if can and not could and project.sung_flipped:
        shots = row.data["song"]["shots"]
        back = [f["shot"] for f in project.sung_flipped
                if f["shot"] in shots and not shots[f["shot"]].get("sung")
                and _print(row.data, f["shot"]) == f["print"]]  # fmt: skip
        _set_sung(db, project, row, dict.fromkeys(back, True))
        project.sung_flipped = []
        return len(back)
    return 0


def switch(db: Session, user: User, project: Project, values: dict) -> dict:
    """Switch one setting (refused over the budget or the cap, with the reason); returns the
    settings it replaced, for Undo (the same call with them)."""
    values = _check(db, user, project, values)
    found = preview(db, user, project, values)
    if found["reason"]:
        raise HTTPException(409, found["reason"])
    was = {k: getattr(project, k) for k in values}
    could = lip_sync(project)
    for k, v in values.items():
        setattr(project, k, v)
    _follow_lip_sync(db, project, could)
    db.commit()
    return was


def script_of(db: Session, project: Project):
    """The library script the video is made from (None for a video made without one)."""
    from app.models.script_library import Script, ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id or project.released_draft_id or 0)
    return db.get(Script, draft.script_id) if draft else None


def settings(db: Session, project: Project) -> dict:
    """The row's choices, each with its price in credits and whether it's over the cap."""
    from app.credits import estimate

    used = credits_used(db, project)
    cap = get_limits(db, project.workspace_id).per_video_max_credits

    def price(kind: str, m) -> float:
        job = {"model": m.id, "input": {"resolution": "480p" if kind == "video" else "1K"}}
        return float(estimate(db, project.workspace_id, kind, Decimal(1), job))

    def over(field: str, value) -> bool:
        with trying(db, project, {field: value}):
            return used + to_finish(db, project) > cap

    screens = db.scalars(select(BrandScreen).where(BrandScreen.brand_id == project.brand_id,
                                                   BrandScreen.deleted_at.is_(None)))  # fmt: skip
    flavours: dict[str, list[str]] = {}
    for s in screens:
        if s.product and s.variant and s.variant not in flavours.setdefault(s.product, []):
            flavours[s.product].append(s.variant)
    script = script_of(db, project)
    return {
        "look": project.look, "video_model": project.video_model,
        "image_model": project.image_model, "aspect_ratio": project.aspect_ratio,
        "product_variants": project.product_variants or {},
        "language": script.language if script else "en",
        "video_models": [{"id": m.id, "name": m.name, "credits_per_second": price("video", m),
                          "lip_sync": m.lip_sync, "default": m.default,
                          "over_cap": over("video_model", m.id)} for m in _models("video")],
        "image_models": [{"id": m.id, "name": m.name, "credits_per_still": price("image", m),
                          "default": m.default, "over_cap": over("image_model", m.id)}
                         for m in _models("image")],
        "shapes": list(SHAPES), "flavours": flavours,
    }  # fmt: skip
