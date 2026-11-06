"""What the director's watch of each take and host piece found and did (rule 11), as the Clips
tab, the progress card, the delivery note and the chat read it; and which of its findings are
confirmed (Reed, 4 Nov: "Uncertain evidence alone must not trigger paid remakes").

A finding is confirmed only by unambiguous evidence (Reed, 4 Nov): a fault seen in the sampled
frames, or clipped samples, the one measurement that can't mean anything else. Not confirmed:
the speech model's transcript (it can mishear, miss or invent words), a silence (a pause or a
dropout?), a jump in picture change (a glitch or a fast move?), lip-sync and voice judged from
sampled frames and the spectrogram, and music under a voice from the spectrogram and loudness.
An unconfirmed finding never pays for a remake on its own: the owner sees it as a note
("… (not confirmed)")."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import item_checks
from app.models.clips import ClipTake, FinalVideo, HostPiece, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project

UNSURE = ("lipsync", "voice", "timing")  # samples, the spectrogram, word times: never confirmed
CLIPPED = 10  # samples at full scale, with the peak at 0 dB, before clipping counts
ACTED = ("redo", "held", "flagged", "unsure")  # what's said in the chat and the delivery note
UNWATCHED = "Couldn't watch this one. Nothing was charged."


def facts(measured: dict | None) -> dict:
    """What a confirmation can rest on, from the listen: {clipped}: the peak reached full
    scale (0 dB) and at least CLIPPED samples sit there."""
    sound = (measured or {}).get("sound") or {}
    peak = sound.get("peak_db")
    full = peak is not None and peak >= -0.1
    return {"clipped": full and (sound.get("clipped_samples") or 0) >= CLIPPED}


def confirmed(kind: str, evidence: str, known: dict) -> bool:
    """A finding unambiguous evidence bears: seen in the frames, or clipped samples measured.
    Words from the transcript, a silence or a picture-change jump alone never are."""
    if kind in UNSURE:
        return False
    if evidence == "picture":
        return kind not in ("sound", "clipping")  # a sound isn't seen
    return evidence == "measured" and kind == "clipping" and known.get("clipped", False)


def faults(answer, ref_ids: list[str], known: dict) -> list[dict]:
    """The look's faults as kept: each with whether it's confirmed, unknown references blank."""
    refs = {"", "screen", "extra", *ref_ids}
    return [{"kind": f.kind, "at": f.at, "who": f.who if f.who in refs else "",
             "says": f.says if (ok := confirmed(f.kind, f.evidence, known))
             else f"{f.says.rstrip('.')} (not confirmed)", "verified": ok}
            for f in answer.faults]  # fmt: skip


def unsure(found: list[dict]) -> str:
    """What the owner is told when only unconfirmed faults would have remade it."""
    return f"Not remade: {'; '.join(f['says'] for f in found)}. Listen before you use it."


def shown(db: Session, item, target: str = "take") -> dict | None:
    """A take's (or a host piece's, `target` "piece") watch as the Clips tab reads it
    (WatchOut), or None before any. A talker clip's take shows its talker take's, live."""
    if target == "take" and (talker := (item.made_with or {}).get("talker")):
        return _talker(db, item, talker)
    w = item.watch
    if not w:
        return None
    if w.get("state") == "watching":  # its listen or look ended without an answer
        row = item_checks.latest(db, target, [item.id]).get(item.id)
        job = db.get(Job, row.job_id) if row and row.job_id else None
        if job and job.status in (JobStatus.failed, JobStatus.cancelled):
            w = {"state": "failed", "did": UNWATCHED}
    look = db.get(Job, w["job_id"]) if w.get("job_id") else None
    remake = db.scalar(select(ClipTake.number).where(ClipTake.job_id == w["remake_job_id"])
                       ) if w.get("remake_job_id") and target == "take" else None  # fmt: skip
    held = db.get(Job, w["remake_job_id"]) if w.get("action") == "held" else None
    return {**{k: w.get(k) for k in ("state", "found", "did", "action", "note", "at",
                                     "remake_credits")},
            "faults": [{k: f.get(k) for k in ("kind", "at", "says")} | {
                "verified": f.get("verified", True)} for f in w.get("faults") or []],
            "credits": float(look.credits) if look and look.status == JobStatus.succeeded else None,
            "remake_take": remake,
            "waiting": bool(held and held.status == JobStatus.needs_owner_approval)}  # fmt: skip


def _talker(db: Session, take: ClipTake, file_id: int) -> dict | None:
    """A talker clip's share of its talker take's watch: the faults inside its stretch."""
    clip = db.get(ProjectClip, take.clip_id)
    piece = next((p for p in db.scalars(select(HostPiece).where(
        HostPiece.project_id == clip.project_id))
        if p.file_id == file_id or file_id in (p.earlier or [])), None)  # fmt: skip
    seen = shown(db, piece, "piece") if piece else None
    span = clip.song_slice or {}
    return part(seen, span.get("start", 0.0), span.get("end", 0.0)) if seen else None


def part(watch: dict | None, start: float, end: float) -> dict | None:
    """A stretch's share of a watch: the faults inside it, in its own seconds; one for the whole
    take (no time) belongs to every stretch."""
    if not watch or watch.get("state") != "done":
        return watch
    inside = [{**f, "at": None if f.get("at") is None else round(f["at"] - start, 2)}
              for f in watch.get("faults") or []
              if f.get("at") is None or start <= f["at"] < end]  # fmt: skip
    if not inside:
        return {**watch, "faults": [], "action": "keep", "did": "Kept it."}
    return {**watch, "faults": inside}


def clip_takes_of(db: Session, project: Project) -> list[tuple[ProjectClip, list[ClipTake]]]:
    clips = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)
                       .order_by(ProjectClip.id))  # fmt: skip
    return [(c, list(db.scalars(select(ClipTake).where(ClipTake.clip_id == c.id)
                                .order_by(ClipTake.number)))) for c in clips]  # fmt: skip


def watched(db: Session, project: Project) -> list[dict]:
    """Every take and host piece the watch looked at: {clip_id ("c7", or "host"), number,
    item, watch (as `shown`)}. A talker clip's take is the host's: counted once, as the host."""
    out = [{"clip_id": c.clip_id, "number": t.number, "item": t, "watch": shown(db, t)}
           for c, takes in clip_takes_of(db, project) for t in takes
           if t.watch and not (t.made_with or {}).get("talker")]  # fmt: skip
    pieces = db.scalars(select(HostPiece).where(HostPiece.project_id == project.id,
                                                HostPiece.watch.is_not(None)))  # fmt: skip
    return out + [{"clip_id": "host", "number": r.number, "item": r,
                   "watch": shown(db, r, "piece")} for r in pieces]  # fmt: skip


def doubts(db: Session, project: Project) -> str:
    """For the delivery note's "What I'm unsure of": what the watch couldn't confirm on the
    takes in use and the host (Reed, 4 Nov: uncertain findings stay visible to the owner)."""
    out = []
    for x in watched(db, project):
        w, item = x["watch"], x["item"]
        said = "; ".join(f["says"] for f in w.get("faults") or [] if not f["verified"])
        if not said:  # any take in use: its doubts stay visible whatever else was done
            continue
        host = x["clip_id"] == "host"
        if not host and db.get(ProjectClip, item.clip_id).picked_take_id != item.id:
            continue
        what = (f"The host's piece {x['number']}" if host else
                f"Clip {x['clip_id'].removeprefix('c')}")  # fmt: skip
        out.append(f"{what}: {said}.")
    return " ".join(out)


def summary(db: Session, project: Project) -> dict:
    """Watching each take as it lands (the progress card): how many were watched, are being
    watched, remade, waiting for the owner, flagged or unconfirmed, and the newest one acted on."""
    count = {"watched": 0, "watching": 0, "redone": 0, "held": 0, "flagged": 0, "unsure": 0}
    acted = []
    for x in watched(db, project):
        state, action = x["watch"]["state"], x["watch"].get("action")
        count["watched"] += state == "done"
        count["watching"] += state == "watching"
        if action in ACTED:
            count[{"redo": "redone"}.get(action, action)] += 1
            acted.append(x)
    latest = max(acted, key=lambda x: x["watch"].get("at") or "") if acted else None
    return {**count, "latest": {"clip_id": latest["clip_id"], "take": latest["number"],
                                **latest["watch"]} if latest else None}  # fmt: skip


def redid(db: Session, project: Project) -> list[dict]:
    """What I watched and redid, for the delivery note: each take of the newest cut's clips
    and each host piece the watch remade, asked about, flagged or wasn't sure of, at its time
    in the cut ({at, clip_id, take, found, did, action}), in time order."""
    video = db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id)
                      .order_by(FinalVideo.id.desc()).limit(1))  # fmt: skip
    if video is None:
        return []
    by_clip = {c.id: (c, takes) for c, takes in clip_takes_of(db, project)}
    out, offset = [], 0.0
    for take_id in video.take_ids:
        take = db.get(ClipTake, take_id)
        if not take or take.clip_id not in by_clip:
            continue
        clip, takes = by_clip[take.clip_id]
        for t in takes:
            if (t.made_with or {}).get("talker"):
                continue  # the host's, listed once below
            if (w := t.watch or {}).get("action") in ACTED:
                out.append(_line(w, offset, clip.seconds, clip.clip_id, t.number))
        piece = clip.song_slice or {}
        offset += (piece["end"] - piece["start"]) if piece else clip.seconds
    for x in watched(db, project):  # a presenter's host runs on the narration's clock
        row = x["item"]
        if x["clip_id"] == "host" and x["watch"].get("action") in ACTED:
            out.append(_line(x["watch"], row.start, row.end - row.start, "host", row.number))
    return sorted(out, key=lambda x: x["at"])


def _line(w: dict, offset: float, longest: float, clip_id: str, number: int) -> dict:
    at = next((f["at"] for f in w.get("faults") or [] if f.get("at") is not None), 0)
    return {"at": round(offset + min(at, longest), 1), "clip_id": clip_id, "take": number,
            "found": w.get("found"), "did": w.get("did"), "action": w["action"]}  # fmt: skip
