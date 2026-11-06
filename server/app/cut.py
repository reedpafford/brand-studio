"""The cut and its editor (v6 boards S7-01 to S7-07, S3-12, P-12; build-plan piece E).

A video's cut is a timeline: B-roll pieces (each a take, from an in-point, for a stretch of
the cut), the presenter's spans (side, size, hidden), the voice (a narration or a song: the
clock), the music under it (how much quieter under the voice, whether it rises when no one
speaks) and each take's sound effects (app/take_sound.py). The base timeline comes from the
picked takes as the cut always put them; edits (models CutEdit) replay over it in order: trim,
re-time to the words, split, swap, presenter, music. Undo marks any one edit undone, so the
director's edits each have their own Undo. Edits are free; so is making the cut (Cut 1,
Cut 2, …), which runs on the worker's local lane (cut_render.py) while the cut before it
keeps playing. A story video's takes sit back to back (trims ripple); a narrated or song
video's pieces share their edges on the voice's clock (a trim moves the edge)."""

import copy
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import (
    host,
    host_layer,
    looks,
    narration,
    narration_music,
    take_sound,
    talker,
    video_settings,
)
from app.db import utcnow
from app.models.clips import ClipTake, CutEdit, FinalVideo, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import WAITING, Job, JobStatus
from app.models.projects import Project
from app.models.songs import SongTake

STEP = "cut_make"
MIN = 0.5  # seconds: the shortest piece
LEAD, TAIL = 0.15, 0.3  # re-timed to the words: a breath before the first word and after
SNAP = 0.5  # Snap to words: an edge this near a word's edge lands on it
HOLD = 3.0  # seconds a narrated cut may run past its last word
SIZES = {"small": 0.30, "medium": host_layer.HEIGHT, "large": 0.46}
QUIETER, LOUDEST = 18.0, 30.0  # dB the music sits under the voice: default ("A lot"), most
KINDS = ("trim", "retime", "split", "swap", "presenter", "music")
AFTER_LAST_LINE = 1.0  # seconds of song after the last sung line before the end
NO_PIECE = "There's no {} in the cut."
NO_HOST = "This video has no presenter."
NO_MUSIC = "This video has no music under it."
TOO_SHORT = f"A piece can't be shorter than {MIN} s."
BEFORE_WORDS = "The cut can't end before the last word, at {}."
NO_WORDS = "This clip's words aren't heard yet, so it can't be re-timed to them."
MAKING = "Cut {} is being made. It's ready in a moment."
SYNCED = "This piece lip-syncs the voice: its start can only move later, with its picture."
SYNCED_LONG = "This piece lip-syncs the voice: it can't run longer than its picture."
OLD_TALKER = "That take wasn't cut from the talker take in use: its lips say another voice."
NOT_TIMED = "A clip isn't timed to the song yet. Rewrite the clip prompts, then make the video."
SONG_CHANGED = (
    "{} of the clips were made for the video's earlier song. Press Rewrite clip prompts on "
    "Clips and remake them, then make the video."
)


class Refused(ValueError):
    """An edit that can't be made, in plain words."""


def tc(t: float) -> str:
    """0:24, as the boards write a time in the cut."""
    return f"{int(t // 60)}:{int(t % 60):02d}"


def label(piece_id: str) -> str:
    """ "Clip 7" for c7 and for a piece split off it (c7.12)."""
    return f"Clip {piece_id.split('.')[0].removeprefix('c')}"


def rows(db: Session, project: Project) -> list[ProjectClip]:
    return list(db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)
                           .order_by(ProjectClip.id)))  # fmt: skip


def song(db: Session, project: Project) -> SongTake | None:
    return db.get(SongTake, project.song_take_id) if project.song_take_id else None


def song_end(take: SongTake) -> float | None:
    """Where a song video ends: its last line heard, and a breath."""
    sung = [x for x in (take.timing or {}).get("lines") or []
            if (x.get("heard") or 0) >= 0.5 and x.get("end") is not None]  # fmt: skip
    return round(sung[-1]["end"] + AFTER_LAST_LINE, 2) if sung else None


def ends_at(lengths: list[float], end: float | None) -> list[float]:
    """The clips' lengths cut to end at `end` (the last sung line and a breath after it):
    the clips past it drop, the one across it is shortened. None or later: as they are."""
    if end is None or end >= sum(lengths):
        return lengths
    out, t = [], 0.0
    for d in lengths:
        if t >= end:
            break
        out.append(round(min(d, end - t), 2))
        t += d
    return out


def _take_seconds(db: Session, take: ClipTake | None, planned: float) -> float:
    """A take's length as it was asked of the model (its job's duration), else as planned."""
    job = db.get(Job, take.job_id) if take else None
    asked = ((job.input or {}).get("input") or {}).get("duration") if job else None
    return float(asked or planned)


def synced(p: dict) -> bool:
    """A piece whose picture says the words: a talker's lip-sync."""
    return bool(p.get("lipsync"))


def poster(db: Session, take_id: int | None) -> int | None:
    """A take's picture for the timeline: the storyboard still it was made from, if any."""
    from app.models.storyboards import StoryboardFrame

    take = db.get(ClipTake, take_id) if take_id else None
    job = db.get(Job, take.job_id) if take else None
    given = ((job.input or {}).get("files") or {}).get("reference_images") or [] if job else []
    return db.scalar(select(StoryboardFrame.file_id).where(StoryboardFrame.file_id.in_(given))
                     .limit(1)) if given else None  # fmt: skip


def _heard(db: Session, take: ClipTake | None) -> list[dict]:
    from app.word_splice import _heard

    return _heard(db, take)[0] if take else []


def base(db: Session, project: Project) -> dict:
    """The cut as the picked takes make it, before any edit."""
    voice, clips = song(db, project), rows(db, project)
    mode = "takes" if voice is None else "narrated" if voice.kind == narration.KIND else "song"
    if mode == "takes":
        lengths = [_take_seconds(db, db.get(ClipTake, r.picked_take_id) if r.picked_take_id
                                 else None, r.seconds) for r in clips]  # fmt: skip
    else:
        lengths = [(r.song_slice["end"] - r.song_slice["start"]) if r.song_slice
                   else float(r.seconds) for r in clips]  # fmt: skip
        lengths = ends_at(lengths, song_end(voice)) if mode == "song" else lengths
    pieces, at = [], 0.0
    synced = talker.clips(db, project)  # a talker's clips lip-sync the narration
    made = next(iter(host.rows(db, project)[1:]), None) if synced else None
    voiced = made.file_id if made else None  # the talker take in use (a take's made_with "talker")
    for r, d in zip(clips, lengths, strict=False):
        pieces.append({"id": r.clip_id, "clip_id": r.clip_id, "take_id": r.picked_take_id,
                       "source": label(r.clip_id), "start": round(at, 2),
                       "end": round(at + d, 2), "from": 0.0, "whole": mode == "takes",
                       "edited": False, "director": False,
                       "lipsync": r.clip_id in synced,
                       **({"picture": round(d, 2), "voiced": voiced}
                          if r.clip_id in synced else {})})  # fmt: skip
        at += d
    total = round(at, 2)
    tl = {
        "mode": mode,
        "pieces": pieces,
        "length": total,
        "presenter": None,
        "voice": None,
        "music": None,
        "words": [],
        "seconds": float(voice.seconds or 0) if voice else None,
    }
    if host.on(db, project) and not talker.on(db, project):  # a talker is in its clips
        look = host.host_look(db, project)
        sides = host.sides(db, project)
        ends = [t for t, _ in sides[1:]] + [total]
        tl["presenter"] = {"name": look.name if look else "The presenter", "spans": [
            {"start": a, "end": b, "side": s, "size": "medium", "hidden": False,
             "director": False} for (a, s), b in zip(sides, ends, strict=True)]}  # fmt: skip
    if voice is not None:
        name = tl["presenter"]["name"] if tl["presenter"] else voice.voice or "The narrator"
        tl["voice"] = {"label": f"{name}’s voice" if mode == "narrated" else "The song",
                       "text": voice.lyrics or ""}  # fmt: skip
        tl["words"] = [{"word": w["word"], "start": w["start"], "end": w["end"]}
                       for w in (voice.timing or {}).get("words") or []]  # fmt: skip
        tl["lines"] = [[ln["start"], ln["end"]] for ln in (voice.timing or {}).get("lines") or []
                       if ln.get("start") is not None and ln.get("end") is not None]  # fmt: skip
        last = song_end(voice) if mode == "song" else None  # a breath after its last good line
        tl["last_word"] = round(last - AFTER_LAST_LINE, 2) if last else max(
            (w["end"] for w in tl["words"]), default=0.0)  # fmt: skip
    if mode == "narrated" and voice.music_file_id:
        tl["music"] = {"file_id": voice.music_file_id, "name": _bed_name(db, voice),
                       "quieter_db": QUIETER, "gaps": "rise", "loop": True, "removed": False,
                       "director": False}  # fmt: skip
    return tl


def _bed_name(db: Session, voice: SongTake) -> str:
    """The bed's name: its prompt's first phrase ("Low synth bed")."""
    job = db.scalar(select(Job).where(Job.input["take_id"].as_integer() == voice.id,
                                      Job.input["step"].as_string() == "narration_bed")
                    .order_by(Job.id.desc()).limit(1))  # fmt: skip
    said = ((job.input or {}).get("input") or {}).get("prompt", "") if job else ""
    return re.split(r"[,.:;]", said)[0].strip()[:40] or "Music"


def active(db: Session, project: Project) -> list[CutEdit]:
    return list(db.scalars(select(CutEdit).where(CutEdit.project_id == project.id,
                                                 CutEdit.undone_at.is_(None))
                           .order_by(CutEdit.id)))  # fmt: skip


def every(db: Session, project: Project) -> list[CutEdit]:
    return list(db.scalars(select(CutEdit).where(CutEdit.project_id == project.id)
                           .order_by(CutEdit.id)))  # fmt: skip


def replay(tl: dict, edits: list[CutEdit]) -> tuple[dict, set[int]]:
    """The timeline with each edit applied in order; the ids of those that no longer apply
    (a piece split off by an edit since undone, say), which are skipped."""
    tl, lost = copy.deepcopy(tl), set()
    for e in edits:
        try:
            _one(tl, e)
        except Refused:
            lost.add(e.id)
    return tl, lost


def _find(tl: dict, piece_id: str) -> int:
    i = next((n for n, p in enumerate(tl["pieces"]) if p["id"] == piece_id), None)
    if i is None:
        raise Refused(NO_PIECE.format(label(piece_id).lower() if piece_id else "such piece"))
    return i


def _place(tl: dict) -> None:
    """A story video's pieces back to back from 0 (a trim ripples); the cut's length."""
    if tl["mode"] == "takes":
        at = 0.0
        for p in tl["pieces"]:
            d = p["end"] - p["start"]
            p["start"], p["end"], at = round(at, 2), round(at + d, 2), at + d
    tl["length"] = tl["pieces"][-1]["end"] if tl["pieces"] else 0.0


def _one(tl: dict, e: CutEdit) -> None:
    d, mark = e.data, {"edited": True, **({"director": True} if e.director else {})}
    if e.kind in ("trim", "retime", "split", "swap"):
        i = _find(tl, d["piece"])
        p, pieces = tl["pieces"][i], tl["pieces"]
        if e.kind == "split":
            if not p["start"] + MIN <= d["at"] <= p["end"] - MIN:
                raise Refused(TOO_SHORT)
            half = {**p, "id": f"{p['id'].split('.')[0]}.{e.id}", "start": d["at"],
                    "from": round(p["from"] + d["at"] - p["start"], 2), **mark}  # fmt: skip
            p.update(end=d["at"], whole=False, **mark)
            pieces.insert(i + 1, half)
        elif e.kind == "swap":
            if p.get("lipsync") and d.get("voiced") != p.get("voiced"):
                raise Refused(OLD_TALKER)  # also on a replay, once the talker is remade
            p.update(take_id=d["take_id"], source=d["source"], whole=False, **mark)
            p["from"] = p["from"] if synced(p) else 0.0  # on the words, as it was
        elif tl["mode"] == "takes":  # in the take's own seconds; the rest ripples
            p.update(start=p["start"], end=p["start"] + d["length"], whole=False, **mark)
            p["from"] = d["from"]
        else:  # on the voice's clock: an edge moves, and the picture after it with it
            if "from" in d and synced(p):
                raise Refused(SYNCED)
            if "start" in d and i > 0:
                _edge(pieces, i, d["start"])
            if "end" in d:
                p["end"] = d["end"]
                if i + 1 < len(pieces):
                    _edge(pieces, i + 1, d["end"])
            p["from"] = d.get("from", p["from"])
            p.update(**mark)
        if any(synced(q) and q["from"] + q["end"] - q["start"] > q["picture"] + 0.02
               for q in pieces):  # fmt: skip
            raise Refused(SYNCED_LONG)  # slowed to fill, its lips would fall behind
        if any(q["end"] - q["start"] < MIN - 0.01 for q in pieces):
            raise Refused(TOO_SHORT)
        _place(tl)
        return
    if e.kind == "presenter":
        if not tl["presenter"]:
            raise Refused(NO_HOST)
        what = {k: d[k] for k in ("side", "size", "hidden") if k in d}
        tl["presenter"]["spans"] = _spanned(tl["presenter"]["spans"], d["start"], d["end"],
                                            {**what, **mark})  # fmt: skip
        return
    if tl["mode"] != "narrated" or (not tl["music"] and "file_id" not in d):
        raise Refused(NO_MUSIC)  # a story's sound is its takes', a song's its song
    keys = ("quieter_db", "gaps", "loop", "removed", "file_id", "name")
    tl["music"] = {**(tl["music"] or {"quieter_db": QUIETER, "gaps": "rise", "loop": False,
                                      "removed": False}),
                   **{k: d[k] for k in keys if k in d}, **mark}  # fmt: skip


def _edge(pieces: list[dict], i: int, t: float) -> None:
    """The edge before piece `i` moves to `t`: the piece after it starts that much further
    into its take (or less far), so a lip-synced piece stays on the words; one that would
    have to start before its take's beginning can't move that way."""
    q = pieces[i]
    moved = t - q["start"]
    if synced(q) and q["from"] + moved < -0.005:
        raise Refused(SYNCED)
    q["from"] = round(max(0.0, q["from"] + moved), 2)
    pieces[i - 1]["end"] = q["start"] = t


def _spanned(spans: list[dict], a: float, b: float, what: dict) -> list[dict]:
    """The presenter's spans with a..b set to `what`, split at a and b, equal ones joined."""
    cut = []
    for s in spans:
        for x, y in ((s["start"], min(s["end"], a)), (max(s["start"], a), min(s["end"], b)),
                     (max(s["start"], b), s["end"])):  # fmt: skip
            if y - x > 0.01:
                cut.append({**s, "start": x, "end": y, **(what if a <= x and y <= b else {})})
    out: list[dict] = []
    for s in cut:
        if out and {k: v for k, v in out[-1].items() if k not in ("start", "end")} == {
            k: v for k, v in s.items() if k not in ("start", "end")
        }:
            out[-1]["end"] = s["end"]
        else:
            out.append(s)
    return out


def timeline(db: Session, project: Project) -> tuple[dict, set[int]]:
    tl, lost = replay(base(db, project), active(db, project))
    tl["words"] = _cut_words(db, tl)
    return tl, lost


def _cut_words(db: Session, tl: dict) -> list[dict]:
    """The words in cut seconds: the voice's, or a story video's takes' as each piece plays."""
    if tl["mode"] != "takes":
        return tl["words"]
    out = []
    for p in tl["pieces"]:
        take = db.get(ClipTake, p["take_id"]) if p["take_id"] else None
        for w in _heard(db, take):
            at = p["start"] + w["start"] - p["from"]
            if p["start"] <= at and at + w["end"] - w["start"] <= p["end"] + 0.05:
                out.append({"word": w["word"], "start": round(at, 2),
                            "end": round(at + w["end"] - w["start"], 2)})  # fmt: skip
    return out


def _snap(t: float, words: list[dict]) -> float:
    edges = [x for w in words for x in (w["start"], w["end"])]
    near = min(edges, key=lambda x: abs(x - t), default=t)
    return round(near if abs(near - t) <= SNAP else t, 2)


def newest(db: Session, project: Project) -> FinalVideo | None:
    """The newest cut made (the one that plays)."""
    return db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id)
                     .order_by(FinalVideo.id.desc()).limit(1))  # fmt: skip


def next_number(db: Session, project: Project, playing: FinalVideo | None) -> int:
    """Cut N is the Nth cut handed over (S3-12): a person's, or one the director delivered.
    The director making its own cut again in the run that made it, before it delivers, keeps
    that cut's number: the new one replaces it."""
    from app import director
    from app.routes.jobs import BY_DIRECTOR, DIRECTOR_TOOL

    if playing is None:
        return 1
    run = director.turns(db, project) if DIRECTOR_TOOL.get() else []
    made = db.scalar(select(Job).where(Job.project_id == project.id,
                                       Job.status == JobStatus.succeeded,
                                       Job.input["step"].as_string() == STEP)
                     .order_by(Job.id.desc()).limit(1))  # fmt: skip
    draft = (bool(run) and made is not None and made.id > run[0].id and made.input.get(BY_DIRECTOR)
             and (made.output or {}).get("file_ids", [None])[0] == playing.file_id)  # fmt: skip
    return playing.number if draft else playing.number + 1


def making(db: Session, project: Project) -> Job | None:
    return db.scalar(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING),
                                       Job.input["step"].as_string() == STEP)
                     .order_by(Job.id.desc()).limit(1))  # fmt: skip


def sfx(db: Session, tl: dict) -> list[dict]:
    """Each piece's added sound effects (take_sound), where they sit in the cut."""
    out = []
    for p in tl["pieces"]:
        take = db.get(ClipTake, p["take_id"]) if p["take_id"] else None
        state = take_sound.state(db, take) if take else None
        if state and state["state"] != "none":
            director = bool(take_sound._job(db, take) and take_sound._job(db, take).input.get(
                "by_director"))  # fmt: skip
            out.append({"piece": p["id"], "start": p["start"], "end": p["end"],
                        "state": state["state"], "asked": state["asked"],
                        "how": state["how"], "director": director})  # fmt: skip
    return out


def ready(db: Session, project: Project, storage) -> None:
    """What a cut needs before it's made, each in plain words (rule 22). A UGC talker's clips
    are cut from its one take first (free: talker.fill)."""
    from app.routes.project_clips import _newest_breakdown, _stale

    clips = rows(db, project)
    if not clips:
        raise HTTPException(409, "Write the clip prompts and make the clips first.")
    if talker.on(db, project):
        if not host.ready(db, project):
            raise HTTPException(409, host.NOT_READY)
        talker.fill(db, storage, project)
    if left := sum(not c.approved for c in clips):
        raise HTTPException(409, f"Approve every clip to make the video ({left} left).")
    if other := sum(looks.take_other(db, project, c) for c in clips):  # VS1: never mixed looks
        raise HTTPException(409, looks.OTHER.format("1 clip was" if other == 1
                                                    else f"{other} clips were"))  # fmt: skip
    if other := sum(video_settings.take_stale(db, project, c) for c in clips):  # nor settings
        said = "1 clip was" if other == 1 else f"{other} clips were"
        raise HTTPException(409, video_settings.OTHER.format(said))
    voice = song(db, project)
    if voice and not all(c.song_slice for c in clips):
        raise HTTPException(409, NOT_TIMED)
    newest = _newest_breakdown(db, project)
    if voice and (old := sum(_stale(db, c, newest) for c in clips)):  # made for the earlier song
        raise HTTPException(409, SONG_CHANGED.format(old))
    narrated = bool(voice and voice.kind == narration.KIND)
    if narrated and narration_music.state(db, voice)[0] == "making":
        raise HTTPException(409, narration_music.MAKING)
    if host.on(db, project) and not (narrated and host.ready(db, project)):
        raise HTTPException(409, host.NOT_READY)


def doing(tl: dict) -> str:
    """What making it does, as the banner says it."""
    music = ", music under the voice" if tl["music"] and not tl["music"]["removed"] else ""
    if tl["presenter"]:
        name = tl["presenter"]["name"]
        name = "the presenter" if name == "The presenter" else name
        return f"laying {name} over the B-roll{music}"
    if tl["mode"] == "narrated":
        return f"putting the B-roll under the voice{music}"
    return "putting the clips to the song" if tl["mode"] == "song" else "putting the clips together"


def saved(db: Session, job: Job) -> None:
    """The cut is made: the next Cut plays from now on. A problem keeps the one before."""
    out, i = job.output or {}, job.input
    if out.get("problem") or not out.get("file_ids"):
        return
    project = db.get(Project, job.project_id)
    stored = db.get(StoredFile, out["file_ids"][0])
    stored.filename, stored.uploaded_by_id = f"{project.name[:200]}.mp4", job.created_by_id
    db.add(FinalVideo(project_id=project.id, file_id=stored.id, number=i["number"],
                      take_ids=i["take_ids"], cut_ins=i["cut_ins"], edit_ids=i["edit_ids"],
                      song_take_id=i["song_take_id"], timeline=i["timeline"],
                      seconds=i["timeline"]["length"],  # Media shows it
                      created_by_id=job.created_by_id))  # fmt: skip
    project.finished_at = project.finished_at or utcnow()
