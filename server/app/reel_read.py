"""Reading an imported reel (docs/design/reel-import-server.md §3): three paid steps after the
free prep, priced together and pressed once. Watch (Gemini) describes the shots and names the
speakers; the server builds the breakdown from it plus the transcript and cuts it measured;
then the existing Write (script_draft) and Cast read (cast_slots) steps run on it. Each step's
job queues the next with `prepaid`; a failed step stops the chain and a new press retries
from it."""

import json
import logging
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import prompts, script_write
from app import script_cast_read as cast_read
from app.credits import estimate
from app.enhance import escape
from app.models.accounts import User
from app.models.jobs import Job
from app.models.script_library import Script
from app.prompts import check
from app.reference import checked

log = logging.getLogger(__name__)
STEPS = ("watch", "write", "cast")
WATCH_MODEL = "gemini-3.5-flash"
KIND = {"watch": "watch-gemini", "write": "write-claude", "cast": "write-claude"}
NAMES = {"watch": "Finding the shots", "write": "Writing the script", "cast": "Reading the cast"}


def latest(db: Session, job: Job) -> Script | None:
    """The job's script as the database has it now (sessions keep objects across commits,
    and the web side may have moved it on, e.g. a new press)."""
    return db.get(Script, job.input["script_id"], populate_existing=True)


def remaining(script: Script) -> list[str]:
    done = (script.reel or {}).get("done", [])
    return [s for s in STEPS if s not in done]


def price(db: Session, user: User, steps: list[str]) -> Decimal:
    model = {"watch": {"model": WATCH_MODEL}}
    return sum(
        (estimate(db, user.workspace_id, KIND[s], Decimal(1), model.get(s, {})) for s in steps),
        Decimal(0),
    )


def shots(reel: dict) -> list[dict]:
    """The measured shots, [{n, start, end}], from the cut times."""
    edges = [0.0, *reel.get("cuts", []), reel["seconds"]]
    pairs = [(a, b) for a, b in zip(edges, edges[1:], strict=False) if b > a]
    return [{"n": n, "start": a, "end": b} for n, (a, b) in enumerate(pairs, 1)]


def watch_input(script: Script) -> dict:
    reel = script.reel
    said = (
        f"{i}. {x['start']:.2f}–{x['end']:.2f} {x['text']}"
        for i, x in enumerate(reel["transcript"])
    )
    cuts = (f"{s['n']}. {s['start']:.2f}–{s['end']:.2f}" for s in shots(reel))
    prompt = (
        f"<transcript>\n{escape(chr(10).join(said))}\n</transcript>\n"
        f"<cuts>\n{chr(10).join(cuts)}\n</cuts>"
    )
    return {
        "step": "reel_watch",
        "script_id": script.id,
        "model": WATCH_MODEL,
        "input": {"prompt": prompt, "system_instruction": prompts.system("reel_watch")},
        "files": {"images": [reel["contact_file_id"]]},
        "uploads": {"videos": [reel["video_file_id"]]},
    }


def _job_input(db: Session, script: Script, step: str) -> dict:
    if step == "watch":
        data = watch_input(script)
    elif step == "write":
        data = script_write.job_input(db, script, script.reference_breakdown)
    else:
        versions = {0: script_write.original(db, script).text}
        data = cast_read.job_input(db, script, script.reference_breakdown, versions)
    return {**data, "reel_step": step}


def queue(db: Session, user: User, script: Script, step: str, prepaid: bool = False) -> Job:
    """Queue one step and point the script at it (the import's latest job)."""
    from app.routes.jobs import enqueue

    provider = "replicate" if step == "watch" else "claude"
    data = _job_input(db, script, step)
    job = enqueue(db, user, KIND[step], data, provider=provider, prepaid=prepaid)
    script.reel = {k: v for k, v in script.reel.items() if k != "failed_step"}
    script.reel_job_id = job.id
    db.commit()
    return job


def _parse(text: str) -> dict:
    """Gemini answers in text; take the JSON object out of it (fenced or not)."""
    found = re.search(r"\{.*\}", text or "", re.S)
    if not found:
        raise ValueError("The watch answer has no JSON.")
    return json.loads(found.group(0))


def breakdown(watch: dict, reel: dict) -> dict:
    """The reel's breakdown (BREAKDOWN.json shape) from what Gemini saw and what we measured:
    lines and their times come from the transcript, each in the shot that holds its start;
    a live-action shot is marked so `reference_block` drops it."""
    speakers = {s["line"]: s["speaker"] for s in watch.get("speakers", [])}
    held: dict[int, list[tuple[str, str]]] = {}
    for i, line in enumerate(reel["transcript"]):
        shot = next((s for s in watch["shots"] if s["start"] <= line["start"] < s["end"]), None)
        shot = shot or watch["shots"][-1]
        held.setdefault(shot["n"], []).append((speakers.get(i) or "unknown", line["text"]))
    out = []
    for s in watch["shots"]:
        lines = held.get(s["n"], [])
        who = list(dict.fromkeys(name for name, _ in lines))
        out.append(
            {
                **{
                    k: s[k] for k in ("n", "start", "end", "framing", "camera", "action", "emotion")
                },
                "on_screen": s.get("on_screen", ""),
                "speaker": " / ".join(who) or None,
                "line": " / ".join(text for _, text in lines) or None,
                "style": "live action" if s.get("live_action") else watch.get("style", ""),
            }
        )
    return checked(
        {
            "logline": watch["logline"],
            "duration_seconds": reel["seconds"],
            "hook": watch["hook"],
            "beats": watch["beats"],
            "shots": out,
        }
    )


def save_watch(db: Session, job: Job) -> None:
    """Gemini's answer, checked, becomes the script's own reel breakdown. A shot list that
    doesn't match the cuts fails the step (the press is retried from here)."""
    script = latest(db, job)
    if script is None or script.reel_job_id != job.id:
        return
    watch = (
        prompts.SCHEMAS["reel_watch"].model_validate(_parse(job.output.get("text"))).model_dump()
    )
    reel = script.reel
    fixes = [
        p
        for p in check.reel_watch(watch, shots(reel), reel["transcript"])
        if not p.startswith(check.ADVICE)
    ]
    if fixes:
        raise ValueError(f"The watch answer doesn't fit the cuts: {fixes[0]}")
    script.reference_breakdown = breakdown(watch, reel)
    if not script.description:
        script.description = watch["logline"]


def follow_on(db: Session, job: Job, saved: bool) -> None:
    """After a chain step's job succeeds: mark it done and queue the next, already paid for.
    If saving its answer failed, the chain stops at this step."""
    script = latest(db, job)
    if script is None or script.reel_job_id != job.id:
        return
    step = job.input["reel_step"]
    if not saved:
        script.reel = {**script.reel, "failed_step": step}
        return
    script.reel = {**script.reel, "done": [*script.reel.get("done", []), step]}
    if left := remaining(script):
        try:
            queue(db, db.get(User, job.created_by_id), script, left[0], prepaid=True)
        except HTTPException as exc:  # e.g. a cap reached meanwhile: stop here, say why
            log.warning("job %s: couldn't queue the reel's %s step: %s", job.id, left[0], exc)
            script.reel = {**script.reel, "failed_step": left[0]}
