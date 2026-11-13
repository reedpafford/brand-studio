"""The cut editor's routes (app/cut.py, app/cut_edits.py; v6 S7-01 to S7-07, S3-12, P-12):
read the cut and its timeline, edit it (free), undo and redo, and make the cut (free: Cut 1,
Cut 2, …, made on the worker while the one before keeps playing). Every change is for
whoever made the video, or the owner."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cut, cut_edits, cut_render, take_sound
from app.auth import current_user
from app.credits import USD_PER_CREDIT
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.clips import ClipTake, FinalVideo
from app.models.jobs import WAITING, Job, JobStatus
from app.models.projects import Project
from app.routes.jobs import enqueue
from app.routes.projects import _mine, get_project, video_writer

router = APIRouter(prefix="/projects/{project_id}/cut", tags=["cut"],
                   dependencies=[Depends(video_writer)])  # fmt: skip
FIXES = {"loop_music": {"loop": True}, "remove_music": {"removed": True}}
Fix = Literal["loop_music", "remove_music", "again"]
SAME_AGAIN = "Loop the music to fit, or remove it, first (both free)."
NOT_MADE = "It didn't finish"


class PieceOut(BaseModel):
    id: str  # c7, or c7.12 for a piece split off it
    clip_id: str
    take_id: int | None
    file_id: int | None  # the take's video
    poster_file_id: int | None  # the still it was made from: its picture on the B-roll lane
    source: str  # where its take is from: "Clip 7", "Take 1", "Bloated after pizza, take 2"
    start: float
    end: float
    in_point: float  # seconds into the take it starts from
    said: str  # the words heard over it
    edited: bool  # an edit touched it
    director: bool  # the director's edit touched it (its dot)
    changed: bool  # not as it is in the cut that plays (its outline)
    card: str | None = None  # a time card on black, a piece with no take: its words


class SpanOut(BaseModel):
    start: float
    end: float
    side: Literal["left", "right"]
    size: Literal["small", "medium", "large"]
    hidden: bool
    director: bool


class PresenterOut(BaseModel):
    name: str
    spans: list[SpanOut]


class CutVoiceOut(BaseModel):
    label: str  # "Dr. Pickle’s voice", "The song"
    text: str


class MusicOut(BaseModel):
    name: str
    file_id: int | None
    quieter_db: float  # under the voice
    gaps: Literal["down", "rise"]  # when no one speaks: Stay down or Rise
    loop: bool
    removed: bool
    director: bool


class WordOut(BaseModel):
    word: str
    start: float
    end: float


class SoundFxOut(BaseModel):
    piece: str
    start: float
    end: float
    state: Literal["making", "ready", "failed"]
    asked: str
    how: str
    director: bool


class TimelineOut(BaseModel):
    mode: Literal["takes", "narrated", "song"]
    length: float
    pieces: list[PieceOut]
    presenter: PresenterOut | None
    voice: CutVoiceOut | None
    music: MusicOut | None
    words: list[WordOut]
    sfx: list[SoundFxOut]
    speed: float = 1.0  # the made cut plays this much faster than its takes' own seconds
    captions: bool = False  # the spoken words burned in (the cut's "captions" edit switches it)
    cards: bool = True  # the plan's time cards shown (the cut's "cards" edit switches it)


class EditOut(BaseModel):
    id: int
    kind: str
    said: str
    at: float
    director: bool
    by: str | None
    undone: bool
    applies: bool  # false once an edit it needed was undone (a split's piece, say)
    in_cut: bool  # in the cut that plays


class CutVersionOut(BaseModel):
    number: int
    file_id: int
    made_at: str
    seconds: float | None = None  # its file's length (E2E 233: "0:18" for a 16.7 s file)


class MakingOut(BaseModel):
    number: int
    percent: int
    doing: str  # "laying Dr. Pickle over the B-roll, music under the voice"
    about_seconds: int  # left, about
    changes: int  # the edits it's made with that the cut before didn't have


class FailedOut(BaseModel):
    number: int
    why: str  # "Cut 3 couldn’t be made: … Nothing was charged." (its own number: "… made again")
    fixes: list[Fix]


class GoingOut(BaseModel):
    piece: str
    label: str  # "Clip 7", "the ending"
    file_id: int | None  # its take in the cut that plays


class CutDirectorOut(BaseModel):
    editing: bool
    doing: str


KEPT = "That would have cut {}, so the edge moved to just past it. Every spoken word stays."
KEPT_ALL = ("That would have cut {}, so the edges moved to just past them. Every spoken word "
            "stays.")  # fmt: skip


class CutOut(BaseModel):
    number: int | None  # the cut that plays (Cut 2); None before the first
    file_id: int | None
    seconds: float | None = None  # its file's length
    out_of_date: bool
    versions: list[CutVersionOut]
    making: MakingOut | None
    failed: FailedOut | None
    timeline: TimelineOut
    edits: list[EditOut]
    changes: int  # edits not in the cut yet
    can_undo: bool
    can_redo: bool
    can_edit: bool  # whoever made the video, or the owner: everyone else only watches
    notice: str | None = None  # an edit moved to keep a spoken word: what happened (S4)
    sound_credits: float  # Add sound effects on a clip: one run, "up to" ("under 1 credit")
    sound_usd: float | None  # the same in dollars, for the owner only ("up to $0.01")
    going: list[GoingOut]  # what the next cut changes
    director: CutDirectorOut


class EditIn(BaseModel):
    kind: Literal["trim", "retime", "split", "swap", "presenter", "music", "captions", "cards"]
    piece: str | None = Field(None, max_length=40)
    start: float | None = None  # cut seconds
    end: float | None = None
    in_point: float | None = Field(None, ge=0)
    at: float | None = None  # split here
    snap: bool = False  # Snap to words
    take_id: int | None = None  # swap for it
    side: Literal["left", "right"] | None = None
    size: Literal["small", "medium", "large"] | None = None
    hidden: bool | None = None
    quieter_db: float | None = None
    gaps: Literal["down", "rise"] | None = None
    loop: bool | None = None
    removed: bool | None = None
    file_id: int | None = None  # music to swap to
    on: bool | None = None  # captions burned in, or the plan's time cards shown, or not


class CutFixIn(BaseModel):
    fix: Fix


class SwapOut(BaseModel):
    take_id: int
    file_id: int
    poster_file_id: int | None
    label: str  # "In the cut", "Take 1", "Clip 4", "Library"
    kind: Literal["in_cut", "take", "clip", "library"]


class MusicChoiceOut(BaseModel):
    file_id: int
    name: str


def _newest_job(db: Session, project: Project) -> Job | None:
    return db.scalar(select(Job).where(Job.project_id == project.id,
                                       Job.input["step"].as_string() == cut.STEP)
                     .order_by(Job.id.desc()).limit(1))  # fmt: skip


def _failed(db: Session, project: Project, playing: FinalVideo | None) -> FailedOut | None:
    job = _newest_job(db, project)
    if job is None or job.status in WAITING:  # every cut is a cut_make job's: none is newer
        return None
    out = job.output or {}
    if job.status == JobStatus.succeeded and not out.get("problem"):
        return None
    why, n = (out.get("problem") or NOT_MADE).rstrip("."), job.input["number"]
    again = " again" if playing and playing.number == n else ""  # the director's own, made again
    return FailedOut(number=n, fixes=out.get("fixes") or ["again"],
                     why=f"Cut {n} couldn’t be made{again}: {why}. Nothing was "
                         "charged.")  # fmt: skip


def _about(db: Session, project: Project, job: Job) -> int:
    """Seconds left, about: as long as the video's last cut took, else a guess by length."""
    done = db.scalar(select(Job).where(Job.project_id == project.id,
                                       Job.input["step"].as_string() == cut.STEP,
                                       Job.status == JobStatus.succeeded)
                     .order_by(Job.id.desc()).limit(1))  # fmt: skip
    took = ((done.finished_at - done.started_at).total_seconds()
            if done and done.started_at and done.finished_at else None)  # fmt: skip
    whole = round(took) if took else cut_render.about(job.input["timeline"]["length"])
    gone = (utcnow() - job.started_at).total_seconds() if job.started_at else 0
    return max(5, round(whole - gone))


def _making(db: Session, storage, project: Project) -> MakingOut | None:
    job = cut.making(db, project)
    if job is None:
        return None
    key, percent = job.input["progress_key"], 0
    if job.status == JobStatus.running and storage.exists(key):
        percent = int(storage.get(key) or 0)
    return MakingOut(number=job.input["number"], percent=percent, doing=job.input["doing"],
                     about_seconds=_about(db, project, job),
                     changes=job.input["changes"])  # fmt: skip


def _director(db: Session, project: Project) -> CutDirectorOut:
    """The director at work on the cut: its run goes on and its last move edits the cut."""
    from app import director

    turn = director.active(db, project)
    move = (turn.output or {}) if turn else {}
    editing = move.get("tool") in ("edit_cut", "add_sound", "final_cut")
    return CutDirectorOut(editing=editing, doing=move.get("why", "") if editing else "")


def _going(db: Session, project: Project, tl: dict, changed: set[str]) -> list[GoingOut]:
    """What the next cut changes: pieces edited since, and clips with a take being made."""
    remade = {(j.input or {}).get("project_clip_id") for j in db.scalars(select(Job).where(
        Job.project_id == project.id, Job.status.in_(WAITING),
        Job.input["step"].as_string() == "clip_take"))}  # fmt: skip
    rows = {r.id: r.clip_id for r in cut.rows(db, project)}
    remade = {rows.get(i) for i in remade}
    last = tl["pieces"][-1]["id"] if tl["pieces"] else None
    return [GoingOut(piece=p["id"], label="the ending" if p["id"] == last else cut.label(p["id"]),
                     file_id=_file(db, p["take_id"]))
            for p in tl["pieces"] if p["id"] in changed or p["clip_id"] in remade]  # fmt: skip


def _file(db: Session, take_id: int | None) -> int | None:
    take = db.get(ClipTake, take_id) if take_id else None
    return take.file_id if take else None


def state(db: Session, project: Project, storage, user: User) -> CutOut:
    from app.routes.project_clips import out_of_date

    playing = cut.newest(db, project)
    tl, lost = cut.timeline(db, project)
    made = (playing.timeline or cut.base(db, project)) if playing else {}  # a cut before n42: base
    was = {p["id"]: p for p in made.get("pieces") or []}
    keys = ("start", "end", "from", "take_id")
    changed = {p["id"] for p in tl["pieces"] if playing and (
        p["id"] not in was or any(p[k] != was[p["id"]].get(k) for k in keys))}  # fmt: skip
    words = tl["words"]
    pieces = [PieceOut(**{k: p[k] for k in ("id", "clip_id", "take_id", "source", "start",
                                            "end", "edited", "director")},
                       file_id=_file(db, p["take_id"]), in_point=p["from"],
                       poster_file_id=cut.poster(db, p["take_id"]),
                       changed=p["id"] in changed, card=p.get("card"),
                       said=" ".join(w["word"] for w in words
                                     if p["start"] <= (w["start"] + w["end"]) / 2 < p["end"]))
              for p in tl["pieces"]]  # fmt: skip
    music = tl["music"]
    timeline = TimelineOut(
        mode=tl["mode"], length=tl["length"], pieces=pieces, words=words,
        presenter=tl["presenter"], voice=tl["voice"], sfx=cut.sfx(db, tl),
        speed=tl.get("speed", 1.0),
        captions=bool(tl.get("captions")), cards=bool(tl.get("cards", True)),
        music=MusicOut(**{"name": "Music", "file_id": None, "director": False, **music})
        if music else None)  # fmt: skip
    in_cut = set(playing.edit_ids or []) if playing else set()
    rows, live = cut.every(db, project), {e.id for e in cut.active(db, project)}
    names = {u.id: u.name for u in db.scalars(select(User).where(
        User.id.in_({e.by_id for e in rows if e.by_id})))}  # fmt: skip
    edits = [EditOut(id=e.id, kind=e.kind, said=e.said, at=e.at, director=e.director,
                     by=names.get(e.by_id), undone=e.undone_at is not None,
                     applies=e.id not in lost, in_cut=e.id in in_cut) for e in rows]  # fmt: skip
    sound = take_sound.price(db, project.workspace_id)
    versions = db.scalars(select(FinalVideo).where(FinalVideo.project_id == project.id)
                          .order_by(FinalVideo.id))  # fmt: skip
    return CutOut(
        number=playing.number if playing else None,
        file_id=playing.file_id if playing else None,
        seconds=playing.seconds if playing else None,
        out_of_date=bool(playing) and project.id in out_of_date(db, [project]),
        versions=[CutVersionOut(number=v.number, file_id=v.file_id, seconds=v.seconds,
                                made_at=v.created_at.isoformat())
                  for v in {v.number: v for v in versions}.values()],  # made again: the newest
        making=_making(db, storage, project), failed=_failed(db, project, playing),
        timeline=timeline, edits=edits, changes=len(live ^ in_cut), can_undo=bool(live),
        can_redo=cut_edits.redoable(db, project) is not None,
        going=_going(db, project, tl, changed), director=_director(db, project),
        can_edit=user.is_owner or project.created_by_id == user.id,
        sound_credits=float(sound), sound_usd=float(sound * USD_PER_CREDIT) if user.is_owner
        else None,
    )  # fmt: skip


@router.get("", response_model=CutOut)
def read(project_id: int, request: Request, user: User = Depends(current_user),
         db: Session = Depends(get_db)):  # fmt: skip
    """The cut that plays, the one being made, and the timeline with its edits."""
    return state(db, get_project(db, user, project_id), request.app.state.storage, user)


@router.post("", response_model=CutOut, status_code=202)
def make(project_id: int, request: Request, user: User = Depends(current_user),
         db: Session = Depends(get_db)):  # fmt: skip
    """Make the cut (free): the next Cut, on the worker; the one before plays until it's
    ready. A director tool calls this same route."""
    from app.credits import lock
    from app.routes.project_clips import _cut_ins

    project, storage = _mine(db, user, project_id), request.app.state.storage
    lock(db, Project, project.id)  # two presses at once: the second sees the first's job
    if job := cut.making(db, project):
        raise HTTPException(409, cut.MAKING.format(job.input["number"]))
    cut.ready(db, project, storage)
    clips, playing = cut.rows(db, project), cut.newest(db, project)
    tl, _ = cut.timeline(db, project)
    try:  # a new pick under an old trim, say: never a cut that loses a spoken word
        cut_edits.keeps_every_word(db, tl)
    except cut.Refused as no:
        hint = ("" if not cut.active(db, project)  # nothing edited: the cut's own words
                else " Undo that edit, or trim the clip out to the word." if tl["mode"] == "takes"
                else " Undo or re-time that edit first.")  # fmt: skip
        raise HTTPException(409, f"{no}{hint}") from no
    live = [e.id for e in cut.active(db, project)]
    song = cut.song(db, project)
    data = {"step": cut.STEP, "project_id": project.id,
            "number": cut.next_number(db, project, playing), "edit_ids": live,
            "take_ids": [c.picked_take_id for c in clips], "cut_ins": _cut_ins(db, project, clips),
            "song_take_id": song.id if song else None, "timeline": tl,
            "recipe": cut_render.recipe(db, project, tl), "doing": cut.doing(tl),
            "changes": len(set(live) ^ set(playing.edit_ids or [] if playing else [])),
            "progress_key": f"progress/cut-{uuid.uuid4().hex}"}  # fmt: skip
    failed, before = _failed(db, project, playing), _newest_job(db, project)
    same = ("edit_ids", "take_ids", "cut_ins", "song_take_id")
    if failed and failed.fixes != ["again"] and all(before.input.get(k) == data[k] for k in same):
        raise HTTPException(409, f"{failed.why} {SAME_AGAIN}")  # it would fail the same way
    enqueue(db, user, cut.STEP, data, units=0, project=project, provider="local", prepaid=True)
    return state(db, project, storage, user)


def _edited(db: Session, project: Project, storage, user: User, do) -> CutOut:
    try:
        do()
    except cut.Refused as no:
        db.rollback()
        raise HTTPException(422, str(no)) from no
    db.commit()
    return state(db, project, storage, user)


@router.post("/edits", response_model=CutOut, status_code=201)
def edit(project_id: int, body: EditIn, request: Request, user: User = Depends(current_user),
         db: Session = Depends(get_db)):  # fmt: skip
    """One edit (free): trim, re-time to the words, split, swap, presenter or music."""
    from app.routes.jobs import DIRECTOR_TOOL

    project = _mine(db, user, project_id)
    asked = body.model_dump(exclude_none=True, exclude={"kind"})
    if "in_point" in asked:
        asked["from"] = asked.pop("in_point")
    made = []
    out = _edited(db, project, request.app.state.storage, user,
                  lambda: made.append(cut_edits.add(db, user, project, body.kind, asked,
                                                    director=DIRECTOR_TOOL.get())))  # fmt: skip
    if made and made[0].kept:  # moved to keep a word (S4): said, never a refusal with no way on
        words = made[0].kept
        out.notice = (KEPT if len(words) == 1 else KEPT_ALL).format(cut_edits.quoted(words))
    return out


@router.post("/edits/{edit_id}/undo", response_model=CutOut)
def undo_one(project_id: int, edit_id: int, request: Request,
             user: User = Depends(current_user), db: Session = Depends(get_db)):  # fmt: skip
    """Undo this edit (the director's each have Undo)."""
    project = _mine(db, user, project_id)
    return _edited(db, project, request.app.state.storage, user,
                   lambda: cut_edits.undo(db, project, edit_id))  # fmt: skip


@router.post("/undo", response_model=CutOut)
def undo(project_id: int, request: Request, user: User = Depends(current_user),
         db: Session = Depends(get_db)):  # fmt: skip
    project = _mine(db, user, project_id)
    return _edited(
        db, project, request.app.state.storage, user, lambda: cut_edits.undo(db, project)
    )


@router.post("/redo", response_model=CutOut)
def redo(project_id: int, request: Request, user: User = Depends(current_user),
         db: Session = Depends(get_db)):  # fmt: skip
    project = _mine(db, user, project_id)
    return _edited(
        db, project, request.app.state.storage, user, lambda: cut_edits.redo(db, project)
    )


@router.post("/undo-all", response_model=CutOut)
def undo_all(project_id: int, request: Request, user: User = Depends(current_user),
             db: Session = Depends(get_db)):  # fmt: skip
    """Back to the cut that plays: every edit since is undone."""
    project = _mine(db, user, project_id)
    return _edited(db, project, request.app.state.storage, user,
                   lambda: cut_edits.undo_all(db, project))  # fmt: skip


@router.post("/fix", response_model=CutOut, status_code=202)
def fix(project_id: int, body: CutFixIn, request: Request, user: User = Depends(current_user),
        db: Session = Depends(get_db)):  # fmt: skip
    """A failed cut's one-click fix (free): loop the music to fit, remove it, or try again."""
    project = _mine(db, user, project_id)
    if body.fix in FIXES:
        try:
            cut_edits.add(db, user, project, "music", FIXES[body.fix])
        except cut.Refused as no:
            db.rollback()
            raise HTTPException(422, str(no)) from no
        db.commit()
    return make(project_id=project_id, request=request, user=user, db=db)


@router.get("/swaps/{piece}", response_model=list[SwapOut])
def swaps(project_id: int, piece: str, user: User = Depends(current_user),
          db: Session = Depends(get_db)):  # fmt: skip
    """What a B-roll piece can swap to: as it is, its clip's other takes, the other clips'
    picked takes, and the brand's other videos' takes you can see (the Library)."""
    project = get_project(db, user, project_id)
    tl, _ = cut.timeline(db, project)
    try:
        p = tl["pieces"][cut._find(tl, piece)]
    except cut.Refused as no:
        raise HTTPException(404, str(no)) from no
    return [
        SwapOut(**s, poster_file_id=cut.poster(db, s["take_id"]))
        for s in cut_edits.swaps(db, user, project, tl, p)
    ]


@router.get("/music", response_model=list[MusicChoiceOut])
def music(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Music the cut can swap to: the brand's music beds and songs."""
    return cut_edits.music_choices(db, get_project(db, user, project_id))
