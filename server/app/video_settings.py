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
import math
from contextlib import contextmanager
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import looks
from app.catalogue import catalogue
from app.credits import budget_used
from app.models.accounts import User
from app.models.brands import BrandScreen
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame

SHAPES = ("9:16", "1:1", "16:9", "4:3", "3:4", "21:9")
OVER_BUDGET = "That's more than this video's budget."
ONE = "Change one setting at a time."
NOT_A_MODEL = "There's no such {} model."
PAST_OK = (
    "That takes this video past the price approved (up to {credits} credits), so it needs a "
    "new OK. Nothing changed: pick a model that costs the same or less."
)
OTHER = "{} made with other video settings. Make them again, then make the video."
NO_PRESENTER = "This video has no presenter: its format isn't Presenter."
PRESENTER = ("Pick how the presenter appears: talks to camera, in a corner over the B-roll, or "
             "acts in the story.")  # fmt: skip


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
    if not made.get("model"):  # made before n09 (or only marks like mutes): can't tell
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
    take = db.get(ClipTake, clip.picked_take_id) if clip.picked_take_id else None
    return take is not None and made_stale(project, clip, take)


def made_stale(project: Project, clip: ProjectClip, take: ClipTake) -> bool:
    """This take of the clip made with another video model, shape, flavour or Sung shots."""
    from app.model_map import of_clip, speaks

    sung = (clip.song_slice or {}).get("sung_shots")
    made = take.made_with or {}
    if made.get("model") and bool(made.get("speaks")) != speaks(
        clip, project
    ):  # Omni speech on or off
        return True
    return _stale(project, made, of_clip(project, clip).id, sung)


# --- Choices and prices ----------------------------------------------------------------------


def _models(kind: str) -> list:
    return [m for m in catalogue().values() if m.kind == kind and m.offered]


def check(db: Session, user: User, project: Project, values: dict) -> dict:
    """One setting, valid for this person; returns it as stored (Auto: None)."""
    from app.routes.projects import _check_variants

    if len(values) != 1:
        raise HTTPException(422, ONE)
    field, value = next(iter(values.items()))
    if field == "look":
        value = looks.pick(db, user, value)  # the look's own rules (Off for editors)
        looks.keep_style(db, project, value)  # a published script's style stays (item 7)
    elif field == "broll_look":  # a hosted video's B-roll in another style's look (n31)
        value = looks.pick_broll(db, user, project, value)
    elif field in ("video_model", "image_model"):
        kind = field.split("_")[0]
        if value is not None and value not in {m.id for m in _models(kind)}:
            raise HTTPException(422, NOT_A_MODEL.format("video" if kind == "video" else "picture"))
    elif field == "aspect_ratio" and value not in SHAPES:
        raise HTTPException(422, "Pick a shape: " + ", ".join(SHAPES) + ".")
    elif field == "voice":  # the narrator for this video (S5-02): an app voice or a saved one
        from app import voices

        value = voices.checked(db, project, value)
    elif field == "narration_only":  # Reed, 4 Nov: no talker speaks on Omni here
        if value not in (None, True, False):
            raise HTTPException(422, "Narration only is on or off.")
    elif field == "presenter":  # Reed's L3: how a Presenter video's presenter appears
        from app import host

        if not host.presents(db, project):
            raise HTTPException(409, NO_PRESENTER)
        if value is not None and value not in host.HOW:
            raise HTTPException(422, PRESENTER)
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
    """Credits still to spend: the steps not done yet (the looks still to make among them,
    as the cost bar shows), plus redoing what's out of date."""
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
    values = check(db, user, project, values)
    from app.sheets import roles_needing_look

    was = to_finish(db, project)
    stills_now, clips_now = out_of_date(db, project)
    roles_now = roles_needing_look(db, project)
    flips = 0
    with trying(db, project, values):
        if lip_sync(project) is False and project.song_take_id:
            flips = len(_sung(db, project))
        stills, clips = out_of_date(db, project)
        roles = [r for r in roles_needing_look(db, project) if r not in roles_now]
        now = to_finish(db, project)
    budget = project.budget_credits
    over_budget = bool(budget) and budget_used(db, project) + now > budget  # as the hold counts
    reason = OVER_BUDGET if over_budget else ""
    return {
        "to_finish_credits": float(now), "was_credits": float(was),
        "stills_out_of_date": len({s.id for s in stills} - {s.id for s in stills_now}),
        "clips_out_of_date": len({c.id for c in clips} - {c.id for c in clips_now}),
        "roles_needing_look": roles,
        "sung_to_broll": flips, "over_budget": over_budget,
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


def follow_lip_sync(db: Session, project: Project, could: bool) -> int:
    """After a video-model switch on a song video: Sung shots to B-roll when the new model
    can't lip-sync (remembered), back when it can (unless the editor changed the shot). A UGC
    talker's shots stay: HeyGen lip-syncs them, whatever the B-roll's model (app/talker.py)."""
    from app import talker

    row = _newest(db, project) if project.song_take_id else None
    if row is None or not row.data.get("song") or talker.on(db, project):
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


def switch(db: Session, user: User, project: Project, values: dict, undo: bool = False) -> dict:
    """Switch one setting (refused over the budget, with the reason); returns the
    settings it replaced, for Undo (the same call with them). Undo puts back what the video
    already had, so it's never refused: each paid press still checks when it spends."""
    values = check(db, user, project, values)
    keep = _follow_price(db, user, project, values)  # a freestyle's: past its OK, said first
    found = preview(db, user, project, values)
    if found["reason"] and not undo:
        raise HTTPException(409, found["reason"])
    keep()
    was = {k: getattr(project, k) for k in values}
    could = lip_sync(project)
    for k, v in values.items():
        setattr(project, k, v)
    follow_lip_sync(db, project, could)
    if "video_model" in values:
        from app.breakdown import follow_model

        follow_model(db, project)
    if "look" in values:
        looks.picked_by_person(project)  # a plan's lane leaves it as they chose
        follow_own_looks(db, project)
    db.commit()
    return was


def _follow_price(db: Session, user: User, project: Project, values: dict):
    """A freestyle's video switched before its run asked for any take: its newest send's
    "up to" (and what the owner's OK covers) is the video's whole price with the switch (rule
    36), kept by the step this returns. Past what the owner approved, only the owner may
    switch it: theirs is the new OK (rule 34); an editor's is refused here, saying so."""
    from app.credits import approved
    from app.models.freestyles import Freestyle
    from app.models.jobs import Job
    from app.models.script_library import ScriptDraft
    from app.routes.estimate import run_price
    from app.routes.jobs import PRICE

    fs = db.scalar(select(Freestyle).where(Freestyle.project_id == project.id))
    sent = fs.chat[-1] if fs and fs.chat and "price" in fs.chat[-1] else None
    if sent is None or not project.script_draft_id or db.scalar(select(Job.id).where(
            Job.project_id == project.id, Job.kind == "video", Job.id > sent["job"])):  # fmt: skip
        return lambda: None  # not a freestyle's, or its run makes takes: each step holds
    with trying(db, project, values):
        price = run_price(db, db.get(ScriptDraft, project.script_draft_id), project)
    ok = Decimal(sent.get("approved", sent["price"]))  # the figure the owner said yes to
    if price > ok and not user.is_owner:
        raise HTTPException(409, PAST_OK.format(credits=math.ceil(ok)))

    def keep() -> None:
        fs.chat = [*fs.chat[:-1], {**sent, "price": str(price),
                                   "approved": str(price if user.is_owner else ok)}]  # fmt: skip
        turn = db.get(Job, sent["job"])
        turn.input = {**turn.input, PRICE: str(price)}
        fs.up_to = approved(db, fs)

    return keep


def follow_own_looks(db: Session, project: Project) -> None:
    """A look switch re-casts each role still on its own look to the one it already has in
    the new look (n12), free, so switching back never makes it again. A role the editor gave
    a Cast & places character keeps it."""
    from app import cast_roles

    cast, mine = dict(project.slot_cast or {}), dict(project.slot_looks or {})
    for slot in cast_roles.video_slots(db, project):
        key = str(slot.id)
        there = cast_roles.own_look_in(db, project, slot, project.look or "house")
        if there and mine.get(key) and cast.get(key) == mine[key]:
            cast[key] = mine[key] = there
    project.slot_cast, project.slot_looks = cast, mine


def script_of(db: Session, project: Project):
    """The library script the video is made from (None for a video made without one)."""
    from app.models.script_library import Script, ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id or project.released_draft_id or 0)
    return db.get(Script, draft.script_id) if draft else None


def _presenter(db: Session, project: Project) -> str | None:
    """How a Presenter video's presenter appears now; None for any other video."""
    from app import host

    return host.how(project) if host.presents(db, project) else None


def settings(db: Session, project: Project) -> dict:
    """The row's choices, each with its price in credits."""
    from app.breakdown import video_model
    from app.credits import estimate

    def price(kind: str, m) -> float:
        if kind != "video":  # a still, priced as its job will be
            from app.storyboard import still_credits

            return float(still_credits(db, project.workspace_id, m))
        job = {"model": m.id, "input": {"resolution": m.take_resolution}}
        return float(estimate(db, project.workspace_id, kind, Decimal(1), job))

    from app.enhance import screens_of
    from app.models.brands import Brand

    screens = screens_of(db, db.get(Brand, project.brand_id))  # not an archived product's
    flavours: dict[str, list[str]] = {}
    for s in screens:
        if s.product and s.variant and s.variant not in flavours.setdefault(s.product, []):
            flavours[s.product].append(s.variant)
    script = script_of(db, project)
    with trying(db, project, {"video_model": None}):
        auto = video_model(project).id  # what Auto means for this video
    return {
        "changes": [{k: e[k] for k in ("field", "was", "now", "by", "why", "at")}
                    for e in reversed(project.settings_log or [])],
        "presenter": project.presenter,  # null: the style's start (`presenter_now` says it)
        "presenter_now": _presenter(db, project),
        "narration_only": bool(project.narration_only),
        "voice": project.voice,  # null: the video's own (its host's, its style's or the default)
        "look": project.look, "broll_look": project.broll_look,
        "video_model": project.video_model,
        "image_model": project.image_model, "aspect_ratio": project.aspect_ratio,
        "product_variants": project.product_variants or {},
        "language": script.language if script else "en",
        "video_models": [{"id": m.id, "name": m.name, "credits_per_second": price("video", m),
                          "lip_sync": m.lip_sync, "default": m.id == auto}
                         for m in _models("video")],
        "image_models": [{"id": m.id, "name": m.name, "credits_per_still": price("image", m),
                          "default": m.default}
                         for m in _models("image")],
        "shapes": list(SHAPES), "flavours": flavours,
    }  # fmt: skip
