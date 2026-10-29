"""The music bed under a narration (flows N1, V6n): once the narration is timed, the
Director's narration_music step writes a prompt from the brand and the script (one Claude
call, with one free rewrite for a name, vocals or the wrong length, as the directions do),
then Stable Audio 2.5 on Replicate makes one instrumental the narration's length. Both were
priced in the Make the narration press. If either fails the narration is kept, and the take
says what was charged: nothing if the prompt failed (Try again writes it and makes the
music), the prompt's credits if only the music failed (Try again makes only the music).
Real runs only with BS_NARRATION_MUSIC_PAID, within its budget; the stand-ins always run.
Off, a narration has no music and its price leaves it out."""

import logging
import math

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.credits import estimate
from app.credits import price as shown
from app.enhance import project_context
from app.models.accounts import User
from app.models.jobs import WAITING, Job, JobStatus
from app.models.script_library import Script, ScriptDraft
from app.models.songs import SongTake
from app.prompts import check
from app.prompts.schemas import NarrationMusic
from app.settings import get_settings

log = logging.getLogger(__name__)

STEP, BED = "narration_music", "narration_bed"
MODEL = "stable-audio-2.5"
LONGEST = 190  # seconds the model makes at most; a longer narration loops its bed in the mix
FAILED = "The music didn't finish. Nothing was charged for it."
BED_FAILED = ("The music didn't finish. Writing its prompt cost {}; the music itself wasn't "
              "charged. Try the music again makes only the music.")  # fmt: skip
OFF = "Music under a narration isn't switched on here."
MAKING = "The music is still being made. Make the video when it's ready."
NOT_FAILED = "The music isn't failed, so there's nothing to try again."
STILL = "still needs fixing: "  # the raw reason when the one rewrite didn't fix it


def bed_job(prompt: str, seconds: float) -> dict:
    return {"model": MODEL, "input": {"prompt": prompt,
                                      "duration": min(LONGEST, math.ceil(seconds))}}  # fmt: skip


def on(db: Session) -> bool:
    """Free on the stand-ins; for real only when switched on, and within its budget."""
    settings = get_settings()
    if settings.fake_providers:
        return True
    if not settings.narration_music_paid:
        return False
    # Each music file sent counts (a retry too), and each prompt still on its way to one
    rows = db.scalars(select(Job).where(Job.input["step"].as_string().in_((STEP, BED))))
    runs = sum(1 for j in rows if _counts(j))
    if (runs + 1) * settings.narration_music_usd_per_run > settings.narration_music_budget_usd:
        log.warning("Music under narrations stopped at the test budget after %s runs.", runs)
        return False
    return True


def _counts(job: Job) -> bool:
    if job.input["step"] == BED:  # sent: paid whatever happens after
        return job.status != JobStatus.cancelled or job.provider_ref is not None
    return job.status in WAITING


def _bed_price(db: Session, ws: int) -> float:
    return estimate(db, ws, "music_bed", 1, bed_job("", 1))


def price(db: Session, ws: int) -> float:
    """The prompt (one Claude call) and the bed (one file); nothing while it's off."""
    if not on(db):
        return 0
    return estimate(db, ws, "write-claude", 1) + _bed_price(db, ws)


def start(db: Session, take: SongTake, user: User, prepaid: bool = True, hold=0) -> None:
    """Write the music prompt (paid: priced in the press, or Try the music again's own
    price, checked with the bed as `hold`), then make the bed. Off: no music."""
    from app.routes.jobs import enqueue
    from app.script_preview import stand_in_project

    if not on(db):
        return

    draft = db.get(ScriptDraft, take.draft_id)
    script = db.get(Script, draft.script_id)
    system, _ = project_context(db, stand_in_project(db, script, draft), STEP)
    message = prompts.narration_music_input(check.narration_text(take.lyrics), take.seconds)
    job = enqueue(db, user, "write-claude", {"step": STEP, "take_id": take.id,
                                             "system": system, "prompt": message},
                  units=1, provider="claude", prepaid=prepaid, hold=hold)  # fmt: skip
    take.music_job_id, take.music_file_id = job.id, None
    db.commit()


def checked(output: dict) -> tuple[dict, list[str]]:
    """An answer and its fixes (the Director's check), for steps.recheck."""
    result = NarrationMusic.model_validate(output)
    return result.model_dump(), check.narration_music(result)


def again(job_input: dict, fixes: list[str]) -> dict:
    said = "\n".join(f"- {f}" for f in fixes)
    fix = f"<fix>\nYour last answer can't be used:\n{said}\nWrite the music prompt again.\n</fix>"
    return {**job_input, "prompt": f"{job_input['prompt']}\n{fix}"}


def save_prompt(db: Session, job: Job) -> None:
    """The prompt is written: make the bed the narration's length."""
    from app.routes.jobs import enqueue

    take = db.get(SongTake, job.input["take_id"])
    if take is None or take.music_job_id != job.id:  # tried again since: this one is old
        return
    prompt = prompts.music_prompt(NarrationMusic.model_validate(job.output))
    user = db.get(User, job.created_by_id)
    bed = enqueue(db, user, "music_bed", {**bed_job(prompt, take.seconds), "step": BED,
                                          "take_id": take.id, "prompt_job_id": job.id},
                  units=1, provider="replicate", prepaid=True)  # fmt: skip
    take.music_job_id = bed.id


def save_bed(db: Session, job: Job) -> None:
    take = db.get(SongTake, job.input["take_id"])
    if take is not None and take.music_job_id == job.id:
        take.music_file_id = job.output["file_ids"][0]


def _failed_bed(db: Session, take: SongTake) -> Job | None:
    """The music's failed bed, when its prompt was written (and charged)."""
    job = db.get(Job, take.music_job_id) if take.music_job_id else None
    if job and job.status == JobStatus.failed and job.input.get("step") == BED:
        return job
    return None


def state(db: Session, take: SongTake) -> tuple[str, str | None]:
    """(none | making | ready | failed, a plain reason)."""
    if take.music_file_id:
        return "ready", None
    job = db.get(Job, take.music_job_id) if take.music_job_id else None
    if job is None:
        return "none", None
    if job.status in WAITING or (job.status == JobStatus.succeeded and job.input["step"] == STEP):
        return "making", None
    if bed := _failed_bed(db, take):
        cost = shown(db.get(Job, bed.input["prompt_job_id"]).credits)
        return "failed", BED_FAILED.format("1 credit" if cost == 1 else f"{cost} credits")
    return "failed", FAILED


def retry_price(db: Session, take: SongTake, ws: int) -> float:
    """Try the music again: only the bed once its prompt was written, else both."""
    return _bed_price(db, ws) if _failed_bed(db, take) else price(db, ws)


def try_again(db: Session, take: SongTake, user: User) -> None:
    from app.routes.jobs import enqueue

    if state(db, take)[0] != "failed":
        raise HTTPException(409, NOT_FAILED)
    if not on(db):
        raise HTTPException(409, OFF)
    if bed := _failed_bed(db, take):  # the saved prompt: the music alone, at its own price
        again = enqueue(db, user, "music_bed", dict(bed.input), units=1, provider="replicate")
        take.music_job_id = again.id
        db.commit()
        return
    start(db, take, user, prepaid=False, hold=_bed_price(db, user.workspace_id))
