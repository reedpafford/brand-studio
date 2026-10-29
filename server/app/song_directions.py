"""Song directions (song ads, flows S3): "Write 2 song directions". One paid Claude call per
press writes 2 directions (concept, lyrics, style line, visual concept) for a Song version,
from its About, an optional script or voice-over to adapt (`source`) and an optional "sounds
like". They're kept on the version (newest pair first); Use puts one's lyrics and style line
into the version (Undo puts the old ones back), and its claims wait to be checked.

Each direction in ScriptDraft.song_directions: {id, title, concept, lyrics, style_line,
visual_concept, left_out, unchecked_claims, recommended, length_note, style_names, advice,
made_at}, plus `used` (Use was pressed), `claims_kept` (the owner vouched) and `removed_at`."""

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.db import utcnow
from app.enhance import escape, project_context
from app.models.jobs import Job, JobStatus
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft
from app.prompts import check
from app.prompts.schemas import SongDirections
from app.script_preview import stand_in_project

STEP = "song_directions"
NOTHING = "Add what the brand sells on the brand page, or paste a script to adapt."
APPROVED = "These lyrics are approved, so a direction can't be used here. Duplicate it to try one."


def stop(db: Session, script: Script, draft: ScriptDraft, source: str = "") -> str | None:
    """Why a press can't run, in plain words (None: it can): an approved version can't take
    a direction, and with nothing at all to go on (no About, script, lyrics, brand notes or
    product) there's nothing to write from."""
    from app.models.brands import Brand
    from app.models.library import Kind

    if draft.status == "approved":
        return APPROVED
    brand = db.get(Brand, script.brand_id)
    products = [i for i in brand_items(db, brand) if i.kind == Kind.prop]
    has = (script.description.strip() or source.strip() or draft.text.strip()
           or brand.tone_notes.strip() or products)  # fmt: skip
    return None if has else NOTHING


def brand_items(db: Session, brand) -> list:
    from app.models.library import LibraryItem, item_brands

    return list(db.scalars(select(LibraryItem).join(item_brands)
                           .where(item_brands.c.brand_id == brand.id,
                                  LibraryItem.archived.is_(False))))  # fmt: skip


def job_input(
    db: Session, script: Script, draft: ScriptDraft, source: str, sounds_like: str, note: str
) -> dict:
    project = stand_in_project(db, script, draft)
    system, _ = project_context(db, project, STEP)
    slots = db.scalars(select(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id)
                       .order_by(ScriptCastSlot.position))  # fmt: skip
    cast = [escape(f"{s.role}: {s.description}".strip(": ")) for s in slots]
    brief = escape(f"{script.title}\n{script.description}".strip())
    message = prompts.song_directions_input(
        brief, cast, seconds=draft.target_seconds, note=escape(note),
        source=escape(source), sounds_like=escape(sounds_like),
    )  # fmt: skip
    return {"step": STEP, "script_id": script.id, "slot": draft.slot, "system": system,
            "prompt": message, "sounds_like": sounds_like}  # fmt: skip


def save(db: Session, job: Job) -> None:
    """The pair lands first on the version; older pairs stay below it."""
    script = db.get(Script, job.input["script_id"])
    draft = db.scalar(select(ScriptDraft).where(ScriptDraft.script_id == script.id,
                                                ScriptDraft.slot == job.input["slot"]))  # fmt: skip
    if draft is None or script.published:
        return
    result = SongDirections.model_validate(job.output)
    brand = script_brand(db, script)
    advice = check.song_directions(result, brand, draft.target_seconds,
                                   sounds_like=job.input.get("sounds_like", ""))  # fmt: skip
    pair = []
    for n, d in enumerate(result.directions, 1):
        names = [a for a in advice if a.startswith(f"direction {n}")]
        pair.append({
            **d.model_dump(), "id": uuid.uuid4().hex[:12], "recommended": n == result.recommended,
            "length_note": check.length_note(d.lyrics), "advice": names,
            "style_names": _names(d.style_line, job.input.get("sounds_like", "")),
            "made_at": utcnow().isoformat(), "job_id": job.id,
        })  # fmt: skip
    draft.song_directions = [*pair, *(draft.song_directions or [])]


def script_brand(db: Session, script: Script) -> str:
    from app.models.brands import Brand

    return db.get(Brand, script.brand_id).name


def _names(style_line: str, sounds_like: str) -> list[str]:
    """Names from the "sounds like" the style line still carries (Suno refuses names)."""
    found = [n for n in check.NAME.findall(sounds_like) if len(n) > 2]
    return [n for n in found if n.lower() in style_line.lower()]


def latest_job(db: Session, script: Script, draft: ScriptDraft) -> Job | None:
    jobs = db.scalars(select(Job).where(Job.kind == "write-claude").order_by(Job.id.desc()))
    return next((j for j in jobs if j.input.get("step") == STEP
                 and j.input.get("script_id") == script.id
                 and j.input.get("slot") == draft.slot), None)  # fmt: skip


def job_state(db: Session, script: Script, draft: ScriptDraft) -> dict | None:
    """The press in hand: {id, status, reason, started_at}; None when idle or done."""
    job = latest_job(db, script, draft)
    if not job or job.status in (JobStatus.succeeded, JobStatus.cancelled):
        return None
    status = job.status if job.status != JobStatus.needs_owner_approval else "queued"
    return {"id": job.id, "status": str(status), "reason": job.error or None,
            "started_at": job.started_at}  # fmt: skip


def shown(draft: ScriptDraft) -> list[dict]:
    return [d for d in draft.song_directions or [] if not d.get("removed_at")]


def _find(draft: ScriptDraft, direction_id: str) -> dict:
    found = next((d for d in draft.song_directions or [] if d["id"] == direction_id), None)
    if found is None:
        raise HTTPException(404, "No such song direction.")
    return found


def use(db: Session, draft: ScriptDraft, direction_id: str) -> tuple[str, str]:
    """Its lyrics and style line go into the version; returns the old ones (Undo)."""
    if draft.status == "approved":
        raise HTTPException(409, "These words are approved and can't change.")
    chosen = _find(draft, direction_id)
    was = (draft.text, draft.style_line)
    draft.text, draft.style_line = chosen["lyrics"], chosen["style_line"]
    draft.song_directions = [{**d, "used": d["id"] == direction_id}
                             for d in draft.song_directions]  # fmt: skip
    db.commit()
    return was


def claims_to_check(draft: ScriptDraft) -> list[str]:
    """The used direction's claims, while the version still sings its lyrics (an Undo, or
    other words, leaves nothing to check) and until the owner keeps them."""
    used = next((d for d in draft.song_directions or [] if d.get("used")), None)
    if not used or used.get("claims_kept") or draft.text.strip() != used["lyrics"].strip():
        return []
    return used.get("unchecked_claims", [])


def keep_claims(db: Session, draft: ScriptDraft) -> None:
    draft.song_directions = [{**d, "claims_kept": True} if d.get("used") else d
                             for d in draft.song_directions or []]  # fmt: skip
    db.commit()


def remove(db: Session, draft: ScriptDraft, direction_id: str, back: bool = False) -> None:
    _find(draft, direction_id)
    stamp = None if back else utcnow().isoformat()
    draft.song_directions = [{**d, "removed_at": stamp} if d["id"] == direction_id else d
                             for d in draft.song_directions]  # fmt: skip
    db.commit()
