"""Freestyle (Reed's v4): a video from a pasted script, a type, a look, a shape and an optional
brand, changed by chatting. It replaces Quick clip. An editor's every send (the first and each
change) waits for the owner before anything is spent; the owner's own run straight away. Not
charged to any video's budget, never gated by the Quick clip week; each job carries its
freestyle (`FREESTYLE`) for Usage. One clip is a single take, no plan or cut. Dialogue is run
by the director on the freestyle's own hidden script and video (app/hidden.py): an editor's
send waits for the owner as the run's first turn, and the owner's OK covers the price shown
(`up_to`, the video's budget), no more. Song and Narrated come next."""

import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import director, hidden, looks, prompts
from app.auth import current_user
from app.catalogue import get_model
from app.credits import (
    COUNTED,
    FREESTYLE,
    PAST_APPROVED,
    WAIT_OK,
    approved,
    estimate,
    get_limits,
    lock,
    over_cap,
)
from app.db import get_db, utcnow
from app.models.accounts import User
from app.models.brands import Brand
from app.models.clips import FinalVideo
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.scripts import ScriptVersion
from app.references import LONG_SIDE
from app.routes.brands import get_brand
from app.routes.clips import generation_on
from app.routes.estimate import run_price
from app.routes.jobs import CHANGE, DECLINE, PRICE, SAID, WITHDRAWN, enqueue, stop_jobs

router = APIRouter(prefix="/freestyles", tags=["freestyles"])
Type = Literal["dialogue", "song", "narrated", "one_clip"]
Shape = Literal["9:16", "1:1", "16:9"]
Status = Literal["waiting", "working", "delivered", "declined", "stopped", "withdrawn", "failed"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
Change = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
MODEL, RESOLUTION = "seedance-2.5", "480p"  # Quick clip's defaults
NOT_YET = "Song and Narrated are coming next; One clip and Dialogue work now."
ONE_SOURCE = "Paste a script, or pick one: not both."
NO_LOOK = "Pick a look."
HAS_VIDEO = "This version already has a video."
FREEZE = "freeze"  # an editor's first turn: what the owner's OK makes real (`freeze`)
DIRECTED = {"dialogue": "story"}  # the types the director makes: the script kind it reads
PAST_CAP = (
    "That change would take this freestyle past its limit of {cap} credits. Start a new "
    "freestyle from here."
)
HELD = f"{WAIT_OK}every freestyle send is checked first."
BUSY = "Wait for the last send to finish, or stop it."
NONE = "No such freestyle."
MAX_PROMPT = 6000  # what Quick clip sends at most
TOO_LONG = "That's more changes than one clip can carry. Start a new freestyle from here."


class FreestyleIn(BaseModel):
    """A pasted script (`text`, with its look), or "Make a video" from a script's version
    (`script_id`, `slot`): its kind, look and brand are the script's."""

    type: Type = "dialogue"
    look: str | None = None
    shape: Shape
    brand_id: int | None = None
    text: Text | None = None
    script_id: int | None = None
    slot: int | None = None  # the script's version (A is 0, the default)
    make_another: bool | None = None  # a version that has a video: make a new one from it too


class MessageIn(BaseModel):
    text: Change


class TitleIn(BaseModel):
    title: Title


class FreestyleItem(BaseModel):
    """One line of the thread, the same shape as a video's director thread."""

    id: str  # m{n} for a message, t{job id} for a move: stable across reads
    kind: Literal["message", "move"]
    at: datetime
    who: str
    text: str
    status: Literal["held", "queued", "running", "refused", "done"] | None
    why: str = ""  # a move's reason when it has one (the director-run types)


class FreestyleRow(BaseModel):
    id: int
    title: str
    type: Type
    status: Status
    created_at: datetime
    created_by_name: str


class FreestyleOut(FreestyleRow):
    look: str
    shape: Shape
    brand_id: int | None
    credits: float  # everything asked so far that wasn't declined, withdrawn or stopped unstarted
    file_id: int | None  # the delivered take or cut, for the player and Download MP4
    up_to: float | None = None  # a director-run freestyle: the price the owner's OK covers
    project_id: int | None = None  # its video (a director-run one): in Videos when it has a brand
    script_id: int | None = None  # and its script: in Scripts when it has a brand
    thread: list[FreestyleItem]


class EstimateOut(BaseModel):
    credits: float


def _seconds(text: str) -> int:
    """One clip's length: about 2.5 words a second spoken, within the model's limits."""
    span = get_model(MODEL).duration
    return max(span.min, min(span.max, math.ceil(prompts.spoken_words(text) / 2.5)))


def _job_input(fs: Freestyle, texts: list[str]) -> dict:
    """A single take, drawn in the look: the script, then each change asked since."""
    own, base = (prompts.style(i)["sections"] for i in (fs.look, looks.base(fs.look)))
    style = own.get("clip_style") or base.get("clip_style", "")  # a lane's, else its look's
    changes = "".join(f"\nChange: {t}" for t in texts[1:])
    return {
        FREESTYLE: fs.id,
        "model": MODEL,
        "brand_id": fs.brand_id,
        "fit_images_to": LONG_SIDE[RESOLUTION],
        "input": {
            "prompt": f"{style}\n{texts[0]}{changes}".strip(),
            "duration": _seconds(texts[0]),
            "resolution": RESOLUTION,
            "aspect_ratio": fs.shape,
            "generate_audio": True,
        },
    }


def _db(db: Session = Depends(get_db)) -> Session:
    """Freestyle's routes work on its hidden script and video."""
    return hidden.see(db)


def _freestyle_brand(db: Session, workspace_id: int) -> Brand:
    """The workspace's hidden "Freestyle" brand, for a freestyle with no brand picked."""
    found = db.scalar(select(Brand).where(Brand.workspace_id == workspace_id, Brand.hidden))
    if found is None:
        found = Brand(workspace_id=workspace_id, name="Freestyle", slug="_freestyle", hidden=True)
        db.add(found)
        db.flush()
    return found


def _video(db: Session, user: User, fs: Freestyle, text: str) -> tuple[Project, ScriptDraft]:
    """The freestyle's own script (published, its one version approved) and video: in the
    brand's Scripts and Videos when a brand is picked (P3: the director-first video), else
    hidden under the Freestyle brand."""
    brand_id = fs.brand_id or _freestyle_brand(db, user.workspace_id).id
    hide = fs.brand_id is None or not user.is_owner  # an editor's shows once the owner OKs it
    script = Script(workspace_id=user.workspace_id, brand_id=brand_id, title=fs.title,
                    kind=DIRECTED[fs.type], look=fs.look, published=True, hidden=hide,
                    created_by_id=user.id)  # fmt: skip
    db.add(script)
    db.flush()
    draft = ScriptDraft(script_id=script.id, slot=0, text=text, status="approved",
                        approved_at=utcnow(), approved_by_id=user.id)  # fmt: skip
    db.add(draft)
    db.flush()
    project = Project(workspace_id=user.workspace_id, brand_id=brand_id, hidden=hide,
                      name=f"{fs.title[:100]} · freestyle {fs.id}", created_by_id=user.id,
                      script_draft_id=draft.id, look=fs.look, aspect_ratio=fs.shape)  # fmt: skip
    db.add(project)
    db.flush()
    db.add(ScriptVersion(project_id=project.id, version=1, text=text, source="library",
                         created_by_id=user.id))  # fmt: skip
    return project, draft


def _from_script(db: Session, user: User, request: Request, fs: Freestyle, script: Script,
                 draft: ScriptDraft, another: bool | None = False,
                 ) -> tuple[Project, ScriptDraft]:  # fmt: skip
    """ "Make a video" from a script's version (P1): the version is frozen, approved, and the
    script published with it (rule 31: an edit after is a new version; the video keeps this
    one), then its one video as Make this version makes it: its cast, plan and saved shots,
    landed free when they follow its plan (#934, Reed's item 8). A version that has a video
    makes another only when asked (`make_another`); else the 409 says which, and its price."""
    from app.routes.script_produce import make_video

    lock(db, ScriptDraft, draft.id)  # two sends at once: the second finds the first's video
    had = db.scalar(select(Project.id).where(Project.script_draft_id == draft.id)
                    .order_by(Project.id.desc()))  # fmt: skip
    if had and not another:  # "Open it · Make another · up to N credits"
        raise HTTPException(409, {"text": HAS_VIDEO, "project_id": had,
                                  "up_to": float(run_price(db, draft))})  # fmt: skip
    project, _, _ = make_video(db, user, request, script, draft, {"aspect_ratio": fs.shape},
                               another=bool(another))  # fmt: skip
    if user.is_owner:
        freeze(db, {"project": project.id, "draft": draft.id, "show": True}, user)
    else:  # an editor's: nothing changes, nothing shows, until the owner's OK
        project.hidden = True
    return project, draft


def freeze(db: Session, what: dict, owner: User) -> None:
    """A director-first video becomes real when its run starts (the owner's at once, an
    editor's on the owner's OK; Next-Lead): its version frozen, approved and the script
    published (rule 31), and, with a brand, its script and video shown."""
    project = db.get(Project, what["project"])
    draft = db.get(ScriptDraft, what["draft"])
    script = db.get(Script, draft.script_id)
    if draft.status != "approved":
        draft.status, draft.approved_at, draft.approved_by_id = "approved", utcnow(), owner.id
    script.published = True
    if what["show"]:
        project.hidden = script.hidden = False


def release(db: Session, what: dict) -> None:
    """An editor's send declined or withdrawn before it ran: nothing is left behind. Its video
    stays hidden and lets go of the version, which stays as it was, free to make again."""
    project = db.get(Project, what["project"])
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    project.script_draft_id = None
    if draft is not None:
        draft.reserved_by_id = None


def _start(db: Session, user: User, fs: Freestyle, text: str, made=None) -> None:
    """A Dialogue send: its video (`made`: from a script), then the director's first turn
    (held for an editor's)."""
    at = utcnow().isoformat()  # the message comes before the moves it starts
    project, draft = made or _video(db, user, fs, text)
    what = {"project": project.id, "draft": draft.id, "show": fs.brand_id is not None}
    fs.project_id, fs.up_to = project.id, run_price(db, draft, project)  # all a run may spend
    cap = get_limits(db, user.workspace_id).per_video_max_credits
    if fs.up_to > cap:
        db.rollback()
        raise over_cap(user, cap)
    db.flush()
    if user.is_owner:
        freeze(db, what, user)
    turn = director.start(db, user, project, wait="" if user.is_owner else HELD, frozen=False,
                          extra={FREESTYLE: fs.id, SAID: text, CHANGE: False,
                                 PRICE: str(fs.up_to),
                                 **({} if user.is_owner else {FREEZE: what})})  # fmt: skip
    fs.chat = [{"by": user.id, "text": text, "at": at, "job": turn.id, "price": str(fs.up_to)}]
    db.commit()


def _change(db: Session, user: User, fs: Freestyle, text: str) -> None:
    """A change to a Dialogue freestyle (the Producer, 3b). While a run goes on it's a note,
    read at the director's next turn, inside the price already approved. Otherwise the send
    is the press: quoted "up to" the whole video's price again, and the running total stays
    under the per-video cap; a new run reads every unread note, an editor's after the
    owner's OK, the owner's at once."""
    project = db.get(Project, fs.project_id)
    at = utcnow().isoformat()
    if director.active(db, project):
        director.say(db, user, project, text)
        fs.chat = [*fs.chat, {"by": user.id, "text": text, "at": at, "job": None}]
        db.commit()
        return
    draft = db.get(ScriptDraft, project.script_draft_id)
    price = run_price(db, draft, project)
    total, cap = approved(db, fs) + price, get_limits(db, user.workspace_id).per_video_max_credits
    if total > cap:
        raise HTTPException(409, PAST_CAP.format(cap=cap))
    director.say(db, user, project, text)  # unread: the new run reads it
    turn = director.start(db, user, project, wait="" if user.is_owner else HELD,
                          extra={FREESTYLE: fs.id, SAID: text, CHANGE: True,
                                 PRICE: str(price)})  # fmt: skip
    fs.chat = [*fs.chat, {"by": user.id, "text": text, "at": at, "job": turn.id,
                          "price": str(price)}]  # fmt: skip
    fs.up_to = total
    db.commit()


def _check(db: Session, user: User, type: str, look: str, brand_id: int | None) -> None:
    if type != "one_clip" and type not in DIRECTED:
        raise HTTPException(422, NOT_YET)
    looks.pick(db, user, look)  # an editor: only a look that's on
    if brand_id is not None:
        get_brand(db, user, brand_id)


def _get(db: Session, user: User, freestyle_id: int) -> Freestyle:
    """The maker's or, for the owner, anyone's; to anyone else it isn't there."""
    fs = db.get(Freestyle, freestyle_id)
    if not fs or fs.workspace_id != user.workspace_id:
        raise HTTPException(404, NONE)
    if not (user.is_owner or fs.created_by_id == user.id):
        raise HTTPException(404, NONE)
    return fs


def _jobs(db: Session, fs: Freestyle) -> dict[int, Job]:
    ids = [m["job"] for m in fs.chat if m.get("job")]
    return {j.id: j for j in db.scalars(select(Job).where(Job.id.in_(ids)))} if ids else {}


def _send(db: Session, user: User, fs: Freestyle, text: str) -> None:
    """Add a message and start its take: held for the owner when an editor sends it."""
    texts = [m["text"] for m in fs.chat] + [text]
    input = _job_input(fs, texts)
    if len(input["input"]["prompt"]) > MAX_PROMPT:  # every change rides in one clip's prompt
        raise HTTPException(409, TOO_LONG)
    lock(db, Freestyle, fs.id)  # a freestyle is one video: its sends share the per-video cap
    earlier = sum(j.credits for j in _jobs(db, fs).values() if j.status in COUNTED)
    units = Decimal(input["input"]["duration"])
    cap = get_limits(db, user.workspace_id).per_video_max_credits
    if earlier + estimate(db, user.workspace_id, "video", units, input) > cap:
        db.rollback()
        raise over_cap(user, cap)
    input = {**input, SAID: text, CHANGE: bool(fs.chat)}  # for Needs you: what this send asks
    if fs.brand_id is None:  # charged to the hidden Freestyle brand: Usage shows it as such
        input["brand_id"] = _freestyle_brand(db, user.workspace_id).id
    job = enqueue(db, user, "video", input, units=input["input"]["duration"],
                  provider="replicate", wait="" if user.is_owner else HELD)  # fmt: skip
    message = {"by": user.id, "text": text, "at": utcnow().isoformat(), "job": job.id}
    fs.chat = [*fs.chat, message]
    db.commit()


def _move(fs: Freestyle, job: Job) -> tuple[str, str, str]:
    """(freestyle status, move status, plain words) for one send's job."""
    s = job.status
    if s == JobStatus.needs_owner_approval:
        return "waiting", "held", "Waiting for the owner's OK."
    if s == JobStatus.queued:
        return "working", "queued", "Starting the clip."
    if s == JobStatus.running:
        return "working", "running", "Making the clip."
    if s == JobStatus.succeeded:
        return "delivered", "done", "Made the clip."
    if s == JobStatus.failed:
        return "failed", "refused", f"Couldn't make it: {job.error or 'it failed'}"
    if job.input.get(DECLINE):
        return "declined", "refused", f"The owner declined: {job.error}"
    if job.input.get(WITHDRAWN):
        return "withdrawn", "refused", "Withdrawn."
    return "stopped", "refused", "Stopped."


def _out(db: Session, fs: Freestyle) -> FreestyleOut:
    jobs = _jobs(db, fs)
    names = dict(db.execute(select(User.id, User.name).where(
        User.id.in_({fs.created_by_id, *(m["by"] for m in fs.chat)}))).all())  # fmt: skip
    thread, status, file_id, credits = [], "waiting", None, Decimal(0)
    for n, m in enumerate(fs.chat, 1):
        at = datetime.fromisoformat(m["at"])
        thread.append(FreestyleItem(id=f"m{n}", kind="message", at=at, who=names.get(m["by"], ""),
                                    text=m["text"], status=None))  # fmt: skip
        job = jobs.get(m.get("job"))
        if job is None:
            continue
        status, move, words = _move(fs, job)
        thread.append(FreestyleItem(id=f"t{job.id}", kind="move", at=job.created_at,
                                    who="Director", text=words, status=move))  # fmt: skip
        if job.status == JobStatus.succeeded:
            file_id = ((job.output or {}).get("file_ids") or [None])[0]
        if job.status in (*COUNTED, JobStatus.needs_owner_approval):
            credits += job.credits  # never a failed, declined, withdrawn or stopped one
    if fs.project_id:  # the director's run: its moves, cut and cost
        status, thread, file_id, credits = _directed(db, fs, jobs, thread)
    project = db.get(Project, fs.project_id) if fs.project_id else None
    draft = db.get(ScriptDraft, project.script_draft_id) if project else None
    return FreestyleOut(**_row(fs, names, status).model_dump(), look=fs.look, shape=fs.shape,
                        brand_id=fs.brand_id, credits=credits, file_id=file_id,
                        up_to=fs.up_to, project_id=fs.project_id,
                        script_id=draft.script_id if draft else None, thread=thread)  # fmt: skip


def _directed(db: Session, fs: Freestyle, jobs: dict, said: list) -> tuple:
    """(status, thread, file id, credits) of a director-run freestyle, from its video's run."""
    project = db.get(Project, fs.project_id)
    sends = [jobs[m["job"]] for m in fs.chat if m.get("job") in jobs]
    last = sends[-1] if sends else None  # the newest send: the first, or a change's new run
    words = {f"t{j.id}": f"The owner declined: {j.error}" for j in sends if j.input.get(DECLINE)}
    words |= {f"t{j.id}": "Withdrawn." for j in sends if j.input.get(WITHDRAWN)}
    if last is not None and last.input.get(DECLINE):
        status = "declined"
    elif last is not None and last.input.get(WITHDRAWN):
        status = "withdrawn"
    elif last is not None and last.status == JobStatus.needs_owner_approval:
        status = "waiting"
    elif director.active(db, project):  # paused for a new OK, past the price approved
        held = select(Job.id).where(Job.project_id == project.id,
                                    Job.status == JobStatus.needs_owner_approval)  # fmt: skip
        status = "waiting" if db.scalar(held.limit(1)) else "working"
    else:
        rows = director.turns(db, project)
        status = "delivered" if rows and rows[-1].input.get("result") == "Delivered." else "stopped"
    moves = [FreestyleItem(**{**m, "text": words.get(m["id"], m["text"])})
             for m in director.thread(db, project) if m["kind"] == "move"]  # fmt: skip
    held = db.scalars(select(Job).where(  # a take or a watch past the price, waiting mid-run
        Job.project_id == project.id, Job.status == JobStatus.needs_owner_approval,
        Job.input["step"].as_string() != director.STEP)).all()  # fmt: skip
    moves += [FreestyleItem(id=f"j{j.id}", kind="move", at=j.created_at, who="Director",
                            text=j.input.get("held") or PAST_APPROVED, status="held")
              for j in held]  # fmt: skip
    delivered = db.scalar(select(func.max(Job.created_at)).where(  # the last delivery
        Job.project_id == project.id, Job.input["step"].as_string() == director.STEP,
        Job.input["result"].as_string() == "Delivered."))  # fmt: skip
    file_id = delivered and db.scalar(  # the cut it delivered, until another is delivered
        select(FinalVideo.file_id).where(FinalVideo.project_id == project.id,
                                         FinalVideo.created_at <= delivered)
        .order_by(FinalVideo.id.desc()))  # fmt: skip
    thread = sorted([*(m for m in said if m.kind == "message"), *moves], key=lambda m: m.at)
    return status, thread, file_id, director.credits(db, project)


def _row(fs: Freestyle, names: dict[int, str], status: str) -> FreestyleRow:
    return FreestyleRow(id=fs.id, title=fs.title, type=fs.type, status=status,
                        created_at=fs.created_at,
                        created_by_name=names.get(fs.created_by_id, ""))  # fmt: skip


def _source(db: Session, user: User, body) -> tuple:
    """(type, look, brand, words, script, draft) of a send: a pasted script, or a script's
    version ("Make a video", P1) with the script's own kind, look and brand."""
    if (body.text is None) == (body.script_id is None):
        raise HTTPException(422, ONE_SOURCE)
    if body.script_id is None:
        if not body.look:
            raise HTTPException(422, NO_LOOK)
        return body.type, body.look, body.brand_id, body.text, None, None
    from app import script_library as lib

    script = lib.get_script(db, user, body.script_id)
    draft = lib.get_draft(db, script, body.slot or 0)
    kind = next((t for t, k in DIRECTED.items() if k == script.kind), None)
    if kind is None:
        raise HTTPException(422, NOT_YET)
    return kind, script.look, script.brand_id, draft.text, script, draft


@router.get("/estimate", response_model=EstimateOut)
def estimate_freestyle(
    shape: Shape,
    type: Type = "dialogue",
    look: str | None = None,
    text: Text | None = None,
    script_id: int | None = None,
    slot: int = 0,
    user: User = Depends(current_user),
    db: Session = Depends(_db),
):
    """What a send would cost, at most. Free: nothing is queued and nothing is asked of a model."""
    body = FreestyleIn(type=type, look=look, shape=shape, text=text, script_id=script_id, slot=slot)
    type, look, brand_id, text, _, draft = _source(db, user, body)
    _check(db, user, type, look, None)
    if draft is not None:  # a script's version: its own price
        return EstimateOut(credits=run_price(db, draft))
    if type in DIRECTED:  # the video's own price, from a draft never kept
        fs = Freestyle(workspace_id=user.workspace_id, created_by_id=user.id, title="Estimate",
                       type=type, look=look, shape=shape, chat=[])  # fmt: skip
        db.add(fs)
        db.flush()
        project, draft = _video(db, user, fs, text)
        cost = run_price(db, draft, project)
        db.rollback()
        return EstimateOut(credits=cost)
    fs = Freestyle(id=0, look=look, shape=shape, brand_id=None)
    input = _job_input(fs, [text])
    units = Decimal(input["input"]["duration"])
    return EstimateOut(credits=estimate(db, user.workspace_id, "video", units, input))


@router.post("", response_model=FreestyleOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def create_freestyle(
    body: FreestyleIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(_db),
):
    type, look, brand_id, text, script, draft = _source(db, user, body)
    _check(db, user, type, look, brand_id)
    lock(db, User, user.id)  # a double tap waits here, then finds the first one
    since = utcnow() - timedelta(seconds=10)
    for fs in db.scalars(select(Freestyle).where(Freestyle.created_by_id == user.id,
                                                 Freestyle.created_at >= since)):  # fmt: skip
        same = (fs.type, fs.look, fs.shape, fs.brand_id) == (type, look, body.shape, brand_id)
        first = db.get(Job, fs.chat[0]["job"]) if fs.chat and fs.chat[0].get("job") else None
        waiting = first is not None and first.status in (JobStatus.needs_owner_approval,
                                                         JobStatus.queued)  # fmt: skip
        if same and waiting and fs.chat[0]["text"] == text:  # a repeat sent on purpose
            # (the first done or gone) is a new freestyle
            db.rollback()
            return _out(db, fs)  # the same send twice: one freestyle, one held take
    title = (script.title if script else
             next(line.strip() for line in text.splitlines() if line.strip()))[:60]  # fmt: skip
    fs = Freestyle(workspace_id=user.workspace_id, created_by_id=user.id, title=title,
                   type=type, look=look, shape=body.shape, brand_id=brand_id,
                   chat=[])  # fmt: skip
    db.add(fs)
    db.flush()
    if script is not None:
        made = _from_script(db, user, request, fs, script, draft, body.make_another)
        _start(db, user, fs, text, made)
    else:
        (_start if type in DIRECTED else _send)(db, user, fs, text)
    return _out(db, fs)


@router.get("", response_model=list[FreestyleRow])
def list_freestyles(
    everyone: bool = False, user: User = Depends(current_user), db: Session = Depends(_db)
):
    """The caller's freestyles, newest first; `everyone`: the whole team's (owner only)."""
    if everyone and not user.is_owner:
        raise HTTPException(403, "Only the owner can see everyone's freestyles.")
    query = select(Freestyle).where(Freestyle.workspace_id == user.workspace_id)
    if not everyone:
        query = query.where(Freestyle.created_by_id == user.id)
    rows = db.scalars(query.order_by(Freestyle.id.desc()).limit(200)).all()
    names = dict(db.execute(select(User.id, User.name).where(
        User.workspace_id == user.workspace_id)).all())  # fmt: skip
    return [_row(fs, names, _out(db, fs).status) for fs in rows]


@router.get("/{freestyle_id}", response_model=FreestyleOut)
def get_freestyle(
    freestyle_id: int, user: User = Depends(current_user), db: Session = Depends(_db)
):
    return _out(db, _get(db, user, freestyle_id))


@router.post("/{freestyle_id}/messages", response_model=FreestyleOut, status_code=201,
             dependencies=[Depends(generation_on)])  # fmt: skip
def send_message(
    freestyle_id: int,
    body: MessageIn,
    user: User = Depends(current_user),
    db: Session = Depends(_db),
):
    """A change: a new take with every change asked so far, held like the first send. Only its
    maker sends (the owner reads anyone's)."""
    fs = _get(db, user, freestyle_id)
    if fs.created_by_id != user.id:
        raise HTTPException(403, "Only whoever made this freestyle can change it.")
    if fs.type in DIRECTED:
        _change(db, user, fs, body.text)
        return _out(db, fs)
    if any(j.status in (JobStatus.needs_owner_approval, JobStatus.queued, JobStatus.running)
           for j in _jobs(db, fs).values()):  # fmt: skip
        raise HTTPException(409, BUSY)
    _send(db, user, fs, body.text)
    return _out(db, fs)


@router.post("/{freestyle_id}/withdraw", response_model=FreestyleOut)
def withdraw_freestyle(
    freestyle_id: int, user: User = Depends(current_user), db: Session = Depends(_db)
):
    """The maker takes back a send still waiting for the owner. Nothing was spent."""
    fs = _get(db, user, freestyle_id)
    if fs.created_by_id != user.id:
        raise HTTPException(403, "Only whoever made this freestyle can withdraw it.")
    held = Job.status == JobStatus.needs_owner_approval
    ids = [j.id for j in _jobs(db, fs).values() if j.status == JobStatus.needs_owner_approval]
    done = db.execute(update(Job).where(Job.id.in_(ids), held)  # can't race the owner's OK
                      .values(status=JobStatus.cancelled, finished_at=utcnow()))  # fmt: skip
    if not done.rowcount:
        raise HTTPException(409, "Nothing is waiting to withdraw.")
    for job in db.scalars(select(Job).where(Job.id.in_(ids))):
        job.input = {**job.input, WITHDRAWN: True}
        if job.input.get(FREEZE):
            release(db, job.input[FREEZE])
    db.commit()
    return _out(db, fs)


@router.post("/{freestyle_id}/stop", response_model=FreestyleOut)
def stop_freestyle(
    freestyle_id: int, user: User = Depends(current_user), db: Session = Depends(_db)
):
    """Stop what's waiting or being made, by its maker or the owner. A take already at the
    provider is discarded when it lands."""
    fs = _get(db, user, freestyle_id)
    fs.stopped_at = utcnow()  # when it was last stopped
    if fs.project_id:  # the director's run: no more turns
        director.stop(db, db.get(Project, fs.project_id))
    stop_jobs(db, Job.id.in_(list(_jobs(db, fs))))
    db.commit()
    return _out(db, fs)


@router.patch("/{freestyle_id}", response_model=FreestyleOut)
def rename_freestyle(
    freestyle_id: int,
    body: TitleIn,
    user: User = Depends(current_user),
    db: Session = Depends(_db),
):
    fs = _get(db, user, freestyle_id)
    if fs.created_by_id != user.id and not user.is_owner:
        raise HTTPException(403, "Only whoever made this freestyle can rename it.")
    fs.title = body.title
    db.commit()
    return _out(db, fs)
