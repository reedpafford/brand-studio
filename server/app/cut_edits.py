"""Edits to the cut (app/cut.py; v6 S7-01 to S7-03, P-12): each one checked by replaying every
edit with it, kept with absolute values (so a replay always gives the same cut), what it says
in the list ("Clip 9 re-timed to the words") and where it is in the cut. Free. Undo marks any
one undone, Redo brings back the last undone while nothing newer was edited, Undo all goes
back to the cut that plays."""

from contextvars import ContextVar
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app import host_layer, narration
from app.cut import (
    BEFORE_WORDS,
    HOLD,
    KINDS,
    LEAD,
    LOUDEST,
    MIN,
    NO_HOST,
    NO_WORDS,
    OLD_TALKER,
    SIZES,
    TAIL,
    TOO_SHORT,
    Refused,
    _bed_name,
    _find,
    _heard,
    _one,
    _snap,
    _take_seconds,
    active,
    base,
    every,
    label,
    newest,
    rows,
    song,
    synced,
    tc,
    timeline,
)
from app.db import utcnow
from app.models.accounts import User
from app.models.clips import ClipTake, CutEdit, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.songs import SongTake


def add(db: Session, user: User, project: Project, kind: str, asked: dict,
        director: bool = False) -> CutEdit:  # fmt: skip
    """Make one edit (free), checked by replaying every edit with it; Refused says why not."""
    if kind not in KINDS:
        raise Refused(f"There's no edit called {kind}.")
    tl, _ = timeline(db, project)
    if (
        director
        and kind == "music"
        and not PERSON_ASKED.get()
        and (mine := _persons_music(db, project))
    ):
        raise Refused(PERSONS_MUSIC.format(mine.said))
    try:
        data, said, at = _shape(db, user, project, tl, kind, asked)
    except (KeyError, TypeError, ValueError) as no:
        if isinstance(no, Refused):
            raise
        raise Refused(SAY.get(kind, "Say what the edit changes.")) from no
    row = CutEdit(project_id=project.id, by_id=user.id, director=director, kind=kind,
                  data=data, said=said, at=round(at, 2))  # fmt: skip
    db.add(row)
    db.flush()
    row.kept = []  # the words a trim was moved to keep (said back to whoever pressed it)
    while True:
        after = _replayed(db, project, row)
        try:
            keeps_every_word(db, after)
            return row
        except LosesWord as lost:  # S4 (Flow-QA): the nearest trim that keeps it, said so
            moved = _keeping(db, tl, row, lost) if kind == "trim" else None
            if moved is None:
                raise
            row.data = moved  # each word it would cut, named (one at each edge)
            row.kept += [lost.word] if lost.word not in row.kept else []
            row.said = f"{label(data['piece'])} trimmed, keeping {quoted(row.kept)}"
            flag_modified(row, "data")
            db.flush()


def quoted(words: list[str]) -> str:
    """“Get”, or “Get” and “up”: the words a trim was moved to keep."""
    q = [f"“{w}”" for w in words]
    return q[0] if len(q) == 1 else f"{', '.join(q[:-1])} and {q[-1]}"


def _replayed(db: Session, project: Project, row: CutEdit) -> dict:
    """The timeline with every edit in force, this one too (its own refusal raised)."""
    after = base(db, project)
    for e in active(db, project):
        try:
            _one(after, e)
        except Refused:
            if e.id == row.id:
                raise
    return after


class LosesWord(Refused):
    """An edit that would cut a spoken word: which clip, take and word (its times in the take)."""

    def __init__(self, said: str, slot: str, take_id: int, word: dict):
        super().__init__(said)
        self.slot, self.take_id, self.word, self.times = slot, take_id, word["word"].strip(), word


def _keeping(db: Session, tl: dict, row: CutEdit, lost: LosesWord) -> dict | None:
    """A story trim moved out just past the word it would cut (a breath before it, or after
    it), as far as its take runs; None when it isn't this trim's word, or moving can't keep it."""
    d = row.data
    if not lost.slot:  # a narrated or song cut ending before its last word: at it, a breath on
        ends = d.get("end") is not None and d["piece"] == tl["pieces"][-1]["id"]
        return {**d, "end": round(lost.times["end"] + TAIL, 2)} if ends else None
    if "length" not in d or lost.slot != d["piece"].split(".")[0]:
        return None
    take = db.get(ClipTake, lost.take_id)
    longest = _take_seconds(db, take, d["length"])
    frm, end = d["from"], d["from"] + d["length"]
    frm = round(min(frm, max(0.0, lost.times["start"] - LEAD)), 2)
    end = round(min(max(end, lost.times["end"] + TAIL), longest), 2)
    moved = {**d, "from": frm, "length": round(end - frm, 2)}
    return None if moved == d or end < lost.times["end"] else moved


PERSON_ASKED: ContextVar[bool] = ContextVar("person_asked", default=False)  # a note asks for it
PERSONS_MUSIC = ("A person set the music themselves ({}), so it stays as they left it unless a "
                 "person asks for a change in a note.")  # fmt: skip


def _persons_music(db: Session, project: Project) -> CutEdit | None:
    """The newest music edit in force, when a person made it (removed it, set its level or
    swapped it): their choice, which the director never changes on its own (QA on #1415)."""
    mine = [e for e in active(db, project) if e.kind == "music"]
    return mine[-1] if mine and not mine[-1].director else None


def _fits(tl: dict) -> None:
    """A narrated cut runs at least to its last word; a song cut no further than its song."""
    last = tl.get("last_word") or max((w["end"] for w in tl["words"]), default=0.0)
    if tl["mode"] in ("narrated", "song") and tl["length"] < last - 0.005:
        word = max(tl["words"], key=lambda w: w["end"], default={"word": "the last word"})
        raise LosesWord(BEFORE_WORDS.format(f"{tc(last)}.{int(last * 10) % 10}"), "", 0,
                        {**word, "start": last, "end": last})  # fmt: skip
    if tl["mode"] == "narrated" and tl["length"] > last + HOLD and last:
        raise Refused(f"The cut can hold at most {HOLD:.0f} s past the last word.")
    if tl["mode"] == "song" and tl.get("seconds") and tl["length"] > tl["seconds"] + 0.05:
        raise Refused(f"The cut can't run past the song's end, at {tc(tl['seconds'])}.")


TALKER_MAKING = "The talker is being made again: swap this piece once it's ready."
UNHEARD = ("This clip's words aren't heard yet, so a trim could cut one. Try again once its "
           "words check is done.")  # fmt: skip
SAY = {"split": "Say where to split: a time in the cut.",
       "trim": "Say the piece's new start or end.",
       "swap": "Say which take to swap in."}  # fmt: skip


def _shape(db: Session, user: User, project: Project, tl: dict, kind: str,
           d: dict) -> tuple[dict, str, float]:  # fmt: skip
    """The edit as it's kept (absolute values, so a replay gives the same cut), what it says
    in the list of edits, and where in the cut it is."""
    words, snap = tl["words"], d.get("snap", False)
    near = (lambda t: _snap(t, words)) if snap else (lambda t: round(t, 2))
    if kind == "presenter":
        return _presenter(tl, d)
    if kind == "music":
        return _music(db, project, d, tl)
    if kind in ("captions", "cards"):
        name = "Captions" if kind == "captions" else "Time cards"
        return {"on": bool(d["on"])}, f"{name} {'on' if d['on'] else 'off'}", 0.0
    if kind == "split":
        at = near(float(d["at"]))
        piece = d.get("piece") or next((p["id"] for p in tl["pieces"]
                                        if p["start"] < at < p["end"]), "")  # fmt: skip
        tl["pieces"][_find(tl, piece)]  # noqa: B018 - it's there, or Refused
        return {"piece": piece, "at": at}, f"{label(piece)} split at {tc(at)}", at
    i = _find(tl, d.get("piece") or "")
    p = tl["pieces"][i]
    if kind == "swap":
        take, source = _swap_source(db, user, project, p, d.get("take_id"), tl["mode"])
        voiced = {"voiced": (take.made_with or {}).get("talker")} if p.get("lipsync") else {}
        return (
            {"piece": p["id"], "take_id": take.id, "source": source, **voiced},
            f"{label(p['id'])} swapped for {source[0].lower()}{source[1:]}",
            p["start"],
        )
    if kind == "retime":
        return _retime(db, tl, i), f"{label(p['id'])} re-timed to the words", p["start"]
    start = near(float(d["start"])) if d.get("start") is not None else None
    end = near(float(d["end"])) if d.get("end") is not None else None
    if tl["mode"] == "takes":
        cut = (start - p["start"]) if start is not None else 0.0
        frm = round(max(0.0, p["from"] + cut), 2)
        length = round((end if end is not None else p["end"])
                       - (start if start is not None else p["start"]), 2)  # fmt: skip
        data = {"piece": p["id"], "from": float(d.get("from", frm)), "length": length}
    else:
        data = {
            "piece": p["id"],
            **({"start": start} if start is not None else {}),
            **({"end": end} if end is not None else {}),
            **({"from": round(float(d["from"]), 2)} if d.get("from") is not None else {}),
        }
    take = db.get(ClipTake, p["take_id"]) if p["take_id"] else None
    longest = _take_seconds(db, take, p["end"] - p["start"])
    if data.get("from", 0) > longest - MIN:
        raise Refused(f"The take is {longest:g} s long: start it before {longest - MIN:g} s.")
    last = i == len(tl["pieces"]) - 1
    if last and end is not None and start is None:
        data["ending"] = True  # the ending's trim, kept when it's moved to keep a word
        cut = round(p["end"] - end, 1)
        said = f"Ending trimmed {cut} s" if cut > 0 else f"Ending held {-cut} s longer"
    else:
        said = f"{label(p['id'])} trimmed"
    return data, said, start if start is not None else (end if end is not None else p["start"])


def keeps_every_word(db: Session, tl: dict) -> None:
    """Reed (3 Nov): an edit never cuts a scripted spoken word. A narrated or song cut runs
    to its last word; in a story video, every word a speaking take says plays in a piece of
    its clip that plays that take, after any edit, undo, redo or new pick."""
    from app.item_checks import latest

    _fits(tl)
    if tl["mode"] != "takes":
        return
    groups: dict[tuple[str, int], list[tuple[float, float]]] = {}
    for p in tl["pieces"]:
        end = float("inf") if p["whole"] else p["from"] + p["end"] - p["start"]
        groups.setdefault((p["id"].split(".")[0], p["take_id"]), []).append((p["from"], end))
    for p in tl.get("dropped", []):  # an ending trim's dropped piece plays nothing
        groups.setdefault((p["id"].split(".")[0], p["take_id"]), [])
    for (slot, take_id), plays in groups.items():
        take = db.get(ClipTake, take_id) if take_id else None
        if not _speaks(db, take) or (0.0, float("inf")) in plays:
            continue
        check = latest(db, "words", [take.id]).get(take.id)
        if check is None or check.status != "done":
            raise Refused(UNHEARD)
        for w in _heard(db, take):
            if not any(a - 0.02 <= w["start"] and w["end"] <= b + 0.02 for a, b in plays):
                raise LosesWord(f"{label(slot)} would lose the word “{w['word'].strip()}”. "
                                "Every spoken word stays.", slot, take.id, w)  # fmt: skip


def _speaks(db: Session, take: ClipTake | None) -> bool:
    """The take was made with sound for its lines, so it may say one (silent B-roll says
    nothing, nor does a take with only its own room and effects: `clip_takes.own_sound`)."""
    job = db.get(Job, take.job_id) if take else None
    given = (job.input or {}) if job else {}
    return bool(((given.get("input") or {}).get("generate_audio")  # made with its sound
                 and not given.get("own_sound"))
                or (given.get("files") or {}).get("audio"))  # lip-synced to a voice  # fmt: skip


def _retime(db: Session, tl: dict, i: int) -> dict:
    """Onto the words: a story video's take from just before its first word to just after its
    last; a narrated or song video's edges onto the nearest word starts (where lines begin)."""
    p = tl["pieces"][i]
    if tl["mode"] == "takes":
        take = db.get(ClipTake, p["take_id"]) if p["take_id"] else None
        heard = [w for w in _heard(db, take)
                 if p["from"] <= w["start"] < p["from"] + p["end"] - p["start"]]  # fmt: skip
        if not heard:
            raise Refused(NO_WORDS)
        frm = round(max(0.0, heard[0]["start"] - LEAD), 2)
        return {"piece": p["id"], "from": frm, "length": round(heard[-1]["end"] + TAIL - frm, 2)}
    starts = [w["start"] for w in tl["words"]]
    if not starts:
        raise Refused(NO_WORDS)

    def onto(t: float) -> float:
        best = min(starts, key=lambda s: abs(s - t))
        return round(best if abs(best - t) <= 1.5 else t, 2)

    data = {"piece": p["id"]}
    if i > 0:
        data["start"] = onto(p["start"])
    if i + 1 < len(tl["pieces"]):
        data["end"] = onto(p["end"])
    else:
        last = tl.get("last_word") or max(w["end"] for w in tl["words"])  # a song's last good line
        held = min(p["end"], last + narration.FINAL_HOLD)  # the last shot's planned hold stays
        data["end"] = round(max(held, last + TAIL), 2)
    return data


def _swap_source(db: Session, user: User, project: Project, p: dict, take_id,
                 mode: str) -> tuple[ClipTake, str]:  # fmt: skip
    """A take for this piece: the clip's other takes, another clip's, or one from another
    video of the brand the person can see (the Library, as `swaps` offers it), in the same
    shape. Said as the swap row says it: "Take 1", "Clip 4"."""
    take = db.get(ClipTake, int(take_id)) if take_id else None
    row = db.get(ProjectClip, take.clip_id) if take else None
    other = db.get(Project, row.project_id) if row else None
    if not other or other.workspace_id != project.workspace_id or (
        other.brand_id != project.brand_id
    ) or (other.id != project.id and (other.archived_at is not None or not (
        user.is_owner or other.created_by_id == user.id))):  # fmt: skip
        raise Refused("That take isn't in this brand.")
    current = db.get(ClipTake, p["take_id"]) if p["take_id"] else None
    if (
        mode == "takes"
        and (other.id != project.id or row.clip_id != p["clip_id"])
        and (_speaks(db, current) or _speaks(db, take))
    ):
        raise Refused("Here the takes say the lines: a piece swaps only for another take of "
                      "its own clip.")  # fmt: skip
    elsewhere = other.id != project.id or row.clip_id != p["clip_id"]
    talks = p.get("lipsync") or (take.made_with or {}).get("talker")
    if mode == "narrated" and talks and elsewhere:  # its lips say this stretch of the voice
        raise Refused("A talker piece swaps only for another take of its own clip.")
    if p.get("lipsync") and not p.get("voiced"):  # the talker is being made again
        raise Refused(TALKER_MAKING)
    if p.get("lipsync") and (take.made_with or {}).get("talker") != p.get("voiced"):
        raise Refused(OLD_TALKER)
    if other.aspect_ratio != project.aspect_ratio:
        raise Refused(f"That take is {other.aspect_ratio}; this video is {project.aspect_ratio}.")
    if other.id != project.id:
        return take, f"{other.name[:60]}, take {take.number}"
    if row.clip_id == p["clip_id"]:
        return take, f"Take {take.number}"
    return take, label(row.clip_id)


def _presenter(tl: dict, d: dict) -> tuple[dict, str, float]:
    if not tl["presenter"]:
        raise Refused(NO_HOST)
    if d.get("piece"):
        p = tl["pieces"][_find(tl, d["piece"])]
        a, b = p["start"], p["end"]
    else:
        a, b = float(d.get("start") or 0), float(d.get("end") or tl["length"])
    if b - a < MIN:
        raise Refused(TOO_SHORT)
    what = {k: d[k] for k in ("side", "size", "hidden") if d.get(k) is not None}
    if (
        not what
        or what.get("side", "left") not in host_layer.SIDES
        or what.get("size", "medium") not in SIZES
    ):
        raise Refused("Say a side (left or right), a size (small, medium, large) or hidden.")
    name, span = tl["presenter"]["name"], f"{tc(a)}–{tc(b)}"
    said = (
        f"{name} moved {what['side']}"
        if "side" in what
        else f"{name} hidden {span}"
        if what.get("hidden")
        else f"{name} shown {span}"
        if "hidden" in what
        else f"{name} {what['size']} {span}"
    )
    return {"start": round(a, 2), "end": round(b, 2), **what}, said, a


NO_BED = ("This brand has no music bed yet to lay under the cut. A narrated video's music bed "
          "is saved with the brand and can be used here.")  # fmt: skip


def _music(
    db: Session, project: Project, d: dict, tl: dict | None = None
) -> tuple[dict, str, float]:
    tl = tl or {"mode": "", "music": None}
    if (
        tl["mode"] == "takes"
        and not tl["music"]
        and d.get("removed") is False
        and not d.get("file_id")
    ):  # a dialogue cut with no music yet: "music back" lays the brand's newest bed (free)
        beds = music_choices(db, project)
        if not beds:
            raise Refused(NO_BED)
        d = {"file_id": beds[0]["file_id"]}
    if d.get("quieter_db") is not None:
        n = float(d["quieter_db"])
        if not 0 <= n <= LOUDEST:
            raise Refused(f"Quieter by 0 to {LOUDEST:.0f} dB.")
        return {"quieter_db": round(n, 1)}, f"Music quieter by {n:g} dB under the voice", 0.0
    if d.get("gaps") in ("down", "rise"):
        said = "rises" if d["gaps"] == "rise" else "stays down"
        return {"gaps": d["gaps"]}, f"Music {said} when no one speaks", 0.0
    if d.get("loop") is not None:
        return (
            {"loop": bool(d["loop"])},
            "Music loops to fit" if d["loop"] else "Music plays once",
            0.0,
        )
    if d.get("removed") is not None:
        return (
            {"removed": bool(d["removed"])},
            "Music removed" if d["removed"] else "Music back",
            0.0,
        )
    if d.get("file_id"):
        name = _music_name(db, project, int(d["file_id"]))
        laid = tl["mode"] == "takes" and not tl["music"]  # a dialogue cut's first bed loops
        called = "" if name == "Music" else f" “{name}”"  # its prompt gave it no name
        return (
            {"file_id": int(d["file_id"]), "name": name, "removed": False, "loop": laid},
            f"A music bed{called} under the cut"
            if laid
            else f"Music swapped for{called or ' another bed'}",
            0.0,
        )
    raise Refused("Say how the music changes.")


def music_choices(db: Session, project: Project) -> list[dict]:
    """Music the cut can lay or swap to, newest first: a narrated video's, the brand's
    narration beds and songs; a dialogue (takes) cut's, the brand's beds only (instrumental:
    nothing sung over its lines). A song video's music is its song."""
    from app.models.script_library import Script, ScriptDraft

    voice, kind = song(db, project), narration.video_kind(db, project)
    if kind == "song" or (voice is not None and voice.kind != narration.KIND):
        return []
    if kind == "narrated" and voice is None:  # its music comes with its narration
        return []
    beds_only = voice is None
    takes = db.scalars(select(SongTake).join(ScriptDraft, SongTake.draft_id == ScriptDraft.id)
                       .join(Script, ScriptDraft.script_id == Script.id)
                       .where(Script.brand_id == project.brand_id,
                              Script.workspace_id == project.workspace_id)
                       .order_by(SongTake.id.desc()).limit(40))  # fmt: skip
    out = []
    for t in takes:
        if t.kind == narration.KIND and t.music_file_id:
            out.append({"file_id": t.music_file_id, "name": _bed_name(db, t)})
        elif t.kind != narration.KIND and t.file_id and not beds_only:
            out.append({"file_id": t.file_id, "name": (t.style_line or "A song")[:40]})
    return out


def _music_name(db: Session, project: Project, file_id: int) -> str:
    found = next((m for m in music_choices(db, project) if m["file_id"] == file_id), None)
    if found is None:
        raise Refused("That music isn't in this brand.")
    return found["name"]


def undo(db: Session, project: Project, edit_id: int | None = None) -> CutEdit:
    """Undo one edit (the newest, or the one named: the director's each have Undo)."""
    live = active(db, project)
    row = (next((e for e in live if e.id == edit_id), None) if edit_id is not None
           else (live or [None])[-1])  # fmt: skip
    if row is None:
        raise HTTPException(409 if edit_id is None else 404, "There's nothing to undo.")
    row.undone_at = utcnow()
    db.flush()
    keeps_every_word(db, timeline(db, project)[0])  # an undo never cuts a word either
    return row


def redoable(db: Session, project: Project) -> CutEdit | None:
    """The edit undone last, while nothing new was edited after it."""
    rows = every(db, project)
    gone = max((e for e in rows if e.undone_at), key=lambda e: (e.undone_at, e.id), default=None)
    if gone and not any(e.undone_at is None and e.created_at > gone.undone_at for e in rows):
        return gone
    return None


def redo(db: Session, project: Project) -> CutEdit:
    row = redoable(db, project)
    if row is None:
        raise HTTPException(409, "There's nothing to redo.")
    row.undone_at = None
    db.flush()
    keeps_every_word(db, timeline(db, project)[0])
    return row


def undo_all(db: Session, project: Project) -> None:
    """Back to the cut that plays: every edit since undone, every one in it back."""
    cut = newest(db, project)
    keep, now = set(cut.edit_ids or []) if cut else set(), utcnow()
    for n, e in enumerate(every(db, project)):
        if e.id in keep:
            e.undone_at = None
        elif e.undone_at is None:
            e.undone_at = now - timedelta(microseconds=n)  # Redo brings the oldest back first
    db.flush()
    keeps_every_word(db, timeline(db, project)[0])


GONE = "gone"  # a cancelled edit's piece: no piece has it, so it never lands (replay skips it)
LIBRARY = 24  # the brand's other videos' takes offered for a swap, newest first


def swaps(db: Session, user: User, project: Project, tl: dict, p: dict) -> list[dict]:
    """A piece's swap row: as it is ("In the cut"), its clip's other takes, the other clips'
    picked takes, and picked takes of the brand's other videos the person can see."""

    def one(take: ClipTake, said: str, kind: str) -> dict:
        return {"take_id": take.id, "file_id": take.file_id, "label": said, "kind": kind}

    clips = rows(db, project)
    out = [one(t, "In the cut", "in_cut") for t in [db.get(ClipTake, p["take_id"] or 0)] if t]
    mine = next((r for r in clips if r.clip_id == p["clip_id"]), None)
    takes = db.scalars(select(ClipTake).where(ClipTake.clip_id == (mine.id if mine else 0))
                       .order_by(ClipTake.number)) if mine else []  # fmt: skip
    out += [one(t, f"Take {t.number}", "take") for t in takes if t.id != p["take_id"]]
    out += [one(db.get(ClipTake, r.picked_take_id), label(r.clip_id), "clip") for r in clips
            if r.clip_id != p["clip_id"] and r.picked_take_id
            and r.picked_take_id != p["take_id"]]  # fmt: skip
    seen = select(Project.id).where(
        Project.brand_id == project.brand_id,
        Project.workspace_id == project.workspace_id,
        Project.id != project.id,
        Project.archived_at.is_(None),
        Project.aspect_ratio == project.aspect_ratio,  # the same shape (`_swap_source`)
    )
    if not user.is_owner:
        seen = seen.where(Project.created_by_id == user.id)
    picked = ProjectClip.picked_take_id == ClipTake.id
    others = db.execute(select(ClipTake, Project.name).join(ProjectClip, picked)
                        .join(Project, Project.id == ProjectClip.project_id)
                        .where(ProjectClip.project_id.in_(seen))
                        .order_by(ClipTake.id.desc()).limit(LIBRARY))  # fmt: skip
    out += [one(t, f"{name[:40]}, take {t.number}", "library") for t, name in others]
    return [s for s in out if s["kind"] == "in_cut"
            or _swappable(db, user, project, p, s["take_id"], tl)]  # fmt: skip


def _swappable(db: Session, user: User, project: Project, p: dict, take_id: int,
               tl: dict) -> bool:  # fmt: skip
    """A swap that would go through, so nothing's offered that a press refuses (rule 22): what
    `_swap_source` takes, and what keeps every word with this take in the piece."""
    swapped = {**p, "take_id": take_id, "whole": False,
               "from": p["from"] if synced(p) else 0.0}  # fmt: skip
    trial = {**tl, "pieces": [swapped if q["id"] == p["id"] else q for q in tl["pieces"]]}
    try:
        _swap_source(db, user, project, p, take_id, tl["mode"])
        keeps_every_word(db, trial)
    except Refused:
        return False
    return True


def for_director(db: Session, project: Project) -> dict | None:
    """The cut as the director reads it (<video>.timeline): each piece with when it plays and
    what's said over it, the presenter's spans, the music, and the edits with their ids (for
    undo); None before the first cut."""
    playing = newest(db, project)
    if playing is None:
        return None
    tl, lost = timeline(db, project)
    words = tl["words"]
    live, kept = {e.id for e in active(db, project)}, set(playing.edit_ids or [])
    return {
        "cut": playing.number, "length": tl["length"], "changes": len(live ^ kept),
        "pieces": [{"piece": p["id"], "clip_id": p["clip_id"], "start": p["start"],
                    "end": p["end"], "take_id": p["take_id"], "source": p["source"],
                    "lipsync": bool(p.get("lipsync")),  # a talker's: its edges barely move
                    "said": " ".join(w["word"] for w in words
                                     if p["start"] <= (w["start"] + w["end"]) / 2 < p["end"])}
                   for p in tl["pieces"]],
        "presenter": [{k: s[k] for k in ("start", "end", "side", "size", "hidden")}
                      for s in tl["presenter"]["spans"]] if tl["presenter"] else None,
        "music": {k: tl["music"][k] for k in ("quieter_db", "gaps", "loop", "removed")}
        if tl["music"] else None,
        "edits": [{"id": e.id, "said": e.said, "at": e.at, "director": e.director,
                   "undone": e.undone_at is not None or e.id in lost}
                  for e in every(db, project)][-12:],
    }  # fmt: skip


def follow_clips(db: Session, project: Project, names: dict[str, str], before: set[str]) -> None:
    """The plan's clips were renumbered (a split: c5 is now c6): each cut edit, undone ones
    too (Redo and Undo all bring them back), follows its clip to its new id, and so does a
    swap's source clip. One on a clip that was regrouped (the split clip itself, written
    again) is undone and can't land again: never on whichever clip now has its old id."""
    gone, now = before - set(names), utcnow()
    for e in every(db, project):
        piece, source = (e.data or {}).get("piece"), (e.data or {}).get("source", "")
        if not piece:
            continue  # a span of the cut or the music: on the voice's clock, not a clip's
        old, _, tail = piece.partition(".")
        if old in names and names[old] != old:
            e.data = {**e.data, "piece": names[old] + (f".{tail}" if tail else "")}
            e.said = e.said.replace(label(old), label(names[old]), 1)
        elif old in gone:
            e.data, e.undone_at = {**e.data, "piece": GONE}, e.undone_at or now
        was = "c" + source.removeprefix("Clip ") if source.startswith("Clip ") else ""
        if names.get(was, was) != was:  # swapped for another clip of this video, renumbered
            e.data = {**e.data, "source": label(names[was])}
            e.said = e.said.replace(f"for {source.lower()}", f"for {label(names[was]).lower()}")


def follow_breakdown(db: Session, project: Project, old: dict, new: dict) -> None:
    """Another breakdown in use (an earlier one used again, an edited one saved): the cut's
    edits follow their clips by their shots, as after a split."""
    from app.cast_roles import _renamed
    from app.prompts.schemas import Breakdown

    was, now = Breakdown.model_validate(old), Breakdown.model_validate(new)
    follow_clips(db, project, _renamed(was, now), {c.id for c in was.clips})
