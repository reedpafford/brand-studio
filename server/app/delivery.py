"""The delivery note (v6 piece D: boards S3-09, S3-10, S3-12, P-08), built when the director
delivers and kept on its deliver turn, so a later run never rewrites it. The director writes
what it made, what it's unsure of and what it needs (its last turn: DirectorTurn's `made`,
`unsure` and `needs`); the server adds what it watched and redid, each at its time in the
cut (the takes it made again and its free fixes), the run's real cost and the cut's number."""

import math
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.run_progress import RUN, _found, _model, price_of, runs, said, spent, watched

NOTHING = "Nothing. It’s ready to post."
FIXES = ("mute", "splice_word", "pick_take")  # the free fixes its rows name


def note(db: Session, project: Project, job: Job, decision: dict) -> dict:
    """The note for the run `job` delivers: {made, redid [{at, clip, text}], unsure, needs,
    spent, up_to, since, until, cut, seconds, clips}: money as charged, in credits. The real
    dollars are never kept here (any teammate can read a job's output): `shown` reads them
    for the owner from the run's `since` to `until`."""
    turns = runs(db, project)[job.input[RUN]["id"]]
    cut = db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id)
                    .order_by(FinalVideo.id.desc()).limit(1))  # fmt: skip
    number = db.scalar(select(func.count()).where(
        FinalVideo.project_id == project.id, FinalVideo.id <= cut.id)) if cut else 0  # fmt: skip
    spans = _spans(db, cut)
    credits, _ = spent(db, project, turns[0].created_at)
    rows = _remade(db, project, spans, turns) + _fixed(db, project, spans, turns)
    return {"made": said(decision.get("made") or decision.get("why") or ""),
            "redid": sorted(rows, key=lambda r: r["at"]),
            "unsure": said(decision.get("unsure") or ""),
            "needs": said(decision.get("needs") or ""),
            "spent": float(credits), "up_to": float(price_of(db, project)),
            "since": turns[0].created_at.isoformat(), "until": utcnow().isoformat(),
            "cut": number, "clips": len(spans),
            "seconds": round(sum(s["seconds"] for s in spans), 1)}  # fmt: skip


def _spans(db: Session, cut: FinalVideo | None) -> list[dict]:
    """Each clip of the cut in order: {row, take, start, seconds}."""
    takes = {t.id: t for t in db.scalars(select(ClipTake).where(
        ClipTake.id.in_(cut.take_ids)))} if cut else {}  # fmt: skip
    rows = {r.id: r for r in db.scalars(select(ProjectClip).where(
        ProjectClip.id.in_({t.clip_id for t in takes.values()})))}  # fmt: skip
    out, at = [], 0.0
    for take in (takes.get(i) for i in (cut.take_ids if cut else [])):
        row = rows.get(take.clip_id) if take else None
        if row is None:
            continue
        piece = row.song_slice or {}
        seconds = (piece["end"] - piece["start"]) if piece else row.seconds
        out.append({"row": row, "take": take, "start": at, "seconds": seconds})
        at += seconds
    return out


def _clip(row: ProjectClip) -> str:
    return f"Clip {row.clip_id.removeprefix('c')}"


def _remade(db: Session, project: Project, spans: list[dict], turns: list[Job]) -> list[dict]:
    """Each clip in the cut whose take the director made again after its watch found
    something: what it found on the take before, and that it remade it, at that moment."""
    asked = {clip: {"text": why} for clip, why in watched(turns).items()}  # the cut's watch
    from app.clip_takes import video_model

    out = []
    for s in spans:
        take, row = s["take"], s["row"]
        made = db.get(Job, take.job_id)
        if take.number < 2 or not (made and made.input.get("by_director")):
            continue
        earlier = select(ClipTake.id).where(ClipTake.clip_id == row.id,
                                            ClipTake.number < take.number)  # fmt: skip
        checks = db.scalars(select(ItemCheck).where(ItemCheck.target.in_(("take", "words")),
                                                    ItemCheck.target_id.in_(earlier))
                            .order_by(ItemCheck.id.desc()))  # fmt: skip
        found = next((f for c in checks for f in _found(c)), None) or asked.get(row.clip_id)
        if found is None:  # a remake no watch asked for (a person's note)
            continue
        at = found["at"] if isinstance(found.get("at"), int | float) else 0
        did = ("Remade without them." if found.get("kind") == "text"
               else f"Remade on {_model(take, video_model(project).name)}.")  # fmt: skip
        out.append({"at": round(s["start"] + min(at, s["seconds"]), 1), "clip": row.clip_id,
                    "text": f"{_clip(row)}: {said(found['text']).rstrip('.')}. {did}"})  # fmt: skip
    return out


def _fixed(db: Session, project: Project, spans: list[dict], turns: list[Job]) -> list[dict]:
    """The run's free fixes on clips in the cut (a mute, a spliced word, another take the
    watch picked), as their results said them, at the clip's start, with what the watch of the
    cut found there."""
    from app.watch_cut import state

    found = {f.get("clip_id"): f.get("says", "") for f in state(db, project).get("findings") or []}
    where = {s["row"].clip_id: s for s in spans}
    out = []
    for j in turns:
        tool, clip = (j.output or {}).get("tool"), (j.output or {}).get("clip_id")
        result = j.input.get("result") or ""
        if tool not in FIXES or result.startswith("Refused") or clip not in where:
            continue
        if tool == "pick_take" and clip not in found:
            continue  # its own pick of the best take, not a fix
        head = f"{_clip(where[clip]['row'])}: " + (
            f"{said(found[clip]).rstrip('.')}. " if found.get(clip) else "")  # fmt: skip
        out.append({"at": round(where[clip]["start"], 1), "clip": clip,
                    "text": head + said(result)})  # fmt: skip
    return out


def shown(db: Session, project: Project, note: dict | None, owner: bool) -> dict | None:
    """The note as this person reads it, with its cost line: dollars to the owner ("$9.84
    spent of up to $16.86", what the run really cost), credits only to anyone else ("96
    credits used of up to 164 (59% of the budget)")."""
    from datetime import datetime

    from app.credits import price
    from app.models.credits import USD_PER_CREDIT

    if not note:
        return None
    up_to, usd = Decimal(str(note["up_to"])), None
    if owner:
        _, usd = spent(db, project, datetime.fromisoformat(note["since"]),
                       datetime.fromisoformat(note["until"]))  # fmt: skip
        most = math.ceil(up_to * USD_PER_CREDIT * 100) / 100
        cost = f"${usd:.2f} spent of up to ${most:.2f}"
    else:
        pct = round(100 * note["spent"] / note["up_to"]) if note["up_to"] else 0
        cost = (f"{round(note['spent'])} credits used of up to {price(up_to)} "
                f"({pct}% of the budget)")  # fmt: skip
    return {**note, "needs": note["needs"] or NOTHING, "cost": cost,
            "spent_usd": float(usd) if owner else None}  # fmt: skip


def plain(note: dict) -> str:
    """The note as plain lines: the chat's text for a screen that doesn't draw the card."""
    rows = [f"{int(r['at']) // 60}:{int(r['at']) % 60:02d} {r['text']}" for r in note["redid"]]
    return "\n".join(p for p in (note["made"], *rows, note["unsure"], note["needs"],
                                 note["cost"]) if p)  # fmt: skip
