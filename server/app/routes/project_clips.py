"""A project's clips: ask Claude for one video prompt per clip of the newest breakdown, edit
them, generate takes with the video model, pick and approve one per clip, and stitch the
picked takes into the finished video (free)."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import (
    advice,
    breakdown,
    change,
    clip_prompts,
    clip_takes,
    credits,
    cut_in,
    host,
    item_checks,
    looks,
    model_map,
    narration,
    prompts,
    take_approval,
    take_mute,
    take_sound,
    video_settings,
    watch_report,
    word_splice,
)
from app.advice import Said, SaidText
from app.auth import current_user
from app.db import get_db
from app.item_checks import CheckOut
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, CutEdit, FinalVideo, ProjectClip
from app.models.jobs import WAITING, Job
from app.models.projects import Project
from app.models.scripts import ScriptVersion
from app.models.songs import SongTake
from app.prompts import check
from app.prompts.schemas import Breakdown, ClipPrompt, Reference
from app.routes.clips import _check_media_length, generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import _mine, get_project, video_writer
from app.routes.storyboard import ChangeIn, PriceOut, _newest_breakdown
from app.schemas import PromptText, UtcTime
from app.sheets import require_looks
from app.storyboard import assets as picture_assets

router = APIRouter(
    prefix="/projects/{project_id}", tags=["project clips"], dependencies=[Depends(video_writer)]
)
log = logging.getLogger(__name__)


class ProjectClipIn(BaseModel):
    prompt: PromptText
    references: list[Reference] = Field(max_length=50)


class FaultOut(BaseModel):
    kind: str  # style, action, motion, cast, product, screen, text, lipsync, voice, sound, timing
    at: float | None  # seconds into the take; null: all of it
    says: str  # "Cartoon eyes landed on the stomach"; unconfirmed: "… (not confirmed)"
    verified: bool = True  # seen in the frames or clipped samples; else never remade on its own


class WatchOut(BaseModel):
    """What the director found looking at and measuring this take, and what it did (rule 11)."""

    state: Literal["watching", "done", "failed", "skipped"]
    found: str | None = ""  # "Cartoon eyes landed on the stomach at 0:02. The sound was fine."
    did: str | None = ""  # "Remade it on Seedance 2.0 with “no face on the organs” in the prompt."
    action: Literal["keep", "redo", "held", "flagged", "unsure", "superseded"] | None = None
    note: str | None = ""  # the change, quoted ("no face on the organs")
    at: str | None = None  # when it was watched (ISO)
    faults: list[FaultOut] = []
    credits: float | None = None  # what watching it charged
    remake_credits: float | None = None  # the remake's "up to"
    remake_take: int | None = None  # the take the remake became, once it's made
    waiting: bool = False  # the remake waits for the owner's OK (past the budget)
    kept_by: str | None = None  # a person kept a flagged take (Keep it): their name


class TakeOut(BaseModel):
    id: int
    number: int
    file_id: int
    created_at: UtcTime  # "made 10:42"
    check: CheckOut | None = None  # P4: the advisory check on this take (Advice only)
    words: CheckOut | None = None  # what it says against the script's lines (Advice only)
    verdict: str = "unchecked"  # clean, flagged, checking or unchecked (item_checks.verdict)
    approved_by: str | None = None  # "check": it approved itself, clean (rule 21)
    mutes: list[list[float]] = []  # stretches muted, as added: Undo takes back one (take_mute)
    watch: WatchOut | None = None  # the director's watch of it (app/take_watch)
    remade_from: int | None = None  # the take number its watch remade it from
    model: str | None = None  # the model it was made with, by name ("Seedance 2.0")
    from_still: int | None = None  # the still (file id) it was made from: "From still 2"


class SoundOut(BaseModel):
    """Sound effects added to the picked take on request (app/take_sound.py)."""

    state: Literal["none", "making", "ready", "failed", "removed"]  # removed: a person's "no"
    how: str  # slight, normal or strong: how loud under the take's own sound
    asked: str  # what the person asked for, in their words
    error: SaidText = ""  # its last run failed: why, in plain words (Make again)
    credits: float  # Add sound effects: one run, at its real cost


class NarrationOut(BaseModel):
    voice: str  # "Narration: Sarah · music under it"
    music: bool


class VideoOut(BaseModel):
    """The cut that plays (app/cut.py; the cut editor reads GET …/cut)."""

    number: int  # Cut 1, Cut 2, …
    file_id: int
    take_ids: list[int]  # the picked takes it was made from, in clip order
    out_of_date: bool  # a pick, an edit, anything laid over a take or the song changed since
    song_take_id: int | None = None  # song ads: the take laid under the whole video (V6)
    narration: NarrationOut | None = None  # narrated ads: whose voice, and music under it


class InsertOut(BaseModel):
    """An insert shot (brand screens, no people): "Use the real image" cuts the real picture
    in over this stretch of the clip when the video is made."""

    shot_id: str
    asset_id: str
    name: str
    start: float  # seconds into the clip, as planned
    end: float
    use_real_image: bool


class InsertIn(BaseModel):
    use_real_image: bool


class AutoFixOut(BaseModel):
    fixed: list[str]  # 'removed "9:16"', 'changed "says" to "gestures"'
    undone: bool
    before: str  # the prompt as written, for See the change (after is the clip's prompt)


class Maker(BaseModel):
    id: int
    name: str


class PromptVersionOut(BaseModel):
    index: int  # 0 is the prompt in hand; Go back to this takes another
    made_at: str
    made_by: Maker | None  # null: written by Claude for a job nobody is named on, or before
    current: bool
    prompt: str = ""  # the prompt as it was (History shows it before Go back to this)


class ClipModelOut(BaseModel):
    """The model a clip is made with and why (v6 S6-02's "Model" and "Why")."""

    id: str
    name: str
    why: str
    by: Literal["director", "person", "map"]  # who chose it: the model map is the default


class ProjectClipOut(BaseModel):
    id: int
    clip_id: str
    seconds: int
    prompt: str
    references: list[Reference]
    problems: Said
    kept: Said  # advice kept anyway (never blocks)
    file_id: int | None  # the picked take's video
    takes: list[TakeOut]
    picked_take_id: int | None
    approved: bool
    prompt_ok: bool  # Looks good on the prompt; Make the takes waits for every clip's
    take_credits: float  # what one more take costs (shown on Make clip / Redo)
    stale: bool  # made from an older breakdown
    take_stale: bool = False  # its picked take shows an older sheet (N6): "Out of date"
    inserts: list[InsertOut]
    change: dict | None  # the last Change it note, as on a frame (app/change.py)
    free_fix_used: bool = False  # Fix this clip's prompt's free rewrite used for this prompt
    take_warning: str | None = None  # said before the next take: its last two were refused
    retrying: Literal["refused", "busy"] | None = None  # P3: why its take is being tried again
    retried: Literal["refused", "busy"] | None = None  # P3: its newest take was the retry
    auto_fix: AutoFixOut | None = None  # P3: wording fixed for you, with Undo
    look_fix: str | None = None  # the look's fix to offer when its takes are refused (ST2)
    versions: list[PromptVersionOut] = []  # OR3: this prompt's versions, the one in hand first
    sound: SoundOut | None = None  # the picked take's added sound effects; null with no take
    model: ClipModelOut | None = None  # v6 F: the model it's made with and one line on why
    # The Clips tab's Cost line (S6-02: "$0.64 (2 takes)"): what its takes, stills and their
    # watches have charged, in credits, and how many stills it has had.
    spent: float = 0
    stills: int = 0


def _versions(db: Session, row: ProjectClip) -> list[PromptVersionOut]:
    from app.auth import user_name

    return [PromptVersionOut(index=i, made_at=e["made_at"], current=i == 0,
                             prompt=e.get("prompt") or "",
                             made_by=Maker(id=by, name=user_name(db, by)) if (
                                 by := e.get("made_by_id")) else None)
            for i, e in enumerate(row.prompt_history or [])]  # fmt: skip


def _takes(db: Session, row: ProjectClip) -> list[ClipTake]:
    return list(
        db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id).order_by(ClipTake.number))
    )


_stale = clip_prompts.is_stale


def _out(db: Session, row: ProjectClip, newest: BreakdownVersion | None) -> ProjectClipOut:
    computed = ("stale", "takes", "take_credits", "inserts", "take_warning", "change",
                "take_stale", "approved", "retrying", "retried", "auto_fix",
                "look_fix", "versions", "sound", "model", "spent", "stills")  # fmt: skip
    project = db.get(Project, row.project_id)
    asked = row.change or {}
    if asked.get("status") == "changing":
        rewrite = db.get(Job, asked.get("job_id") or 0)
        if getattr(rewrite, "status", None) not in WAITING:  # ended without saving (failed,
            asked = {**asked, "status": "failed", "error": change.UNFINISHED}  # or stopped)
    inserts = [InsertOut(**vars(i), use_real_image=i.on) for i in cut_in.inserts(db, project, row)]
    takes = _takes(db, row)
    stills = _stills(db, row)  # S-gaps-08 2: the still each take was made from
    checks = item_checks.latest(db, "take", [t.id for t in takes])
    words = item_checks.latest(db, "words", [t.id for t in takes])
    return ProjectClipOut(
        inserts=inserts,
        **{f: getattr(row, f) for f in ProjectClipOut.model_fields if f not in computed},
        takes=[
            TakeOut(
                id=t.id,
                number=t.number,
                file_id=t.file_id,
                created_at=t.created_at,
                check=(seen := item_checks.shown(db, checks.get(t.id))),
                words=(heard := item_checks.shown(db, words.get(t.id))),
                verdict=item_checks.verdict([seen, heard]),
                approved_by=(t.made_with or {}).get("approved_by")
                if row.approved and t.id == row.picked_take_id
                else None,
                mutes=take_mute.spans(t),
                watch=watch_report.shown(db, t),
                remade_from=(t.made_with or {}).get("remade_from"),
                model=_model_name((t.made_with or {}).get("model")),
                from_still=next(iter(clip_prompts._sent(db, row, t) & stills), None),
            )  # fmt: skip
            for t in takes
        ],
        take_credits=clip_takes.take_credits(db, project, row),
        stale=_stale(db, row, newest),
        take_stale=clip_prompts.take_stale(row)
        or looks.take_other(db, project, row)
        or video_settings.take_stale(db, project, row),
        approved=row.approved
        and not looks.take_other(db, project, row)
        and not video_settings.take_stale(db, project, row),
        take_warning=(warning := clip_takes.take_warning(db, row)),
        retrying=(retrying := clip_takes.retrying(db, row)),
        retried=clip_takes.retried(db, row),
        look_fix=prompts.look_fixes(looks.drawn(project)).get("refused")
        if retrying == "refused" or warning
        else None,
        auto_fix=AutoFixOut(**row.auto_fix) if row.auto_fix else None,
        change=asked or None,
        versions=_versions(db, row),
        sound=take_sound.state(db, next((t for t in takes if t.id == row.picked_take_id), None)),
        model=ClipModelOut(**model_map.why(db, project, row)),
        **_spent(db, row),
    )


FACTS = "clip_facts"  # db.info: one video's frames and charged jobs, read once for a whole list


def _facts(db: Session, project_id: int) -> tuple[list, list]:
    """The video's storyboard frames and its counted jobs: from the list's one read, else read."""
    from app.credits import COUNTED
    from app.models.storyboards import StoryboardFrame

    if (cached := db.info.get(FACTS)) and cached[0] == project_id:
        return cached[1], cached[2]
    frames = list(db.scalars(select(StoryboardFrame).where(
        StoryboardFrame.project_id == project_id)))  # fmt: skip
    jobs = list(db.scalars(select(Job).where(Job.project_id == project_id,
                                             Job.status.in_(COUNTED))))  # fmt: skip
    return frames, jobs


def _frames_of(db: Session, row: ProjectClip) -> list:
    frames, _ = _facts(db, row.project_id)
    return [f for f in frames if f.clip_id == row.clip_id and f.breakdown_id == row.breakdown_id]


def _stills(db: Session, row: ProjectClip) -> set[int]:
    """Every still the clip's frame has had (the one in use and the earlier ones)."""
    out = set()
    for f in _frames_of(db, row):
        out |= {f.file_id} if f.file_id else set()
        out |= {e["file_id"] for e in f.earlier or [] if e.get("file_id")}
    return out


def _spent(db: Session, row: ProjectClip) -> dict:
    """What this clip's takes, stills, their checks and its prompt rewrites have charged
    (credits), and how many stills it has had."""
    frames = _frames_of(db, row)
    _, jobs = _facts(db, row.project_id)
    takes, ids = {t.id for t in _takes(db, row)}, {f.id for f in frames}

    def mine(i: dict) -> bool:
        if i.get("project_clip_id") == row.id or i.get("frame_id") in ids:
            return True
        if i.get("take_id") in takes or (i.get("watch") or {}).get("take_id") in takes:
            return True
        return (i.get("target"), i.get("target_id")) in {("clip", row.id),
                                                         *(("frame", f) for f in ids)}  # fmt: skip

    spent = sum(float(j.credits or 0) for j in jobs if mine(j.input or {}))
    stills = sum(bool(f.file_id) + len(f.earlier or []) for f in frames)
    return {"spent": round(spent, 3), "stills": stills}


def _model_name(model_id: str | None) -> str | None:
    from app.catalogue import get_model

    found = get_model(model_id) if model_id else None
    return found.name if found else model_id  # one since taken out of the catalogue: its id


def _clip(db: Session, user: User, project_id: int, clip_id: int):
    project = get_project(db, user, project_id)
    row = db.get(ProjectClip, clip_id)
    if not row or row.project_id != project.id:
        raise HTTPException(404, "No such clip.")
    return project, row


def _clips(db: Session, project_id: int) -> list[ProjectClip]:
    query = select(ProjectClip).where(ProjectClip.project_id == project_id).order_by(ProjectClip.id)
    return list(db.scalars(query))


class RewriteIn(BaseModel):
    clip_id: str | None = None  # one clip ("c2"); else every stale clip (and any new one)


class RewriteOut(BaseModel):
    clip_ids: list[str]  # the clips it would rewrite; [] when none is stale
    credits: int  # "up to": one Claude call, never charged above it


def _rewrite_ids(db: Session, project: Project, clip_id: str | None) -> list[str] | None:
    """None: every clip (no clips yet); else the clips to rewrite."""
    if not _clips(db, project.id):
        return None
    return clip_prompts.to_rewrite(db, project, clip_id)


@router.get("/clips/prompts/price", response_model=RewriteOut)
def rewrite_price(
    project_id: int,
    clip_id: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Rewrite clip prompts · N credits: for every stale clip, or one clip (?clip_id=c2)."""
    project = get_project(db, user, project_id)
    ids = _rewrite_ids(db, project, clip_id)
    bd = _newest_breakdown(db, project)
    every = [c["id"] for c in bd.data["clips"]] if bd else []
    return RewriteOut(
        clip_ids=every if ids is None else ids,
        credits=credits.price(clip_prompts.rewrite_price(db, project, ids)),
    )


@router.post(
    "/clips/prompts", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)]
)
def write_prompts(
    project_id: int,
    body: RewriteIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Write the clip prompts (a paid Claude call): all of them at first, then every stale
    clip, or one clip (Reed, 2026-10-26: Clips never dead-ends). Existing takes are kept as
    earlier takes (clip_prompts.save_clip_prompts)."""
    project = get_project(db, user, project_id)
    if not (bd := _newest_breakdown(db, project)):
        raise HTTPException(409, "Make a breakdown first.")
    require_looks(breakdown.would_show(db, project, bd.data), picture_assets(db, project), 409)
    ids = _rewrite_ids(db, project, body.clip_id if body else None)
    if ids == []:
        raise HTTPException(409, "No clip needs new prompts.")
    return clip_prompts.queue_rewrite(db, user, project, ids)


class FixOut(BaseModel):
    fixed: bool | None  # True: fixed now; None: Claude is fixing it (job); False: can't be
    before: str = ""
    after: str = ""
    reason: str = ""  # why it can't be fixed, in plain words
    job: JobOut | None = None  # the free rewrite of this clip, when the code couldn't fix it
    clip: ProjectClipOut


@router.post("/clips/{clip_id}/fix", response_model=FixOut)
def fix_clip(
    project_id: int, clip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Fix this clip's prompt (spec one-click-fixes.md §5), free and never refused for money:
    its shape is put right in code (seconds, [Image1], audio, Summary and Keep lines); what
    the code can't fix, Claude rewrites for this clip only, charged to no budget or week.
    Looks good is cleared. Undo is PUT of the earlier prompt."""
    project, row = _clip(db, user, project_id, clip_id)
    newest = _newest_breakdown(db, project)
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    was = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, prompt=row.prompt,
                     references=[Reference(**r) for r in row.references])  # fmt: skip
    if not advice.stops(row):
        raise HTTPException(409, "This clip has nothing to fix.")
    if running := clip_prompts.fixing(db, row):  # one in flight per clip: never a second call
        return FixOut(fixed=None, before=was.prompt, job=running, clip=_out(db, row, newest))
    now = clip_prompts.repair_shape(was, bd) if row.prompt else was  # unwritten: Claude
    problems = clip_prompts.clip_problems(db, project, bd, now)
    if now != was:
        row.same_fix = True  # the free fix's own change: its free rewrite stays counted
        row.prompt, row.seconds, row.problems = now.prompt, now.seconds, problems
        row.prompt_ok, row.approved = False, False
        # No job of its own: the project's newest job orders it after a take that failed before.
        newest_job = db.scalar(select(func.max(Job.id)).where(Job.project_id == project.id))
        row.change = {"note": "Fix this clip's prompt", "status": "done", "before": was.prompt,
                      "after": now.prompt, "unchanged": False, "job_id": newest_job}  # fmt: skip
        db.commit()
    if not advice.stops(row):
        return FixOut(fixed=True, before=was.prompt, after=now.prompt,
                      clip=_out(db, row, newest))  # fmt: skip
    if _stale(db, row, newest):
        return FixOut(fixed=False, clip=_out(db, row, newest), reason="This clip was made for an "
                      "older breakdown. Rewrite this clip's prompt first.")  # fmt: skip
    looks = [p for p in advice.stops(row) if "approved look" in p]
    if looks and len(looks) == len(advice.stops(row)):
        return FixOut(fixed=False, clip=_out(db, row, newest), reason=looks[0])
    if row.free_fix_used:  # once per clip per prompt version (Reed, 2026-10-27)
        raise HTTPException(409, "We couldn't fix this one automatically.")
    job = clip_prompts.queue_fix(db, user, project, row, advice.stops(row))
    return FixOut(fixed=None, before=was.prompt, job=job, clip=_out(db, row, newest))


@router.post("/clips/{clip_id}/auto-fix/undo", response_model=ProjectClipOut)
def undo_auto_fix(
    project_id: int, clip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Undo of a wording fix made for you (P3): the prompt's own words come back, free, and
    the flags it fixed are Advice (never a block); it isn't fixed again until it changes."""
    project, row = _clip(db, user, project_id, clip_id)
    fix = row.auto_fix or {}
    if not fix or fix.get("undone"):
        raise HTTPException(409, "There's nothing to undo on this clip.")
    if row.prompt != fix.get("after"):
        raise HTTPException(
            409, "The prompt has changed since the fix, so there's nothing to undo."
        )
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    row.same_fix = True  # its own words back: a used free fix stays used
    row.prompt, row.auto_fix = fix["before"], {**fix, "undone": True}
    was = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, prompt=row.prompt,
                     references=[Reference(**r) for r in row.references])  # fmt: skip
    row.problems = clip_prompts.undone_flags(row, clip_prompts.clip_problems(db, project, bd, was))
    row.prompt_ok = row.approved = False
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.get("/clips", response_model=list[ProjectClipOut])
def list_clips(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(db, user, project_id)
    # free: a role named another way merged, a look approved or swapped since, never stuck
    if any([breakdown.complete_cast(db, project), clip_prompts.repair(db, project)]):
        db.commit()
    newest = _newest_breakdown(db, project)
    db.info[FACTS] = (project.id, *_facts(db, project.id))  # one read for every clip's cost
    try:
        return [_out(db, r, newest) for r in _clips(db, project.id)]
    finally:
        db.info.pop(FACTS, None)


@router.put("/clips/{clip_id}", response_model=ProjectClipOut)
def edit_clip(
    project_id: int,
    clip_id: int,
    body: ProjectClipIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Edit a clip's prompt or references; the cast's sheets are added if missing and its
    problems are checked again. Saving an edit counts as reading it (Looks good)."""
    project, row = _clip(db, user, project_id, clip_id)
    fix = (row.change or {}).get("note") == "Fix this clip's prompt"
    row.same_fix = fix and body.prompt == row.change.get("before")  # its Undo: still counted
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    clip = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, **body.model_dump())
    clip = clip.model_copy(update={"prompt": clip_prompts.words_kept(clip.prompt)})
    clip = clip_prompts.with_cast(db, project, clip, bd, trim=False)
    refused = clip_prompts.refusal(row.problems, row.prompt, clip.prompt)
    if clip.prompt != row.prompt:  # new words: fixed as written, with an Undo for these words
        typed, (fixed, said) = clip.prompt, clip_prompts.reword(clip.prompt, looks.drawn(project))
        clip = clip.model_copy(update={"prompt": fixed})
        row.auto_fix = {"before": typed, "after": fixed, "fixed": said,
                        "undone": False} if said else None  # fmt: skip
    new = clip.prompt != row.prompt or [r.model_dump() for r in clip.references] != row.references
    clip_prompts.before_change(db, row)
    row.prompt, row.references = clip.prompt, [r.model_dump() for r in clip.references]
    row.prompt_ok = True
    row.problems = clip_prompts.clip_problems(db, project, bd, clip) + refused
    if new:
        clip_prompts.log_prompt(db, row, user.id)  # OR3: Versions
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


def _for_clip(given: dict, row: ProjectClip) -> bool:
    """A job that lands on this clip: its take, a change note on it, or a rewrite of it (a
    rewrite of every clip names none)."""
    if given.get("project_clip_id") == row.id:
        return True
    if given.get("step") == "change" and (given.get("target"), given.get("target_id")) == (
        "clip",
        row.id,
    ):
        return True
    ids = given.get("clip_ids")
    return given.get("step") == "clip_prompts" and (ids is None or row.clip_id in ids)


@router.post("/clips/{clip_id}/versions/{index}/use", response_model=ProjectClipOut)
def use_version(
    project_id: int,
    clip_id: int,
    index: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Go back to this (OR3): an earlier version of the prompt is the one in hand again. Free,
    never refused over budget; Undo is index 1 (the one it replaced). Waits while a take or a
    rewrite is being made for this clip, so nothing lands on the wrong version. Whoever made
    the video, or the owner."""
    _mine(db, user, project_id)
    project, row = _clip(db, user, project_id, clip_id)
    if project.archived_at is not None:
        raise HTTPException(409, "This video is archived. Restore it first.")
    busy = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(_for_clip(j.input, row) for j in busy):
        raise HTTPException(409, "Wait for this clip's take or prompt being made.")
    clip_prompts.use_prompt(row, index)
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


class TakeIn(BaseModel):
    note: str = Field("", max_length=500)  # Redo: "What's wrong?" (this take only)


@router.post(
    "/clips/{clip_id}/generate",
    response_model=JobOut,
    status_code=201,
    dependencies=[Depends(generation_on)],
)
def generate(
    project_id: int,
    clip_id: int,
    request: Request,
    body: TakeIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Make a new take of this clip (a paid video job, counted against the project budget).
    A clip with problems must be fixed first."""
    project, row = _clip(db, user, project_id, clip_id)
    if advice.stops(row):  # advice and problems kept anyway never block
        raise HTTPException(409, "Fix this clip's problems first.")
    if _stale(db, row, _newest_breakdown(db, project)):
        raise HTTPException(
            409, "This clip was made for an older breakdown. Rewrite its prompt first."
        )
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    if any(j.input.get("project_clip_id") == row.id for j in pending):
        raise HTTPException(409, "A take of this clip is already being made.")
    note = body.note.strip() if body else ""
    if note:  # a Redo note never changes the dialogue
        bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
        if wrong := check.redo_note(note, bd, row.clip_id):
            raise HTTPException(422, " ".join(wrong))
    job_input = clip_takes.take_input(db, project, row, note)
    model = model_map.of_clip(project, row)  # its own (the director's), else the video's
    files = {k: job_input["files"].get(k, []) for k in clip_takes.KEYS.values()}
    _check_media_length(db, request.app.state.storage, model, files)
    return enqueue(
        db, user, "video", job_input, units=model_map.billed(model, row.seconds), project=project,
        provider="replicate",
    )  # fmt: skip


@router.get("/clips/{clip_id}/change", response_model=PriceOut)
def change_price(
    project_id: int, clip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    project, row = _clip(db, user, project_id, clip_id)
    return PriceOut(credits=credits.price(change.credits(db, project, row)))


@router.post(
    "/clips/{clip_id}/change",
    response_model=JobOut,
    status_code=201,
    dependencies=[Depends(generation_on)],
)
def change_clip(
    project_id: int,
    clip_id: int,
    body: ChangeIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Change it: the note rewrites this clip's prompt; once there's a take, a new take is
    made from it (one price). A note that changes what's said is refused before any charge."""
    project, row = _clip(db, user, project_id, clip_id)
    if _stale(db, row, _newest_breakdown(db, project)):
        raise HTTPException(
            409, "This clip was made for an older breakdown. Rewrite its prompt first."
        )
    return change.start(db, user, project, row, body.note)


@router.post("/clips/{clip_id}/takes/{take_id}/pick", response_model=ProjectClipOut)
def pick_take(
    project_id: int,
    clip_id: int,
    take_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Use this take in the video. Picking another take removes the approval."""
    project, row = _clip(db, user, project_id, clip_id)
    take = db.get(ClipTake, take_id)
    if not take or take.clip_id != row.id:
        raise HTTPException(404, "No such take.")
    if row.picked_take_id != take.id:
        clip_takes.pick(row, take)
        take_approval.unmark(db, row)
        db.flush()
        take_approval.after_check(db, take.id)  # a clean take approves itself (QA-3)
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.post("/clips/{clip_id}/takes/{take_id}/use", response_model=ProjectClipOut)
def use_take(
    project_id: int,
    clip_id: int,
    take_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Use this take · free (S-gaps-08 5): a person's pick is their OK too (rule 21), so the
    clip is ready for the cut at once."""
    pick_take(project_id, clip_id, take_id, user, db)
    return approve(project_id, clip_id, user, db)


@router.post("/clips/{clip_id}/takes/{take_id}/keep", response_model=ProjectClipOut)
def keep_take(
    project_id: int,
    clip_id: int,
    take_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Keep it (S6-04): a take the director's watch flagged, wasn't sure of, or held for the
    owner's OK on its remake, is kept by a person. Its watch says who kept it, the flag clears,
    and it is the clip's take (free)."""
    from app.auth import user_name

    _, row = _clip(db, user, project_id, clip_id)
    take = db.get(ClipTake, take_id)
    if not take or take.clip_id != row.id:
        raise HTTPException(404, "No such take.")
    watch = take.watch or {}
    shown = watch_report.shown(db, take) or {}  # a talker's take shows its host piece's watch
    if shown.get("action") not in ("flagged", "unsure", "held"):
        raise HTTPException(409, "The director didn't flag this take: there's nothing to keep.")
    if shown.get("action") == "held" and (remake := watch.get("remake_job_id")):
        from app.routes.jobs import stop_jobs

        stop_jobs(db, Job.id == remake)  # its remake waited for the owner's OK: nobody wants it now
    name = user_name(db, user.id)
    take.watch = {**watch, "action": "keep", "kept_by": name, "did": f"Kept by {name}."}
    db.flush()
    return use_take(project_id, clip_id, take_id, user, db)


@router.post("/clips/{clip_id}/approve", response_model=ProjectClipOut)
def approve(
    project_id: int,
    clip_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """✓ Looks good: approve the picked take."""
    project, row = _clip(db, user, project_id, clip_id)
    if not row.picked_take_id:
        raise HTTPException(409, "Make a take of this clip first.")
    row.approved, row.change = True, None
    take_approval.by_person(row, db, take_approval.YES)
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.post("/clips/approve-all", response_model=advice.ApproveAllChecked)
def approve_all(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Approve all (Reed, 2026-10-26): every clip with a picked take, made for the newest
    breakdown and with nothing to fix; the others are listed with why. Undo takes back
    exactly these."""
    project = get_project(db, user, project_id)
    newest = _newest_breakdown(db, project)
    approved, skipped = [], []
    for row in _clips(db, project.id):
        if row.approved:
            continue
        why = (
            "no take picked yet" if not row.picked_take_id
            else "made for an older breakdown" if _stale(db, row, newest)
            else "has a problem to fix" if advice.stops(row)
            else ""
        )  # fmt: skip
        if why:
            skipped.append({"id": row.id, "reason": why})
            continue
        row.approved, row.change = True, None
        take_approval.by_person(row, db, take_approval.YES)  # the person's, not the check's
        approved.append(row.id)
    picked = [r.picked_take_id for r in _clips(db, project.id) if r.id in approved]
    flagged = item_checks.with_advice(db, "take", picked, also="words")
    db.commit()
    return advice.ApproveAllChecked(approved=approved, skipped=skipped,
                                    approved_with_advice=flagged)  # fmt: skip


@router.post("/clips/approve-all/undo", response_model=list[ProjectClipOut])
def undo_approve_all(
    project_id: int,
    body: advice.UndoIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo Approve all: exactly the clips it approved go back to not approved."""
    project = get_project(db, user, project_id)
    for row in _clips(db, project.id):
        if row.id in body.ids:
            row.approved = False
    db.commit()
    return list_clips(project_id, user, db)


@router.put("/clips/{clip_id}/inserts/{shot_id}", response_model=ProjectClipOut)
def set_insert(
    project_id: int,
    clip_id: int,
    shot_id: str,
    body: InsertIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Switch "Use the real image" for one insert shot. Free: it applies when the video is
    made, so the take and its approval stay."""
    project, row = _clip(db, user, project_id, clip_id)
    if shot_id not in {i.shot_id for i in cut_in.inserts(db, project, row)}:
        raise HTTPException(404, "That shot isn't an insert in this clip.")
    row.real_images = {**(row.real_images or {}), shot_id: body.use_real_image}
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


def _cut_ins(db: Session, project: Project, clips: list[ProjectClip]) -> list[str]:
    """What the final cut puts over its takes: each insert switched on, each muted stretch, each
    added sound and a presenter's host pieces (so a new one shows as changes waiting)."""
    cuts = [f"{c.clip_id}/{i.shot_id}" for c in clips for i in cut_in.inserts(db, project, c)
            if i.on]  # fmt: skip
    for c in clips:
        take = db.get(ClipTake, c.picked_take_id) if c.picked_take_id else None
        cuts += take_mute.labels(c, take) + word_splice.labels(c, take) + take_sound.labels(c, take)
    return cuts + host.labels(db, project)


@router.post("/clips/{clip_id}/prompt-ok", response_model=ProjectClipOut)
def prompt_looks_good(
    project_id: int, clip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Looks good: the editor read this clip's prompt (and what a note changed in it)."""
    project, row = _clip(db, user, project_id, clip_id)
    row.prompt_ok = True
    if not row.picked_take_id:
        row.change = None
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.delete("/clips/{clip_id}/prompt-ok", response_model=ProjectClipOut)
def undo_prompt_looks_good(
    project_id: int, clip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    project, row = _clip(db, user, project_id, clip_id)
    row.prompt_ok = False
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.post("/clips/{clip_id}/keep", response_model=ProjectClipOut)
def keep_clip_advice(
    project_id: int,
    clip_id: int,
    body: advice.KeepIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Keep anyway: this clip's advice stays as it is. A blocking problem can be kept too once
    the free fix was tried (one-click-fixes.md §5); it then stops blocking the takes."""
    project, row = _clip(db, user, project_id, clip_id)
    tried = row.free_fix_used and bool(row.prompt)  # an unwritten clip has nothing to keep
    advice.keep(
        row, body.problem, None if tried else "Try Fix this clip's prompt first. It's free."
    )
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.delete("/clips/{clip_id}/keep", response_model=ProjectClipOut)
def unkeep_clip_advice(
    project_id: int,
    clip_id: int,
    problem: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo Keep anyway on this clip's advice or kept problem (?problem=, the text as shown)."""
    project, row = _clip(db, user, project_id, clip_id)
    advice.unkeep(row, problem)
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


class MuteIn(BaseModel):
    start: float  # not a number is a 422 from take_mute.add (the default 422 can't echo NaN)
    end: float


def _muting(db: Session, user: User, project_id: int, clip_id: int):
    """The picked take a mute is for: whoever made the video or the owner, never archived."""
    _mine(db, user, project_id)
    project, row = _clip(db, user, project_id, clip_id)
    if project.archived_at is not None:
        raise HTTPException(409, "This video is archived. Restore it first.")
    take = db.get(ClipTake, row.picked_take_id) if row.picked_take_id else None
    if not take:
        raise HTTPException(409, "Make a take of this clip first.")
    return project, row, take


@router.post("/clips/{clip_id}/mute", response_model=ProjectClipOut)
def mute(
    project_id: int,
    clip_id: int,
    body: MuteIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Mute a stretch of the picked take in the final cut (an unscripted line, a gasp). Free;
    the take and its approval stay as they are. Undo: DELETE …/mute/{index}. A director tool
    calls this same route."""
    project, row, take = _muting(db, user, project_id, clip_id)
    try:
        take_mute.add(take, body.start, body.end, longest=float(row.seconds))
    except ValueError as no:
        raise HTTPException(422, str(no)) from no
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.delete("/clips/{clip_id}/mute/{index}", response_model=ProjectClipOut)
def unmute(
    project_id: int,
    clip_id: int,
    index: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Undo a mute: the stretch is heard again in the final cut."""
    project, row, take = _muting(db, user, project_id, clip_id)
    try:
        take_mute.remove(take, index)
    except IndexError:
        raise HTTPException(404, "That stretch isn't muted.") from None
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


@router.delete("/clips/{clip_id}/approve", response_model=ProjectClipOut)
def unapprove(
    project_id: int,
    clip_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project, row = _clip(db, user, project_id, clip_id)
    row.approved = False
    take_approval.by_person(row, db, take_approval.NO)  # the check stays out of this take
    db.commit()
    return _out(db, row, _newest_breakdown(db, project))


def out_of_date(db: Session, projects: list[Project]) -> set[int]:
    """The finished videos whose clips changed since (LW2: lists said "Video done" while it
    was out of date), read as Downloads reads it: a clip unapproved or made for an older
    breakdown or script, or the final cut's picks or real images changed. Free, never
    stored; one query per kind for the whole list, a video's cut-ins only read last."""
    ids = [p.id for p in projects if p.finished_at]
    if not ids:
        return set()
    clips: dict[int, list[ProjectClip]] = {}
    for c in db.scalars(select(ProjectClip).where(ProjectClip.project_id.in_(ids))
                        .order_by(ProjectClip.id)):  # fmt: skip
        clips.setdefault(c.project_id, []).append(c)
    top = select(func.max(BreakdownVersion.id)).where(BreakdownVersion.project_id.in_(ids))
    bds = {b.project_id: b for b in db.scalars(select(BreakdownVersion).where(
        BreakdownVersion.id.in_(top.group_by(BreakdownVersion.project_id))))}  # fmt: skip
    script = dict(db.execute(select(ScriptVersion.project_id, func.max(ScriptVersion.version))
                             .where(ScriptVersion.project_id.in_(ids))
                             .group_by(ScriptVersion.project_id)).all())  # fmt: skip
    videos: dict[int, FinalVideo] = {}
    for v in db.scalars(select(FinalVideo).where(FinalVideo.project_id.in_(ids))
                        .order_by(FinalVideo.id)):  # fmt: skip
        videos[v.project_id] = v  # the newest wins
    old, edits = set(), _edits(db, ids)
    for p in (p for p in projects if p.id in ids):
        bd, rows = bds.get(p.id), clips.get(p.id, [])
        moved = bd is None or bool(script.get(p.id) and bd.script_version != script[p.id])
        # Every clip's take, as cut.ready asks (a person's cut has no Approve, M2); a cut compares
        # its takes below, but a video finished by its zip has only each clip's approval to go on.
        video = videos.get(p.id)
        if any(not c.picked_take_id or (video is None and not c.approved) or moved
               or c.breakdown_id != bd.id or clip_prompts.take_stale(c)
               or looks.take_other(db, p, c) or video_settings.take_stale(db, p, c)
               for c in rows):  # fmt: skip
            old.add(p.id)
        elif video and (
            video.take_ids != [c.picked_take_id for c in rows]
            or (video.edit_ids or []) != edits.get(p.id, [])
            or (video.cut_ins or []) != _cut_ins(db, p, rows)
        ):
            old.add(p.id)
    return old


def _edits(db: Session, ids: list[int]) -> dict[int, list[int]]:
    """Each video's cut edits in force (app/cut.py), in order: a cut made with others is out
    of date."""
    out: dict[int, list[int]] = {}
    for project_id, edit_id in db.execute(select(CutEdit.project_id, CutEdit.id).where(
            CutEdit.project_id.in_(ids), CutEdit.undone_at.is_(None))
            .order_by(CutEdit.id)):  # fmt: skip
        out.setdefault(project_id, []).append(edit_id)
    return out


def _video_out(db: Session, video: FinalVideo) -> VideoOut:
    clips = _clips(db, video.project_id)
    current = [c.picked_take_id for c in clips]
    cuts = _cut_ins(db, db.get(Project, video.project_id), clips)
    old = video.take_ids != current or (video.cut_ins or []) != cuts
    old = old or video.song_take_id != db.get(Project, video.project_id).song_take_id
    old = old or (video.edit_ids or []) != _edits(db, [video.project_id]).get(video.project_id, [])
    take = db.get(SongTake, video.song_take_id) if video.song_take_id else None
    told = (NarrationOut(voice=take.voice, music=bool(take.music_file_id))
            if take and take.kind == narration.KIND else None)  # fmt: skip
    return VideoOut(number=video.number, file_id=video.file_id, take_ids=video.take_ids,
                    out_of_date=old,
                    song_take_id=video.song_take_id, narration=told)  # fmt: skip


@router.get("/video", response_model=VideoOut)
def read_video(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(db, user, project_id)
    video = db.scalar(
        select(FinalVideo)
        .where(FinalVideo.project_id == project.id)
        .order_by(FinalVideo.id.desc())
        .limit(1)
    )
    if not video:
        raise HTTPException(404, "This project has no video yet.")
    return _video_out(db, video)
