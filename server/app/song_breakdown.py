"""Song ads: the breakdown timed to the video's song (flows S6, V2, V2a).

The AI writes a SongBreakdown (prompts.schemas: each shot's song_start, song_end and sung).
Every other step reads a plain Breakdown, so a row keeps the plan as a Breakdown and the song
part beside it, in data["song"] = {"take_id", "shots": {shot id: {start, end, sung}}}. A new
row (an edit, a fix, a recast) carries the song part on for the shots it keeps; when the
video's take changes, the times move to the new take for free (reflow), and the shots keep
their lines and Sung marks."""

import bisect

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models.breakdowns import BreakdownVersion
from app.models.projects import Project
from app.models.songs import SongTake
from app.prompts.schemas import Breakdown, SongBreakdown


def take_for(db: Session, project: Project) -> SongTake | None:
    return db.get(SongTake, project.song_take_id) if project.song_take_id else None


def timing_used(take: SongTake) -> dict:
    """The take's timing, cut to its trim ("Use the first 0:55") if it has one."""
    timing = take.timing or {}
    end = take.trim_to
    if not end:
        return timing
    sections = [{**s, "end": min(s["end"], end),
                 "cuts": [c for c in s.get("cuts", []) if c < end]}
                for s in timing.get("sections", []) if s["start"] < end]  # fmt: skip
    return {**timing, "seconds": end, "beats": [b for b in timing.get("beats", []) if b < end],
            "lines": [ln for ln in timing.get("lines", []) if ln["start"] < end],
            "sections": sections}  # fmt: skip


def split(bd: SongBreakdown, take_id: int) -> tuple[Breakdown, dict]:
    """The AI's song breakdown as the plan every step reads, plus its song part."""
    shots = {s.id: {"start": s.song_start, "end": s.song_end, "sung": s.sung}
             for scene in bd.scenes for s in scene.shots}  # fmt: skip
    return Breakdown.model_validate(bd.model_dump()), {"take_id": take_id, "shots": shots}


def joined(bd: Breakdown, song: dict) -> SongBreakdown:
    """The plan with its song part, for the song check and the song steps. A shot the song
    part doesn't know (made by an edit) starts and ends where the shot before it ended, so
    the check names the gap to fix."""
    data, at = bd.model_dump(), 0.0
    for scene in data["scenes"]:
        for shot in scene["shots"]:
            timed = song["shots"].get(shot["id"], {"start": at, "end": at, "sung": False})
            shot.update(song_start=timed["start"], song_end=timed["end"], sung=timed["sung"])
            at = timed["end"]
    return SongBreakdown.model_validate(data)


def newest_song(db: Session, project_id: int) -> dict | None:
    data = db.scalar(
        select(BreakdownVersion.data).where(BreakdownVersion.project_id == project_id)
        .order_by(BreakdownVersion.id.desc()).limit(1)
    )  # fmt: skip
    return (data or {}).get("song")


@event.listens_for(BreakdownVersion, "before_insert")
def _carry(mapper, connection, row: BreakdownVersion) -> None:
    """A new row without a song part takes the newest row's, for the shots it keeps."""
    if "song" in row.data:
        return
    with Session(bind=connection) as db:
        song = newest_song(db, row.project_id)
    if song:
        kept = {s["id"] for scene in row.data["scenes"] for s in scene["shots"]}
        shots = {k: v for k, v in song["shots"].items() if k in kept}
        row.data = {**row.data, "song": {**song, "shots": shots}}


def _move(t: float, old: list[dict], new: list[dict], new_end: float) -> float:
    """Where time `t` of the old take falls in the new one: the same share of the same
    section (by order), so a shot over the second chorus stays over the second chorus."""
    starts = [s["start"] for s in old]
    k = max(bisect.bisect_right(starts, t) - 1, 0)
    if k >= len(new):
        return new_end
    a, b = old[k]["start"], old[k]["end"]
    share = (t - a) / (b - a) if b > a else 0.0
    return new[k]["start"] + share * (new[k]["end"] - new[k]["start"])


def reflow(song: dict, old: dict, new: dict, take_id: int) -> dict:
    """The song part moved from the old take's timing to the new one's: each shot edge to
    the same place in its section, on the new take's nearest beat, back to back to the end."""
    order = sorted(song["shots"].items(), key=lambda kv: kv[1]["start"])
    beats, end = new.get("beats", []), new["seconds"]
    starts = []
    for _, timed in order:
        t = _move(timed["start"], old.get("sections", []), new.get("sections", []), end)
        t = min(beats, key=lambda b: abs(b - t)) if beats else t
        starts.append(max(t, starts[-1] if starts else 0.0))
    starts[0] = 0.0
    ends = [*starts[1:], end]
    shots = {sid: {**timed, "start": round(a, 2), "end": round(b, 2)}
             for (sid, timed), a, b in zip(order, starts, ends, strict=True)}  # fmt: skip
    return {"take_id": take_id, "shots": shots}


def follow_take(db: Session, project: Project, user_id: int) -> BreakdownVersion | None:
    """The video's take changed: its newest song breakdown, retimed to the new take, as a new
    row (free, no model call). Stills and clips carry over; nothing is redone."""
    from app import breakdown, cast_roles
    from app.models.scripts import ScriptVersion

    row = db.scalar(
        select(BreakdownVersion).where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc()).limit(1)
    )  # fmt: skip
    song = (row.data if row else {}).get("song")
    old, new = db.get(SongTake, song["take_id"]) if song else None, take_for(db, project)
    if not old or not new or old.id == new.id:
        return None
    moved = reflow(song, timing_used(old), timing_used(new), new.id)
    plan = Breakdown.model_validate(row.data)
    text = db.scalar(
        select(ScriptVersion.text).where(ScriptVersion.project_id == project.id,
                                         ScriptVersion.version == row.script_version)
    ) or ""  # fmt: skip
    again = BreakdownVersion(
        project_id=project.id, script_version=row.script_version, source="edit",
        data={**plan.model_dump(), "song": moved}, created_by_id=user_id,
        problems=breakdown.problems(db, project, text, plan, moved),
    )  # fmt: skip
    again.kept = breakdown.carry_kept(row.kept, again.problems)
    db.add(again)
    db.flush()
    cast_roles.carry_frames(db, project, row, again)
    cast_roles.carry_clips(db, project, row, again)
    return again


def guessed(bd: Breakdown, text: str, timing: dict) -> set[str]:
    """Shots one of whose sung lines wasn't heard in the take, so its time is a guess
    ("Timing guessed"). Script line numbers count every line of the lyrics; the timing's
    lines are the sung ones, in the same order (check.sung_lines)."""
    from app.prompts.check import LIP_SYNC, SECTION

    sung, n = {}, 0
    for number, line in enumerate(text.splitlines(), 1):
        if not SECTION.match(line) and LIP_SYNC.sub("", line).strip():
            sung[number], n = n, n + 1
    heard = [ln.get("heard", 1) for ln in timing.get("lines", [])]
    unheard = {num for num, k in sung.items() if k < len(heard) and heard[k] == 0}
    return {s.id for scene in bd.scenes for s in scene.shots if unheard & set(s.script_lines)}
