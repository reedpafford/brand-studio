"""The site's director on a video (docs/next/director-chat.md, first slice): start a run from a
published script, read what it did (its log), stop it. Whoever may change the video may run
it; every action it takes is checked as that person's own press (app/director_tools)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app import asks, director, run_progress
from app.advice import SaidJSON, SaidText
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.projects import Project
from app.routes.clips import generation_on
from app.routes.projects import _mine, get_project, video_writer
from app.schemas import UtcTime

router = APIRouter(
    prefix="/projects/{project_id}/director", tags=["director"],
    dependencies=[Depends(video_writer)],
)  # fmt: skip


class TurnOut(BaseModel):
    turn: int
    tool: str | None  # null while the turn is being decided (or waits for the owner)
    why: str  # its reason; the deliver turn's is the delivery note
    result: str  # what happened: "Making the shots.", "Refused: …" (plain words)
    status: str  # the turn's job: queued, needs_owner_approval, running, succeeded, …
    created_at: UtcTime


class RedidRowOut(BaseModel):
    at: float  # seconds into the cut ("0:14")
    clip: str  # "c7": the clip it names (the text says "Clip 7")
    text: str  # "Clip 7: cartoon eyes landed on the stomach. Remade on Seedance 2.0."


class DeliveryNoteOut(BaseModel):
    """The delivery note (S3-09, S3-10, P-08), as kept when the run delivered."""

    made: str  # What I made
    redid: list[RedidRowOut]  # What I watched and redid, in cut order
    unsure: str  # What remains uncertain, in the director's words ("" when nothing)
    open: list[str] = []  # …and what the server knows is still open: "The cut wasn't
    # watched.", "Clip 3's take wasn't checked.", a finding kept, a step waiting for the owner
    needs: str  # What I need from you; "Nothing. It’s ready to post." only when nothing is
    # open, else "Nothing yet, but look at what remains uncertain before you post it."
    cost: str  # "$9.84 spent of up to $16.86"; an editor's "96 credits used of up to 164 (59%…)"
    spent: float  # credits the whole video had charged at this cut, as its header (S3-12)
    up_to: float  # the video's "up to", in credits, never below `spent`
    spent_usd: float | None  # the owner only: `spent` in dollars, at the header's rate
    cut: int | None = None  # Cut 1, Cut 2, … (S3-12: "Delivery note · Cut 1 · 0:58 · $9.84");
    # None on a note kept before cuts were numbered
    seconds: float  # the cut's length
    clips: int


class EditRef(BaseModel):
    id: int
    at: float  # seconds into the cut ("0:24")
    undone: bool


class ThreadItem(BaseModel):
    id: str  # stable: "m3" a message, "r40" a run's progress card, "t41" a delivery, "a7" a card
    kind: Literal["message", "move", "ask"]  # a person's words, the director's, a card (ask_id)
    at: UtcTime
    who: str  # the person's name, or "Director"
    text: SaidText  # plain words, no ids: a run's card in a line ("Making the clips · 14 of 24 ·
    # scene 4 of 6"), a delivery's note as plain lines
    status: Literal["queued", "running", "held", "done", "refused"] | None  # moves only
    why: str = ""  # "" (kept for the shape: the run's card and note say it all)
    answered: bool | None = None  # a note: a move answered it ("Note N"), else still open
    treatment: SaidJSON = None  # the treatment move: hook, logline, why it holds, beats, ending
    # (no ids in it: "the FOMO home screen", never "screen:3")
    ask_id: int | None = None  # a card: GET /projects/{id}/asks has it whole
    files: list[int] | None = None  # a message's pictures or clips, this video's only (rule 12)
    run: str | None = None  # a run's progress card: GET …/director/progress is its record
    note: DeliveryNoteOut | None = None  # a delivery: its note
    edit: EditRef | None = None  # an edit_cut move's edit: Undo beside it (POST …/cut/edits/…)


class ClipCellOut(BaseModel):
    """One clip on the filmstrip and in the Clips list (S3-03, S6-01, S6-04, S6-05, P-10)."""

    clip_id: str  # "c15"
    number: str  # "15": "Clip 15"; "1b" for a split's c1b (director.clip_no)
    scene: int  # its scene's id
    label: str  # what it shows: "Dr. Pickle points at the clock"
    seconds: int
    model: str  # "Seedance 2.0"
    # too_long: longer than its model makes (S3-11's "Too long for the model")
    state: Literal["todo", "making", "waiting", "failed", "too_long", "flagged", "text", "redone",
                   "done"]  # fmt: skip
    frame_file_id: int | None  # its still (the take's first frame): /files/{id}
    take_id: int | None  # the take in use, once there is one
    note: str  # the state's line: what was found, why it waits or failed ("" when done)
    percent: int | None  # making: how far along (never past 95 until it lands)
    minutes_left: int | None  # making: "about 3 min"
    credits: str | None  # waiting or failed: the price of the press that moves it on, as the
    # viewer reads money ("$0.32" to the owner, "4 credits" to an editor)
    changed: bool  # the director made it again: outlined…
    watched: bool  # …until this person has watched that take (POST …/seen)
    found: bool  # its watch found something on one of its takes (the Flagged filter)


class RunSceneOut(BaseModel):
    id: int
    name: str  # "Hook" (the plan's part), else the scene's heading
    total: int
    done: int  # clips with a take in hand
    clips: list[ClipCellOut]


class RunStepOut(BaseModel):
    key: str  # read, plan, cast, voice, stills, prompts, takes, watching, host, cut
    state: Literal["done", "now", "todo", "wait", "bad"]
    text: str  # "Making takes: 14 of 24"
    sub: str  # now or wait only: "Clip 15 · scene 4 · 6 s · about 3 min"


class ChangedClipOut(BaseModel):
    clip_id: str
    number: int
    take_id: int | None
    frame_file_id: int | None
    watched: bool


class RunStoppedOut(BaseModel):
    by: str  # "Reed stopped the director at 10:14"
    at: str
    made: int
    total: int
    carry_on: str  # "Carry on · up to $10.74 more": what's left of this run's own approved
    # price (rule 34); with none of it left, a new run's whole price
    free: bool = False  # the owner's uncapped site: just "Carry on", the same run, no limit


class RunStopOut(BaseModel):
    """A Stop the run carried on from (S3-08): "Reed stopped the director at 10:31 · carried
    on at 10:40"."""

    by: str
    at: str
    carried_at: str


class RunFixOut(BaseModel):
    kind: Literal["again", "carry_on", "split", "model"]  # again: POST …/clips/{clip}/generate;
    # carry_on: POST …/director; split: POST …/breakdown/fix {problems: [problem]} (free);
    # model: open Video settings to pick a model that makes longer clips
    label: str  # "Split it into 10 clips"
    price: str | None  # as the viewer reads money ("free" for a split); "up to" on the button
    problem: SaidText = ""  # split: the breakdown's problem it fixes, as Fix sends it
    then: str | None = None  # split: what its new clips then need, "up to" (stills, prompts,
    # takes), as the viewer reads money


class RunFailedOut(BaseModel):
    title: str  # "Clip 4 couldn’t be made"
    why: str  # "The service was busy. Nothing was charged."
    offer: str = ""  # "I can split it into 10 clips at the sentence breaks. The words…"
    clip: int | None  # the clip's id for "again"
    fixes: list[RunFixOut]  # never empty (rule 22)


class ClipCountsOut(BaseModel):
    all: int
    needs_you: int  # flagged, waiting or failed: a person's press moves it on
    flagged: int  # the take in use still has what its watch found
    redone: int


class ProgressOut(BaseModel):
    """The newest run's live record (v6 piece C): poll it while `status` is working,
    revising or waiting (the app polls; 3 s is plenty)."""

    run: str
    status: Literal["working", "revising", "waiting", "stopped", "delivered", "needs_fix"]
    title: str  # "Making the clips", "Revising", "Stopped", "Made in 22 min", "Stopped at clip 4"
    sub: str  # "14 of 24 · scene 4 of 6", "1 of 2 changes", "11 of 24 clips made"
    tone: Literal["now", "wait", "done", "bad", "stop"]
    started_at: UtcTime
    ended_at: UtcTime | None
    clips: int
    made: int
    redone: int  # "3 redone after watching"
    scene_at: int  # "scene 4 of 6": the first scene not finished (1-based)
    scenes: list[RunSceneOut]
    counts: ClipCountsOut
    minutes_left: int | None  # "about 2 h 10 min left"
    steps: list[RunStepOut]
    spent: float  # credits the whole video has charged, as its header says (S3-12)
    up_to: float  # the video's "up to", in credits, never below `spent`
    spent_usd: float | None  # the owner only: `spent` in dollars, at the header's rate
    # The owner's uncapped test site (Reed, 6 Nov): this run's own provider charges, whether
    # some aren't reported yet, and what the run will probably cost (an estimate)
    actual_usd: float | None = None
    listed_usd: float | None = None  # of it, at list price (the provider gave no figure)
    unreported: bool = False  # a job still running: its cost comes later
    expected_usd: float | None = None
    cost: str = ""  # "$5.00 spent on this run, $4.00 of it at list price"
    changed: list[ChangedClipOut]  # "Changed after watching" / "Watch the changes"
    stopped: RunStoppedOut | None  # stopped by a person (S3-08); carry_on "" while an
    # editor's Carry on waits for the owner's OK (its card says so)
    stops: list[RunStopOut] = []  # Stops it carried on from, oldest first
    failed: RunFailedOut | None  # stopped on a problem, with its fixes (S3-11)


def _expected_usd(db: Session, user: User, project: Project) -> float | None:
    """On the owner's uncapped site: a run's expected cost, in dollars, rounded up."""
    import math

    from app.credits import uncapped
    from app.models.credits import USD_PER_CREDIT
    from app.routes.asks import _expected

    if not uncapped(user):
        return None
    return math.ceil(_expected(db, project) * USD_PER_CREDIT * 100) / 100


class SeenIn(BaseModel):
    take_ids: list[int] = Field(min_length=1, max_length=500)


class DirectorNoteIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    files: list[int] | None = Field(default=None, max_length=6)  # pictures or clips with it


class WaitingQuestion(BaseModel):
    id: int  # the card's ask id
    topic: str  # "The husband"
    question: str


class DirectorOut(BaseModel):
    status: str  # none, running, delivered or ended
    ended: str  # why it ended, in plain words ("" while running)
    turns: list[TurnOut]  # the deliver turn's why is the delivery note
    credits: float  # the run's cost "up to": its turns and every press its tools made
    spent_usd: float | None  # the owner only: its own Claude time this run (to measure)
    start_blocked: str  # "" when this person can press Make it now; else why (the 409's words)
    thread: list[ThreadItem] = []  # the whole chat on the video, every run, oldest first
    unread: int = 0  # notes waiting for the next Make it ("Start again with this note")
    run_price: float = 0  # before Make it (again): the most one run may charge, "up to" (rule 34)
    run_expected_usd: float | None = None  # the owner's uncapped site: what it will probably
    # cost instead, in dollars ("Make it again · about $8.01")
    spent: float = 0  # what the newest run has charged (held and waiting jobs not counted)
    started: bool = False  # Make it was pressed on this video ("No generation started" before)
    waiting: list[WaitingQuestion] = []  # open questions, oldest first: the pinned bar (S4-03)
    make_it: int | None = None  # its start card, when this person may press Make it (S3-02):
    # POST /asks/{id}/answer {"how": "make_it"}; null otherwise (an editor's held send waits)


def _out(db: Session, user: User, project) -> DirectorOut:
    rows = director.turns(db, project)
    last = rows[-1] if rows else None
    ended = director.ended(db, project)
    delivered = director.delivered(rows)  # a cancelled duplicate after it isn't its end
    status = ("none" if not last else "running" if director.active(db, project)
              else "delivered" if delivered else "ended")  # fmt: skip
    turns = [TurnOut(turn=j.input[director.RUN]["turn"], tool=(j.output or {}).get("tool"),
                     why=director.named((j.output or {}).get("why") or ""),
                     result=run_progress.priced(director.named(j.input.get("result", "")),
                                                user.is_owner),
                     status=j.status, created_at=j.created_at) for j in rows]  # fmt: skip
    spent = director.spent(db, last.input[director.RUN]["id"]) if last else 0
    try:
        _mine(db, user, project.id)  # as the start's own check: the maker or the owner
        blocked = director.blocked(db, project)
    except HTTPException as no:
        blocked = no.detail
    started = run_progress.started(db, project)
    ended = run_progress.priced(ended, user.is_owner)  # rule 4: an editor reads no dollars
    return DirectorOut(status=status, ended=ended, turns=turns,
                       credits=float(director.credits(db, project)),
                       spent_usd=float(spent) if user.is_owner else None,
                       start_blocked=blocked,
                       thread=director.thread(db, project, user),
                       unread=len(director.leftover(db, project)),
                       run_price=0 if status == "running" and started
                       else float(asks.run_price(db, project)),
                       run_expected_usd=_expected_usd(db, user, project),
                       spent=float(director.charged(db, project)), started=started,
                       waiting=[WaitingQuestion(id=a.id, topic=a.topic, question=a.question)
                                for a in asks.waiting(db, project)],
                       make_it=_make_it(db, user, project))  # fmt: skip


def _make_it(db: Session, user: User, project) -> int | None:
    card = asks.start_card(db, project)
    return card if card and asks.may_start(db, user, project) else None


@router.get("", response_model=DirectorOut)
def read(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The newest run: going or not, and each turn (the log on the video)."""
    return _out(db, user, get_project(db, user, project_id))


@router.post("", response_model=DirectorOut, status_code=201, dependencies=[Depends(generation_on)])
def start(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Build the video from its published script (409 if it isn't, or a run is going). The
    treatment comes first, charged nothing; then its start card waits for Make it (S3-02,
    POST /asks/{id}/answer)."""
    project = get_project(db, user, project_id)
    director.start(db, user, project, hold=asks.start_hold(db, user, project))
    return _out(db, user, project)


@router.post("/plan-again", response_model=DirectorOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def plan_again(project_id: int, user: User = Depends(current_user),
               db: Session = Depends(get_db)):  # fmt: skip
    """ "Start the plan again" (S3-08): a new run, as Make it starts one (its treatment first,
    then its start card), that plans the whole video again after Make it instead of carrying
    on from its shots. What was made stays (earlier plans and takes); 409 while a run goes on."""
    project = get_project(db, user, project_id)
    _mine(db, user, project.id)  # as Make it: the video's maker or the owner
    director.start(db, user, project, hold=asks.start_hold(db, user, project), fresh=True)
    return _out(db, user, project)


@router.post("/carry-on", response_model=DirectorOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def carry_on(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Carry on (S3-08) after a person's Stop: the same run goes on where it left off under the
    owner's existing OK, up to what's left of its own approved price ("up to $X more"); a step
    past that waits for the owner. With nothing of it left, a new run with its own start card,
    as Make it starts one. 409 while a run goes on."""
    project = get_project(db, user, project_id)
    _mine(db, user, project.id)  # as Make it: the video's maker or the owner
    director.carry_on(db, user, project)
    return _out(db, user, project)


@router.post("/messages", response_model=DirectorOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def message(
    project_id: int,
    body: DirectorNoteIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Tell the director what to change. While a run goes on, its next turn reads it. After a
    delivery it starts the next run, which reads it: its plan, then its start card (S3-12;
    held for the owner when its maker can't press it, and then nothing runs before their yes).
    After a Stop it waits (`unread`) for Carry on or the next run. Who may: as Make it. At
    most one note a person every 3 s and 30 a run (429). Nothing is charged for a note."""
    project = get_project(db, user, project_id)
    _mine(db, user, project.id)  # as Make it: the video's maker or the owner
    director.say(db, user, project, body.text, [_seeable(db, user, f) for f in body.files or []],
                 revise=True)  # fmt: skip
    return _out(db, user, project)


@router.post("/stop", response_model=DirectorOut)
def stop(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Stop the run: no more turns. What it already started goes on; nothing is undone."""
    project = get_project(db, user, project_id)
    director.stop(db, project, user.id)
    return _out(db, user, project)


@router.get("/progress", response_model=ProgressOut | None)
def progress(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The newest run's live record: its scenes and clips, its steps, its cost; null before
    any run. Free to read, in the same few queries however long the video."""
    return run_progress.record(db, get_project(db, user, project_id), user)


# Its own router: a per-person mark, not a change to the video, so any teammate who can open
# it may mark what they watched (the router above lets only its maker or the owner write).
watched = APIRouter(prefix="/projects/{project_id}/director", tags=["director"])


@watched.post("/seen", status_code=204)
def seen(
    project_id: int, body: SeenIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """This person watched these takes (Watch the changes, or playing a clip): the clips the
    director changed stop being outlined for them. Takes of other videos are ignored."""
    run_progress.seen(db, user, get_project(db, user, project_id), body.take_ids)


def _seeable(db: Session, user: User, file_id: int) -> int:
    from app.routes.files import get_file

    stored = get_file(db, user, file_id)
    if stored.content_type.split("/")[0] not in ("image", "video"):
        raise HTTPException(422, "Send pictures or clips only.")
    return stored.id
