"""The voice audition (Reed, 9 Nov, after the UGC listening test: "maybe it is just a matter of
finding the voice before generating on HeyGen? Let's implement a voice discovery stage").

A presenter speaks in one of our voices (a UGC talker, or a host in a corner). Until that
voice is chosen, the director names 3 or 4 that fit them (age, gender, energy, an ordinary
speaking pitch, not a narrator's) on the card that casts them, in the same move (`ask` with
`voices`). Each reads the opening of what the narration will say, about 8 s, as it will say
it (`line`): a cheap voice call each (narration.job; MiniMax and ElevenLabs are $0.10 per
1,000 characters). The person plays them and picks one. The pick is the video's voice
(`projects.voice`), and it's saved on the presenter, so the next video with them reuses it
with no audition (voices.default_for).

Nothing pricier waits on a guess: while a presenter's voice isn't chosen, the narration (the
clock everything follows), the looks, stills, takes and the host are refused (`HELD`). A
revision keeps the voice: it's the video's own by then."""

import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import narration, voices
from app.models.accounts import User
from app.models.asks import Ask
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project

STEP, ASK = "voice_sample", "ask_id"  # a sample's job, and its card
FEWEST, MOST = 3, 4  # the director's candidates
SECONDS, PACE = 8.0, 3.3  # the opening read: about 8 s at a talker's words a second
HELD = ("narration", "make_looks", "storyboard", "stills", "make_take", "host", "redraw_still")
TOO_FEW = (f"Refused: name {FEWEST} or {MOST} different voices from "
           f"{', '.join(narration.VOICES)} for the audition.")  # fmt: skip
ASK_FIRST = ("Refused: {who}'s voice isn't chosen yet, and everything is timed to it. On the card "
             "that asks who plays {who} (or a voice card about them, when they're cast), name "
             f"{FEWEST} or {MOST} `voices` that fit them: their age, gender and energy, and an "
             "ordinary speaking pitch, not a narrator's. Each reads the script's opening; the "
             "person picks one.")  # fmt: skip
WAITS = ("Refused: {who}'s voice is being auditioned on question {ask}. Nothing that costs more "
         "starts until the person picks one; keep doing what's free, or `wait`.")  # fmt: skip
NOT_ONE = "Pick one of the voices that read for this card."
NOT_MADE = "That voice hasn't read yet. Play it once it's ready."


def needed(db: Session, project: Project) -> bool:
    """A presenter speaks in one of our voices and nobody has chosen it: no pick for this
    video, none saved on the presenter, no style voice (Dr. Pickle's clone), and no narration
    made yet (one made before the audition keeps its voice)."""
    from app import host

    return (not project.song_take_id and host.presents(db, project)
            and not (voices.picked(db, project) or voices.default_for(db, project)))  # fmt: skip


def who(db: Session, project: Project) -> str:
    """The presenter as the script names them: the look that says the narration, else the
    script's first speaker, else "the presenter"."""
    from app import host
    from app.models.script_library import ScriptDraft
    from app.prompts.check import LABEL

    item = host.host_look(db, project)
    if item is not None:
        return item.name
    draft = db.get(ScriptDraft, project.script_draft_id or 0)
    said = next((m[1] for x in (draft.text if draft else "").splitlines()
                 if (m := LABEL.match(x.strip()))), "")  # fmt: skip
    return said.title() if said.isupper() else said or "the presenter"


def line(db: Session, project: Project) -> str:
    """What every candidate reads: the opening of exactly what the narration will say
    (song_takes.words: the approved words, a UGC talker's spoken version once approved),
    whole sentences to about SECONDS (the first one however long). A UGC talker's are run
    together as they'd say them, a comma for each full stop between them (the listening test,
    9 Nov: that reading is half of why Reed preferred Trustworthy Man)."""
    from app import song_takes, talker
    from app.models.script_library import ScriptDraft
    from app.prompts import check

    draft = db.get(ScriptDraft, project.script_draft_id or 0)
    said = song_takes.words(db, draft, project) if draft else ""
    most, out = round(SECONDS * PACE), []
    for sentence in narration.sentences(check.narration_text(said)):
        if out and len(" ".join(out).split()) + len(sentence.split()) > most:
            break
        out.append(sentence)
    if talker.minimax(db, project):
        out = [re.sub(r"\.$", ",", s) for s in out[:-1]] + out[-1:]
    return " ".join(out)


def jobs(db: Session, ask: Ask) -> list[Job]:
    return list(db.scalars(select(Job).where(
        Job.project_id == ask.project_id, Job.input["step"].as_string() == STEP,
        Job.input[ASK].as_integer() == ask.id).order_by(Job.id)))  # fmt: skip


def card(db: Session, project: Project) -> Ask | None:
    """The video's newest card with an audition that's still needed."""
    ids = db.scalars(select(Job.input[ASK].as_integer()).where(
        Job.project_id == project.id, Job.input["step"].as_string() == STEP))  # fmt: skip
    return db.scalar(select(Ask).where(Ask.id.in_(set(ids) or {0}), Ask.state != "not_needed")
                     .order_by(Ask.id.desc()).limit(1))  # fmt: skip


def checked(keys) -> list[str] | None:
    """The director's candidates, each once, when they're FEWEST to MOST app voices."""
    keys = list(dict.fromkeys(str(k) for k in keys or []))
    ok = FEWEST <= len(keys) <= MOST and all(k in narration.VOICES for k in keys)
    return keys if ok else None


def start(db: Session, user: User, project: Project, ask: Ask, keys, before: bool) -> str:
    """The director's candidates read the opening, one voice call each, priced like the
    narration. Before Make it they count on the video's planning allowance, as the treatment
    does. What happened, in plain words for its log ("" when no audition is needed)."""
    from app import asks
    from app.credits import estimate
    from app.routes.jobs import enqueue

    if not needed(db, project):
        return ""
    keys = checked(keys)
    if keys is None:
        raise HTTPException(422, TOO_FEW)
    said = line(db, project)
    for key in keys:
        data = {**narration.job(said, key), "step": STEP, ASK: ask.id, "voice": key}
        units = Decimal(len(said)) / 1000
        wait = ""
        if before:
            data = {**data, asks.BEFORE: True}
            price = estimate(db, project.workspace_id, "speech", units, data)
            wait = asks.PLANNING if asks.past_planning(db, project, price, plan=False) else ""
        enqueue(db, user, "speech", data, project=project, provider="replicate", units=units,
                prepaid=before and not wait, wait=wait)  # fmt: skip
    names = ", ".join(voices.ABOUT[k][0] for k in keys)
    return f" {names} each read the opening for the person to pick from."


def samples(db: Session, ask: Ask) -> list[dict]:
    """The card's candidates, each {id ("stock:<key>"), name, note, sample_file_id, state}."""
    out = []
    for job in jobs(db, ask):
        key = job.input["voice"]
        files = (job.output or {}).get("file_ids") or []
        name, about = voices.ABOUT.get(key, (key, ""))
        out.append({"id": f"{voices.STOCK}{key}", "name": name, "note": about,
                    "sample_file_id": files[0] if files else None, "state": str(job.status),
                    "credits": job.credits})  # fmt: skip
    return out


def pick(db: Session, user: User, ask: Ask, option: str) -> str:
    """The person's pick: this video's voice (logged as theirs, so a revision keeps it), and
    saved on the presenter when they have no voice yet (`keep`). Its name."""
    from app import asks

    made = {s["id"]: s for s in samples(db, ask)}
    if option not in made:
        raise HTTPException(422, NOT_ONE)
    if made[option]["sample_file_id"] is None:
        raise HTTPException(409, NOT_MADE)
    project = db.get(Project, ask.project_id)
    asks._voice(db, user, project, option)
    keep(db, project)
    return made[option]["name"]


def keep(db: Session, project: Project) -> None:
    """The video's picked app voice, saved on its presenter when they have none, so their next
    video skips the audition (Reed: "it might be easier to maintain consistency")."""
    from app import host

    item: LibraryItem | None = host.host_look(db, project) if host.presents(db, project) else None
    key = voices.from_ref(project.voice)
    if item is None or item.voice_id or item.voice_stock_key or key not in narration.VOICES:
        return
    if card(db, project) is not None:  # only a pick from an audition, never a stray setting
        item.voice_stock_key = key


def status(db: Session, project: Project) -> dict | None:
    """What the director reads in its narration: who needs a voice, whether the audition is
    asked (`ask_id`), and the voices to choose from with what each sounds like (its pitch
    where measured); None when the voice is chosen."""
    if not needed(db, project):
        return None
    asked = card(db, project)
    return {
        "who": who(db, project),
        "state": "asked" if asked else "none",
        **(
            {"ask_id": asked.id}
            if asked
            else {"voices": {k: heard(k) for k in voices.stock_keys()}}
        ),
    }


def heard(key: str) -> str:
    """An app voice as the director chooses from it: its name, what it sounds like, and its
    pitch where a test measured it (cards say it in words only)."""
    hz = voices.PITCH.get(key)
    return " · ".join([*voices.ABOUT[key], *([f"about {hz} Hz"] if hz else [])])


def refusal(db: Session, project: Project) -> str:
    """A paid step that would go ahead on a voice nobody chose: refused, saying what to do."""
    said = status(db, project)
    if said is None:
        return ""
    if said["state"] == "asked":
        return WAITS.format(who=said["who"], ask=said["ask_id"])
    return ASK_FIRST.format(who=said["who"])
