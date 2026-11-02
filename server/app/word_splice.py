"""Splice a word (Reed, after his test: "fogo" for fomo in every style): the brand's name said
wrong in a take is covered, at stitch time, by a clean copy of it in the same voice from
another take, with a short crossfade either side. Free (ffmpeg on our server); the takes and
their approvals are untouched. Only the brand's name, as the words check flags it ("name");
only a clip with one speaker, from a take whose clip has that same one speaker. The director
picks from what the server found (`state`), never a time of its own."""

import re
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project

KEY = "splices"  # on a take's made_with: [{word, at, from_take, from}]
FADE = 0.03  # seconds of crossfade either side
STRETCH = 0.15  # the copy may be sped up or slowed down this much to fit, no more
MAX = 4  # splices a take may have
NO_COPY = ("Refused: there's no clean “{w}” in this voice in the video's takes; redo the clip "
           "with a note on how it's said.")  # fmt: skip
TOO_LONG = ("Refused: “{w}” in {c} can't be fitted without changing its speed too much; redo "
            "the clip with a note on how it's said.")  # fmt: skip
NOT_BRAND = "Refused: only the brand's name is spliced."
NOTHING = "Refused: the words check didn't hear “{w}” said wrong in {c}'s picked take."
TOO_MANY = f"Refused: a take can have {MAX} spliced words at most."


def _bare(word: str) -> str:
    return re.sub(r"[^a-z']", "", word.lower())


def spliced(take: ClipTake | None) -> list[dict]:
    return list((take.made_with or {}).get(KEY) or []) if take else []


def _heard(db: Session, take: ClipTake) -> tuple[list[dict], str]:
    """The take's words, each with when (its words check's listen), and the brand it checked."""
    from app.item_checks import latest

    row = latest(db, "words", [take.id]).get(take.id)
    job = db.get(Job, row.job_id) if row and row.job_id else None
    if job is None or row.status != "done":
        return [], ""
    lines = (job.output or {}).get("heard") or []
    return [w for line in lines for w in line.get("words") or []], job.input.get("brand", "")


def _voice(db: Session, row: ProjectClip) -> str | None:
    """The clip's one speaker, or None when nobody or more than one speaks in it."""
    from app.models.breakdowns import BreakdownVersion

    data = db.get(BreakdownVersion, row.breakdown_id).data
    ids = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] == row.clip_id), [])
    shots = [s for sc in data.get("scenes", []) for s in sc.get("shots", []) if s["id"] in ids]
    who = {(s.get("speaker") or "").strip().lower() for s in shots if s.get("line")}
    return who.pop() if len(who) == 1 and "" not in who else None


def wrong(db: Session, take: ClipTake) -> list[dict]:
    """The brand's name said wrong in the take: [{word (as the brand spells it), at}]."""
    from app.take_words import _off_by_one

    words, brand = _heard(db, take)
    name = _bare(brand)
    said = [(w, _bare(w["word"])) for w in words]
    return [{"word": brand, "at": [w["start"], w["end"]]} for w, b in said
            if name and b != name and _off_by_one(b, name)]  # fmt: skip


def _clean(db: Session, take: ClipTake, name: str) -> list[list[float]]:
    words, _ = _heard(db, take)
    return [[w["start"], w["end"]] for w in words if _bare(w["word"]) == name]


def _fits(at: list[float], copy: list[float]) -> bool:
    want, have = at[1] - at[0], copy[1] - copy[0]
    return want > 0 and have > 0 and abs(have / want - 1) <= STRETCH


def find(db: Session, row: ProjectClip, word: str, at: list[float]) -> dict | str:
    """A clean copy for the wrong word at `at` in the clip's picked take, or why there's none:
    the clip's other takes first, then the picked takes of clips with the same one speaker."""
    voice = _voice(db, row)
    name = _bare(word)
    if voice is None:
        return NO_COPY.format(w=word)
    others = db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id,
                                               ClipTake.id != row.picked_take_id)
                        .order_by(ClipTake.id.desc())).all()  # fmt: skip
    clips = db.scalars(select(ProjectClip).where(ProjectClip.project_id == row.project_id,
                                                 ProjectClip.id != row.id,
                                                 ProjectClip.picked_take_id.is_not(None))
                       .order_by(ProjectClip.id)).all()  # fmt: skip
    others += [db.get(ClipTake, c.picked_take_id) for c in clips if _voice(db, c) == voice]
    copies = [(t, span) for t in others for span in _clean(db, t, name)]
    if not copies:
        return NO_COPY.format(w=word)
    for take, span in copies:
        if _fits(at, span):
            return {"word": word, "at": at, "from_take": take.id, "from": span}
    return TOO_LONG.format(w=word, c=row.clip_id)


def state(db: Session, row: ProjectClip) -> dict:
    """For the director's turn, per clip: what's spliced, what can be, and what can't."""
    take = db.get(ClipTake, row.picked_take_id) if row.picked_take_id else None
    done = spliced(take)
    out = {
        "splices": [
            {"word": s["word"], "at": s["at"], "from_take_id": s["from_take"]} for s in done
        ],  # fmt: skip
        "can_splice": [],
        "no_copy": [],
    }
    for bad in wrong(db, take) if take else []:
        if any(s["at"] == bad["at"] for s in done):
            continue
        found = find(db, row, bad["word"], bad["at"])
        out["can_splice" if isinstance(found, dict) else "no_copy"].append(bad)
    return out


def splice(db: Session, project: Project, row: ProjectClip, word: str) -> str:
    """The director's splice_word: the first wrong `word` in the clip's picked take that has a
    clean copy; the cut is out of date until it's made again (its label changes)."""
    from app.models.brands import Brand

    brand = db.get(Brand, project.brand_id)
    if _bare(word) != _bare(brand.name if brand else ""):
        return NOT_BRAND
    take = db.get(ClipTake, row.picked_take_id) if row.picked_take_id else None
    done = spliced(take)
    bad = [b for b in (wrong(db, take) if take else [])
           if not any(s["at"] == b["at"] for s in done)]  # fmt: skip
    if not bad:
        return NOTHING.format(w=word, c=row.clip_id)
    if len(done) >= MAX:
        return TOO_MANY
    found = find(db, row, word, bad[0]["at"])
    if isinstance(found, str):
        return found
    take.made_with = {**(take.made_with or {}), KEY: [*done, found]}
    source = db.scalar(select(ProjectClip.clip_id).join(ClipTake, ClipTake.clip_id ==
                                                        ProjectClip.id)
                       .where(ClipTake.id == found["from_take"]))  # fmt: skip
    return f"Spliced “{word}” into {row.clip_id} from {source}."


def labels(clip: ProjectClip, take: ClipTake | None) -> list[str]:
    """How the final video remembers its splices, so a new one shows as changes waiting."""
    return [f"{clip.clip_id}/splice:{s['at'][0]}-{s['at'][1]}" for s in spliced(take)]


def apply(video: bytes, splices: list[dict], source) -> bytes:
    """The take with each wrong word's sound replaced by its copy (`source(take_id)` gives
    that take's video), fitted to the same length, with FADE crossfades; picture copied."""
    for s in splices:
        video = _one(video, source(s["from_take"]), s["at"], s["from"])
    return video


def _one(video: bytes, other: bytes, at: list[float], copy: list[float]) -> bytes:
    start, end = at
    a, b = copy
    pace = (b - a) / (end - start)  # atempo: >1 plays faster, so the copy fits the gap
    length = end - start
    duck = (f"volume=eval=frame:volume='if(between(t,{start},{end}),"
            f"max(0,max(({start}+{FADE}-t)/{FADE},(t-({end}-{FADE}))/{FADE})),1)'")  # fmt: skip
    insert = (f"atrim={a}:{b},asetpts=PTS-STARTPTS,atempo={pace:.4f},"
              f"afade=t=in:d={FADE},afade=t=out:st={max(0.0, length - FADE):.3f}:d={FADE},"
              f"adelay={int(start * 1000)}:all=1")  # fmt: skip
    mix = "amix=inputs=2:duration=first:normalize=0"
    graph = f"[0:a]{duck}[base];[1:a]{insert}[word];[base][word]{mix}[out]"
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(video)
        (folder / "copy.mp4").write_bytes(other)
        command = ["ffmpeg", "-v", "error", "-y", "-i", "in.mp4", "-i", "copy.mp4",
                   "-filter_complex", graph, "-map", "0:v", "-map", "[out]", "-c:v", "copy",
                   "-c:a", "aac", "out.mp4"]  # fmt: skip
        subprocess.run(command, cwd=folder, check=True, capture_output=True,  # noqa: S603
                       timeout=120)  # fmt: skip
        return (folder / "out.mp4").read_bytes()
