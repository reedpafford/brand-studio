"""The music bed under a narration (flows N1, V6n): once the narration is timed, the
Director's narration_music step writes a prompt from the brand and the script (one Claude
call, with one free rewrite for a name, vocals or the wrong length, as the directions do),
then Stable Audio 2.5 on Replicate makes one instrumental the narration's length. Both were
priced in the Make the narration press. If either fails, the narration is kept: "The music
didn't finish. Nothing was charged for it." and Try the music again runs both once more."""

import math

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import prompts
from app.credits import estimate
from app.enhance import project_context
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.models.script_library import Script, ScriptDraft
from app.models.songs import SongTake
from app.prompts import check
from app.prompts.schemas import NarrationMusic

STEP, BED = "narration_music", "narration_bed"
MODEL = "stable-audio-2.5"
LONGEST = 190  # seconds the model makes at most; a longer narration loops its bed in the mix
FAILED = "The music didn't finish. Nothing was charged for it."
MAKING = "The music is still being made. Make the video when it's ready."
NOT_FAILED = "The music isn't failed, so there's nothing to try again."
STILL = "still needs fixing: "  # the raw reason when the one rewrite didn't fix it
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


def bed_job(prompt: str, seconds: float) -> dict:
    return {"model": MODEL, "input": {"prompt": prompt,
                                      "duration": min(LONGEST, math.ceil(seconds))}}  # fmt: skip


def price(db: Session, ws: int) -> float:
    """The prompt (one Claude call) and the bed (one file)."""
    return estimate(db, ws, "write-claude", 1) + estimate(db, ws, "music_bed", 1, bed_job("", 1))


def start(db: Session, take: SongTake, user: User, prepaid: bool = True) -> None:
    """Write the music prompt (paid: priced in the press, or Try the music again's own
    price), then make the bed."""
    from app.routes.jobs import enqueue
    from app.script_preview import stand_in_project

    draft = db.get(ScriptDraft, take.draft_id)
    script = db.get(Script, draft.script_id)
    system, _ = project_context(db, stand_in_project(db, script, draft), STEP)
    message = prompts.narration_music_input(check.narration_text(take.lyrics), take.seconds)
    job = enqueue(db, user, "write-claude", {"step": STEP, "take_id": take.id,
                                             "system": system, "prompt": message},
                  units=1, provider="claude", prepaid=prepaid)  # fmt: skip
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
                                          "take_id": take.id},
                  units=1, provider="replicate", prepaid=True)  # fmt: skip
    take.music_job_id = bed.id


def save_bed(db: Session, job: Job) -> None:
    take = db.get(SongTake, job.input["take_id"])
    if take is not None and take.music_job_id == job.id:
        take.music_file_id = job.output["file_ids"][0]


def state(db: Session, take: SongTake) -> tuple[str, str | None]:
    """(none | making | ready | failed, a plain reason)."""
    if take.music_file_id:
        return "ready", None
    job = db.get(Job, take.music_job_id) if take.music_job_id else None
    if job is None:
        return "none", None
    if job.status in WAITING or (job.status == JobStatus.succeeded and job.input["step"] == STEP):
        return "making", None
    return "failed", FAILED


def try_again(db: Session, take: SongTake, user: User) -> None:
    if state(db, take)[0] != "failed":
        raise HTTPException(409, NOT_FAILED)
    start(db, take, user, prepaid=False)
