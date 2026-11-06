"""The ask cards (v6 piece B) and Needs you (S9-01): what the screens read and press. Every
card's words and prices come from here, in the viewer's money: the owner sees dollars, an
editor credits (rule 4). An answer in Needs you is the same answer as in the chat."""

import math
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ask_options, asks, director, hidden
from app.auth import current_user
from app.credits import USD_PER_CREDIT, budget, budget_used, price
from app.db import get_db
from app.models.accounts import User
from app.models.asks import Ask
from app.models.brands import Brand
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.routes.clips import generation_on
from app.routes.projects import _mine, get_project
from app.schemas import UtcTime

router = APIRouter(tags=["asks"])


class SavedOption(BaseModel):
    id: str  # "item:12", "screen:4", "voice:Roger": what an answer's `option` names
    name: str
    note: str = ""  # "product", "still", "fomo screen", "Relaxed, male"
    file_id: int | None = None  # its picture
    used_in: int = 0  # "used in 3 videos"
    sample_file_id: int | None = None  # a voice's own sample recording, to play
    sample_url: str | None = None  # an app or style voice's free sample (GET, under /api)


class StoryChoice(BaseModel):
    key: str  # "A"
    title: str
    why: str


class MadeOption(BaseModel):
    index: int  # "Option 1" is 0
    state: str  # the job's: queued, running, succeeded, failed, cancelled, needs_owner_approval
    file_id: int | None  # once drawn


class AskPrice(BaseModel):
    credits: float
    usd: float | None = None  # the owner only


class HeldClip(BaseModel):
    clip: str  # "9"
    still_file_id: int | None


class MoneyCard(BaseModel):
    """A money card's figures: what the OK lets it charge ("up to"), what's spent and the
    budget (past the budget), the run's usual cost (start), the held items and when sent."""

    up_to: AskPrice
    spent: AskPrice | None = None
    budget: AskPrice | None = None
    past: AskPrice | None = None  # how far past the budget it goes
    usual: AskPrice | None = None  # the start card's "Usually it's nearer …"
    clips: list[HeldClip] = []
    sent_at: UtcTime
    held: str  # the hold's own words
    what: str = ""  # past the budget: what it makes, "Redo clips 9 and 12" (Needs you's title)


class AskOut(BaseModel):
    id: int
    project_id: int
    kind: str  # asks.QUESTIONS or asks.MONEY
    topic: str
    question: str  # the card's title, in the viewer's money for a money card
    why: str
    state: str  # open, uploading, generating, ready, failed, held, answered, not_needed
    by_owner: bool = False  # the owner answered on someone else's video ("Answered by the owner")
    saved_in: str = ""  # "Saved in Resilia"
    saved: list[SavedOption] = []
    pick: str | None = None  # the director's pick: a saved id or a choice key
    choices: list[StoryChoice] = []
    decide_at: UtcTime | None = None  # a story choice: "I'll go with A at 11:00"
    generate: AskPrice | None = None  # a round of Generate options, "up to"; null: no Generate
    clone: AskPrice | None = None  # a voice card's "Clone it once · up to $X" (#1314's price)
    clone_to: str = (
        ""  # where the clone is saved, said before the press: "Saved to Resilia's voices"
    )
    options: list[MadeOption] = []
    options_spent: AskPrice | None = None  # "$0.18 spent"
    answer: dict | None = None  # {how, option, name, file_id, text, choice, reused}
    answered_by: str = ""  # a name; "" for the director's own pick or a saved item reused
    answered_at: UtcTime | None = None
    closed: str = ""  # no longer needed: why
    money: MoneyCard | None = None
    can: list[str] = []  # what this viewer may press: answer `how`s, plus generate and cancel
    created_at: UtcTime


class AnswerIn(BaseModel):
    how: str  # saved, upload, reply, option, choice, clone; make_it, approve, keep, decline,
    # withdraw (clone: `file_id` an audio sample, `text` the voice's name)
    option: str | int | None = None  # a saved id, or a generated option's index
    file_id: int | None = None  # upload: POST /files first
    text: str | None = Field(default=None, max_length=2000)  # reply
    choice: str | None = None


class GenerateIn(BaseModel):
    like: int | None = None  # More like this option
    change: str | None = Field(default=None, max_length=500)  # Change something…


class UploadingIn(BaseModel):
    on: bool


def _price(user: User, credits: Decimal) -> AskPrice:
    usd = math.ceil(credits * USD_PER_CREDIT * 100) / 100 if user.is_owner else None
    return AskPrice(credits=price(credits) if credits else 0, usd=usd)


def _said(p: AskPrice) -> str:
    return f"${p.usd:.2f}" if p.usd is not None else f"{int(p.credits)} credits"


def out(db: Session, user: User, ask: Ask) -> AskOut:
    project = db.get(Project, ask.project_id)
    state = asks.sync(db, ask)
    by = db.get(User, ask.answered_by_id) if ask.answered_by_id else None
    card = AskOut(id=ask.id, project_id=ask.project_id, kind=ask.kind, topic=ask.topic,
                  question=ask.question, why=ask.why, state=state,
                  by_owner=bool(by and by.is_owner and by.id != project.created_by_id),
                  pick=ask.pick, choices=[StoryChoice(**c) for c in ask.choices],
                  decide_at=ask.decide_at if state in asks.OPEN else None,
                  answer=ask.answer, answered_by=by.name if by else "",
                  answered_at=ask.answered_at, closed=ask.closed,
                  created_at=ask.created_at)  # fmt: skip
    mine = user.is_owner or project.created_by_id == user.id
    if ask.kind in asks.MONEY:
        return _money(db, user, ask, project, card)
    if ask.kind not in ("story", "question"):
        card.saved_in = f"Saved in {db.get(Brand, project.brand_id).name}"
        card.saved = [SavedOption(**o) for o in ask_options.saved(db, project, ask.kind)]
    if ask.kind in ask_options.GENERATES:
        card.generate = _price(user, ask_options.generate_price(db, ask))
        card.options = [MadeOption(index=o["index"], state=o["state"], file_id=o["file_id"])
                        for o in ask_options.options(db, ask)]  # fmt: skip
        card.options_spent = _price(user, ask_options.spent(db, ask))
    if ask.kind == "voice":
        from app import voices

        card.clone = _price(user, voices.clone_credits(db, project.workspace_id))
        card.clone_to = f"Saved to {db.get(Brand, project.brand_id).name}'s voices"
    if mine and state != "not_needed":
        card.can = ["reply"] + (["saved"] if card.saved else [])
        card.can += ["upload"] if ask.kind in asks.UPLOADS else []
        card.can += ["choice"] if ask.kind == "story" else []
        card.can += ["clone"] if ask.kind == "voice" else []
        makes = ask.kind in ask_options.GENERATES and state != "answered"
        card.can += ["generate"] if makes else []
        card.can += ["option"] if card.options else []
        card.can += ["cancel"] if state in ("generating", "held") else []
    return card


def _money(db: Session, user: User, ask: Ask, project: Project, card: AskOut) -> AskOut:
    """A money card's words, as S4-02, S3-02, S3-06 and S3-07 draw them."""
    from app.routes.jobs import HELD, _with_check

    jobs = list(db.scalars(select(Job).where(Job.id.in_(ask.job_ids or [0])).order_by(Job.id)))
    held = [j for j in jobs if j.status == JobStatus.needs_owner_approval] or jobs
    more = sum((_with_check(db, j) for j in held), Decimal(0))
    sent = held[0].created_at if held else ask.created_at
    words = held[0].input.get(HELD, "") if held else ""
    money = MoneyCard(up_to=_price(user, more), sent_at=sent, held=words)
    owner = user.is_owner
    if ask.kind == "start":
        top = Decimal(held[0].input.get("price") or 0) if held else asks.run_price(db, project)
        money.up_to, money.usual = _price(user, top), _price(user, _usual(db, project))
        card.question = f"Make it for up to {_said(money.up_to)}?"
        card.why = ("That's the most this run can charge: the first takes and their checks, up "
                    f"to {director.MAX_REDOS} remakes a clip, and my own time. Usually it's "
                    f"nearer {_said(money.usual)}.")  # fmt: skip
        may = asks.may_start(db, user, project)
        card.can = ["make_it"] if may else []
        card.can += ["decline"] if owner and project.created_by_id != user.id else []
    elif ask.kind == "plan":  # planning before Make it past its allowance (Reed, 4 Nov)
        from app.settings import get_settings

        settings = get_settings()
        cap = _price(user, Decimal(str(settings.plan_credits_before_ok)))
        card.question = f"Change the plan again for up to {_said(money.up_to)}?"
        card.why = (f"Planning before Make it has used its allowance: a plan and "
                    f"{settings.plans_before_ok - 1} changes, or {_said(cap)}. Nothing more is "
                    "planned until the owner says yes.")  # fmt: skip
        card.can = ["approve", "keep"] if owner else []
    elif ask.kind == "own":
        limit = _price(user, director.own_limit())
        card.question = f"Keep going for up to {_said(money.up_to)} more of my own time?"
        card.why = (f"I've used my own limit of {_said(limit)} on this run. Your OK gives me "
                    f"up to {_said(limit)} more; nothing is charged while it waits.")  # fmt: skip
        card.can = ["approve", "keep"] if owner else []
    else:
        spent = budget_used(db, project)
        top = budget(db, project) if project.hidden else project.budget_credits
        run = asks.approved_run(db, project)
        if run and any(j.input.get(asks.PAST_PRICE) for j in held):  # past its Make it's price
            top, spent = run  # the price approved is this run's budget (S3-06)
        money.spent, money.budget = _price(user, spent), _price(user, top)
        money.past = _price(user, max(Decimal(0), spent + more - top))
        money.clips, money.what = _clips(db, project, held), _what(db, held)
        card.question = f"{money.what}? That goes {_said(money.past)} past the budget."
        notes = " ".join(dict.fromkeys(j.input["note"] for j in held
                                       if isinstance(j.input.get("note"), str)))  # fmt: skip
        if owner:  # the total is the sum of the figures shown, each rounded up
            total = AskPrice(credits=money.spent.credits + money.up_to.credits,
                             usd=round(money.spent.usd + money.up_to.usd, 2))  # fmt: skip
            card.why = (f"{notes} {_said(money.spent)} spent plus up to {_said(money.up_to)} "
                        f"makes up to {_said(total)}; the budget is {_said(money.budget)}."
                        ).strip()  # fmt: skip
        else:
            card.why = f"{notes} The owner has been asked; nothing is charged while it waits."
            card.why = card.why.strip()
        card.can = ["approve", "keep"] if owner else []
    mine = any(j.created_by_id == user.id for j in held)
    if card.state == "open" and not owner and mine and "make_it" not in card.can:
        card.can += ["withdraw"]  # "Waiting for the owner's OK · Withdraw the request"
    if card.state != "open":
        card.can = []
    card.money = money
    return card


def _usual(db: Session, project: Project) -> Decimal:
    from app.models.script_library import ScriptDraft
    from app.routes.estimate import version_cost

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    return version_cost(db, draft, project) if draft else Decimal(0)


def _what(db: Session, jobs: list[Job]) -> str:
    """What the held jobs make, as the card names it: "Redo clips 9 and 12", "Make a still"."""
    from app.needs_you import NAMES

    own = {director.STEP: "Keep the director working", "treatment": "Change the plan",
           "watch_cut": "Watch the cut", "review_stills": "Look at the stills"}  # fmt: skip
    clips, redo, other = [], False, []
    for j in jobs:
        row = db.get(ProjectClip, j.input.get("project_clip_id") or 0)
        if j.input.get("step") in own and row is None:
            other.append(own[j.input["step"]])
        elif row is not None:
            clips.append(row.clip_id.removeprefix("c"))
            redo = redo or row.picked_take_id is not None
        else:
            other.append((NAMES.get(j.input.get("step", "")) or "A step").lower())  # "a still"
    parts = []
    if clips:
        named = clips[0] if len(clips) == 1 else f"{', '.join(clips[:-1])} and {clips[-1]}"
        parts.append(f"{'Redo' if redo else 'Make'} clip{'s' if len(clips) > 1 else ''} {named}")
    for words in dict.fromkeys(other):  # "Make a still", "Keep the director working"
        said = words if words[0].isupper() else f"Make {words}"
        parts.append(said if not parts else said[0].lower() + said[1:])
    return " and ".join(parts)


def _clips(db: Session, project: Project, jobs: list[Job]) -> list[HeldClip]:
    out = []
    for j in jobs:
        row = db.get(ProjectClip, j.input.get("project_clip_id") or 0)
        if row is not None:
            still = db.scalar(select(StoryboardFrame.file_id).where(
                StoryboardFrame.project_id == project.id, StoryboardFrame.clip_id == row.clip_id,
                StoryboardFrame.file_id.is_not(None))
                .order_by(StoryboardFrame.id.desc()))  # fmt: skip
            out.append(HeldClip(clip=row.clip_id.removeprefix("c"), still_file_id=still))
    return out


def _ask(db: Session, user: User, ask_id: int) -> Ask:
    hidden.see(db)  # an editor's send held for the owner is on its hidden video
    ask = db.get(Ask, ask_id)
    if ask is None or ask.workspace_id != user.workspace_id:
        raise HTTPException(404, "No such question.")
    project = db.get(Project, ask.project_id)
    if project.hidden and not (user.is_owner or project.created_by_id == user.id):
        raise HTTPException(404, "No such question.")
    return ask


@router.get("/projects/{project_id}/asks", response_model=list[AskOut])
def list_asks(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Every card on the video, oldest first: open ones, and answered ones folded. A send's
    video before the OK (hidden) shows to its maker and the owner, as its answer route does."""
    hidden.see(db)
    project = get_project(db, user, project_id)
    if project.hidden and not (user.is_owner or project.created_by_id == user.id):
        raise HTTPException(404, "No such project.")
    rows = db.scalars(select(Ask).where(Ask.project_id == project.id).order_by(Ask.id)).all()
    cards = [out(db, user, a) for a in rows]
    db.commit()  # a money card answered through the job routes keeps its state
    return cards


@router.post("/asks/{ask_id}/answer", response_model=AskOut)
def answer(ask_id: int, body: AnswerIn, request: Request, user: User = Depends(current_user),
           db: Session = Depends(get_db)):  # fmt: skip
    """Answer a card (the chat's and Needs you's are the same answer). Questions: the video's
    maker or the owner. MoneyCard: the owner approves or keeps it as it is; an editor's own video
    inside its budget starts with Make it; whoever asked may withdraw."""
    ask = _ask(db, user, ask_id)
    if ask.kind in asks.QUESTIONS:
        _mine(db, user, ask.project_id)
    asks.answer(db, user, ask, body.model_dump(), request.app.state.storage)
    return out(db, user, db.get(Ask, ask_id))


@router.post("/asks/{ask_id}/generate", response_model=AskOut,
             dependencies=[Depends(generation_on)])  # fmt: skip
def generate(ask_id: int, body: GenerateIn, user: User = Depends(current_user),
             db: Session = Depends(get_db)):  # fmt: skip
    """Generate options (paid, at the card's "up to" price): 3 made for this video only, never
    saved to the brand. `like`: more like that option; `change`: Change something…"""
    ask = _ask(db, user, ask_id)
    _mine(db, user, ask.project_id)
    ask_options.generate(db, user, ask, body.like, body.change or "")
    return out(db, user, db.get(Ask, ask_id))


@router.post("/asks/{ask_id}/cancel", response_model=AskOut)
def cancel(ask_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cancel the options being made (or held for the owner): nothing more is charged."""
    ask = _ask(db, user, ask_id)
    _mine(db, user, ask.project_id)
    ask_options.stop_options(db, ask, drop=True)
    db.commit()
    return out(db, user, db.get(Ask, ask_id))


@router.post("/asks/{ask_id}/uploading", response_model=AskOut)
def uploading(ask_id: int, body: UploadingIn, user: User = Depends(current_user),
              db: Session = Depends(get_db)):  # fmt: skip
    """The card shows the upload going up (`on`), or open again if it's cancelled. The file
    itself goes up through POST /files, then POST …/answer with how=upload."""
    ask = _ask(db, user, ask_id)
    _mine(db, user, ask.project_id)
    asks.uploading(db, ask, body.on)
    return out(db, user, ask)
