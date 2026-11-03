"""Song ads: the breakdown timed to the video's song (flows S6, V2, V2a).

The AI writes a SongBreakdown (prompts.schemas: each shot's song_start, song_end and sung).
Every other step reads a plain Breakdown, so a row keeps the plan as a Breakdown and the song
part beside it, in data["song"] = {"take_id", "shots": {shot id: {start, end, sung}}}. A new
row (an edit, a fix, a recast) carries the song part on for the shots it keeps; when the
video's take changes, the times move to the new take for free (reflow), and the shots keep
their lines and Sung marks."""

import bisect
import math
import re

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.projects import Project
from app.models.songs import SongTake
from app.prompts.schemas import Breakdown, SongBreakdown

MIN_CLIP = 4  # seconds: a shorter span is made 4 s long and cut to it (Song-Producer)
PEOPLE_MAX = 16  # seconds: a clip with people in it is split past this


def take_for(db: Session, project: Project) -> SongTake | None:
    return db.get(SongTake, project.song_take_id) if project.song_take_id else None


def split(bd: SongBreakdown, take_id: int, broll: bool = False) -> tuple[Breakdown, dict]:
    """The AI's song breakdown as the plan every step reads, plus its song part, the shots'
    and clips' lengths taken from the song (`fit`; `broll`: a narration's)."""
    shots = {s.id: {"start": s.song_start, "end": s.song_end, "sung": s.sung}
             for scene in bd.scenes for s in scene.shots}  # fmt: skip
    song = {"take_id": take_id, "shots": shots}
    return Breakdown.model_validate(fit({**bd.model_dump(), "song": song}, broll)), song


def fit(data: dict, broll: bool = False) -> dict:
    """The song is the clock (V2, V6): each shot lasts its time in the song and each clip its
    shots' span, rounded up to whole seconds, whatever the plan said (the stand-in counted
    spoken words: a 0:24 song read "1 clip · 14 s"). A clip over the video model's limit
    keeps it: the breakdown check names it, never cut to fit. `data` is a plan with its
    song part; shots the song part doesn't know keep their own. `broll`: under a narration,
    a shot too short to be a clip is a clip of its own (`_apart`)."""
    timed = (data.get("song") or {}).get("shots") or {}
    if not timed:
        return data
    scenes = [{**sc, "shots": [{**sh, "seconds": round(timed[sh["id"]]["end"]
                                                      - timed[sh["id"]]["start"], 2)}
                               if sh["id"] in timed else sh for sh in sc["shots"]]}
              for sc in data.get("scenes", [])]  # fmt: skip
    peopled = {sh["id"] for sc in data.get("scenes", []) for sh in sc.get("shots", [])
               if sh.get("character_ids")}  # fmt: skip
    clips = []
    for clip in data.get("clips", []):
        whole = _apart(clip, timed) if broll else [clip]
        for part in (p for c in whole for p in _split(c, timed, peopled)):
            known = [timed[s] for s in part.get("shot_ids", []) if s in timed]
            if known:
                span = max(t["end"] for t in known) - min(t["start"] for t in known)
                part = {**part, "seconds": max(MIN_CLIP, math.ceil(span - 0.01))}  # its span
            clips.append(part)
    return {**data, "scenes": scenes, "clips": clips}


def _apart(clip: dict, timed: dict) -> list[dict]:
    """F7 (Reed, 3 Nov: "generating several clips and splicing them together"): a B-roll clip
    with a shot shorter than a clip can be (MIN_CLIP) is made as one clip a shot, each at least
    MIN_CLIP long and cut to its shot's time in the edit (clip_takes.song_cut); "c3", "c3b"."""
    ids = clip.get("shot_ids", [])
    short = [s for s in ids if s in timed and timed[s]["end"] - timed[s]["start"] < MIN_CLIP]
    if len(ids) < 2 or not short:
        return [clip]
    return [{**clip, "id": clip["id"] + ("" if n == 0 else chr(ord("a") + n)), "shot_ids": [s]}
            for n, s in enumerate(ids)]  # fmt: skip


def _split(clip: dict, timed: dict, peopled: set[str]) -> list[dict]:
    """A clip with people in it over PEOPLE_MAX seconds of song, split at its shots into
    pieces of at most that (Song-Producer: faces hold up only so long); "c3", "c3b", "c3c"."""
    ids = [s for s in clip.get("shot_ids", []) if s in timed]
    if not ids or not peopled & set(ids):
        return [clip]
    if timed[ids[-1]]["end"] - timed[ids[0]]["start"] <= PEOPLE_MAX:
        return [clip]
    groups: list[list[str]] = [[]]
    for s in ids:
        start = timed[groups[-1][0]]["start"] if groups[-1] else timed[s]["start"]
        if groups[-1] and timed[s]["end"] - start > PEOPLE_MAX:
            groups.append([])
        groups[-1].append(s)
    return [{**clip, "id": clip["id"] + ("" if n == 0 else chr(ord("a") + n)),
             "shot_ids": group} for n, group in enumerate(groups)]  # fmt: skip


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


@event.listens_for(BreakdownVersion, "before_insert")
def _carry(mapper, connection, row: BreakdownVersion) -> None:
    """A new row without a song part (an edit, a fix, a recast) takes the newest row's, its
    shots packed back to back over the same song, free (rule 22: an edit never leaves a gap
    to fix by hand): see `repack`. A shot an edit brings back (Undo) gets its earlier times
    from the rows before, so an Undo is exact. Only a row that brings its own song part (the
    AI's plan, a new take) is word-snapped: an edit never moves another shot's time."""
    with Session(bind=connection) as db:
        if row.data.get("song"):
            take = db.get(SongTake, row.data["song"].get("take_id") or 0)
            row.data = snap(row.data, take.timing or {} if take else {})
        else:
            order = [s["id"] for scene in row.data["scenes"] for s in scene["shots"]]
            if song := carried(db, row.project_id, order):
                row.data = {**row.data, "song": song}
        take = db.get(SongTake, (row.data.get("song") or {}).get("take_id") or 0)
        broll = bool(take and take.kind == "narration")  # every shot under a narration
    if row.data.get("song"):  # whichever way it came (a plan, an edit, a new take): the song's
        row.data = fit(row.data, broll)


LEAD = 0.1  # seconds: a shot that shows what a word names lands just before it's sung
MIN_SNAP = 1.0  # seconds: a snap never leaves either shot shorter than this
NUMBERS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
           "fourteen fifteen sixteen seventeen eighteen nineteen twenty").split()  # fmt: skip
SKIP = {"the", "and", "with", "her", "his", "its", "for", "from", "into", "onto", "our",
        "their", "they", "then", "this", "that", "shot", "close", "wide", "camera", "are",
        "was", "who", "she", "him", "them", "out", "off", "all", "one's"}  # fmt: skip


def _key(word: str) -> str:
    """A word as both sides compare it: lower case, "4" and "four" alike, a plural's s off."""
    w = re.sub(r"[^\w']", "", word.lower()).removesuffix("'s")
    if w.isdigit():
        return NUMBERS[int(w)] if int(w) < len(NUMBERS) else w
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def _named(shot: dict) -> set[str]:
    """The things a shot shows, by name: its action's words and its screen figure's."""
    figure = " ".join(str(v) for v in (shot.get("screen_figure") or {}).values())
    found = re.findall(r"\d+|[a-z']+", f"{shot.get('action') or ''} {figure}".lower())
    return {_key(w) for w in found if w.isdigit() or (len(w) > 2 and w not in SKIP)}


def snap(data: dict, timing: dict) -> dict:
    """Word-snap (P1): a B-roll shot that shows a thing its line names starts just before
    that word is sung, not at the line's start (Reed's scorecard showed a second early before
    "four"). The shot before it in the same clip ends there instead, so a clip's span never
    moves, and neither shot drops under MIN_SNAP. The first such word sung inside the shot
    counts; snapping again changes nothing. Words are the take's measured ones (timing)."""
    song, words = data.get("song"), timing.get("words") or []
    if not song or not words:
        return data
    shots = {sh["id"]: sh for sc in data.get("scenes", []) for sh in sc.get("shots", [])}
    times = {sid: dict(t) for sid, t in song["shots"].items()}
    for clip in data.get("clips", []):
        ids = [s for s in clip.get("shot_ids", []) if s in times and s in shots]
        for prev, sid in zip(ids, ids[1:], strict=False):
            here, before, named = times[sid], times[prev], _named(shots[sid])
            if here.get("sung") or before["end"] != here["start"] or not named:
                continue
            word = next((w for w in words if here["start"] < w["start"] < here["end"]
                         and _key(w["word"]) in named), None)  # fmt: skip
            at = round(word["start"] - LEAD, 2) if word else here["start"]
            if at > here["start"] and at - before["start"] >= MIN_SNAP <= here["end"] - at:
                before["end"] = here["start"] = at
    return {**data, "song": {**song, "shots": times}}


def slice_of(data: dict, clip_id: str) -> dict | None:
    """The piece of the song a clip of this plan covers: {start, end, sung_shots} (V6)."""
    song = data.get("song")
    shots = next((c["shot_ids"] for c in data.get("clips", []) if c["id"] == clip_id), [])
    timed = [(s, song["shots"][s]) for s in shots if song and s in song["shots"]]
    if not timed:
        return None
    return {"start": min(t["start"] for _, t in timed), "end": max(t["end"] for _, t in timed),
            "sung_shots": [s for s, t in timed if t.get("sung")]}  # fmt: skip


@event.listens_for(ProjectClip, "before_insert")
@event.listens_for(ProjectClip, "before_update")
def _slice(mapper, connection, clip: ProjectClip) -> None:
    """A clip's song slice follows the breakdown row it's made from, whichever route set it."""
    if clip.breakdown_id:
        data = connection.scalar(select(BreakdownVersion.data)
                                 .where(BreakdownVersion.id == clip.breakdown_id))  # fmt: skip
        clip.song_slice = slice_of(data or {}, clip.clip_id)


def carried(db: Session, project_id: int, order: list[str]) -> dict | None:
    """The song part a new plan with these shots (in order) gets from the rows before it:
    each shot's newest time on the same take, packed back to back (`repack`)."""
    datas = db.scalars(
        select(BreakdownVersion.data).where(BreakdownVersion.project_id == project_id)
        .order_by(BreakdownVersion.id.desc()).limit(HISTORY)
    ).all()  # fmt: skip
    songs = [d["song"] for d in datas if d.get("song")]
    if not songs:
        return None
    take_id, known = songs[0]["take_id"], {}
    for song in reversed([s for s in songs if s["take_id"] == take_id]):  # newest wins
        known.update(song["shots"])
    end = max(t["end"] for t in songs[0]["shots"].values())
    timed = {sid: known[sid] for sid in order if sid in known}
    return {"take_id": take_id, "shots": repack(order, timed, end)}


HISTORY = 50  # rows looked back through for a shot an Undo brings back
MIN_SHOT = 0.5  # seconds: a shot an edit packs in never gets less


def repack(order: list[str], timed: dict[str, dict], end: float) -> dict[str, dict]:
    """The shots in `order`, back to back from 0 to `end`. A timed shot keeps where its own
    time ends (its place in the song; `own_end`, never a stretch it was given); a deleted
    shot's time goes to the shot after it; shots with no time (added by an edit), or whose
    own end is before an earlier shot's (moved by an edit), share the stretch up to the next
    timed shot's end, so no shot is ever 0 s."""
    own, last = {}, 0.0
    for sid in order:  # in order, each own end after the one before
        if sid in timed and (stop := timed[sid].get("own_end", timed[sid]["end"])) > last:
            own[sid], last = stop, stop
    out, at, k = {}, 0.0, 0
    while k < len(order):
        sid = order[k]
        if sid in own:
            stop = end if k == len(order) - 1 else own[sid]
            shot = {**timed[sid], "start": round(at, 2), "end": round(stop, 2)}
            shot.pop("own_end", None)
            if round(stop, 2) != own[sid]:  # stretched: remember where its own time ends
                shot["own_end"] = own[sid]
            out[sid] = shot
            at, k = stop, k + 1
            continue
        run = k
        while run < len(order) and order[run] not in own:  # the untimed shots together
            run += 1
        stop = end if run == len(order) else own[order[run]]
        group = order[k:run]
        if stop - at < MIN_SHOT * len(group) and k:  # no room: share the shot before's stretch
            group, at = [order[k - 1], *group], out[order[k - 1]]["start"]
        share = max(stop - at, 0) / (len(group) + (run < len(order)))
        for sid in group:
            sung = timed.get(sid, {}).get("sung", False)
            out[sid] = {"start": round(at, 2), "end": round(at + share, 2), "sung": sung}
            if sid in own:  # the shot before, now sharing: it keeps its own end for Undo
                out[sid]["own_end"] = own[sid]
            at += share
        k = run
    return out


def _anchors(old: dict, new: dict) -> list[tuple[float, float]]:
    """Matching points of the two takes, in time order: the start, each sung line's measured
    start and end (the same lyrics, so line n is line n), and the end. When the line lists
    don't match, each section's start and end instead."""
    pairs = list(zip(old.get("lines", []), new.get("lines", []), strict=False))
    if not pairs or len(old.get("lines", [])) != len(new.get("lines", [])):
        pairs = list(zip(old.get("sections", []), new.get("sections", []), strict=False))
    points = [(0.0, 0.0)]
    for a, b in pairs:
        points += [(a["start"], b["start"]), (a["end"], b["end"])]
    points.append((old["seconds"], new["seconds"]))
    kept = []
    for x, y in sorted(points):  # never backwards, so the shots stay in order
        if not kept or (x > kept[-1][0] and y >= kept[-1][1]):
            kept.append((x, y))
    return kept


def _move(t: float, anchors: list[tuple[float, float]]) -> float:
    """Where time `t` of the old take falls in the new one: an edge on a line's start or end
    lands on that line's start or end in the new take; between them, the same share."""
    xs = [x for x, _ in anchors]
    k = min(max(bisect.bisect_right(xs, t) - 1, 0), len(anchors) - 2)
    (x0, y0), (x1, y1) = anchors[k], anchors[k + 1]
    return y0 + (t - x0) / (x1 - x0) * (y1 - y0) if x1 > x0 else y0


def reflow(song: dict, old: dict, new: dict, take_id: int) -> dict:
    """The song part moved from the old take's timing to the new one's by the measured line
    times (the line clock, so no shot newly cuts a line), back to back to the new end."""
    order = sorted(song["shots"].items(), key=lambda kv: kv[1]["start"])
    anchors, end = _anchors(old, new), new["seconds"]
    starts = []
    for _, timed in order:
        starts.append(max(_move(timed["start"], anchors), starts[-1] if starts else 0.0))
    starts[0] = 0.0
    ends = [*starts[1:], end]
    shots = {sid: {**timed, "start": round(a, 2), "end": round(b, 2)}
             for (sid, timed), a, b in zip(order, starts, ends, strict=True)}  # fmt: skip
    return {"take_id": take_id, "shots": shots}


def follow_take(db: Session, project: Project, user_id: int) -> BreakdownVersion | None:
    """The video's take changed: its newest song breakdown, retimed to the new take, as a new
    row (free, no model call). Stills carry over; a clip whose shots moved in the song is out
    of date (made for the old take's slice). Going back to an earlier take (Undo) makes the
    clips made for it current again."""
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
    moved = reflow(song, old.timing or {}, new.timing or {}, new.id)
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
    _current_clips(db, project, again)
    return again


def _current_clips(db: Session, project: Project, row: BreakdownVersion) -> None:
    """The clips made for exactly these song times move to `row` (current): those whose
    shots didn't move (B-roll only: a Sung clip lip-syncs its own take's singing), and, after
    an Undo, those made for the take before. Any other clip
    stays on the row it was made from, out of date (it holds the old take's slice)."""
    from app.models.clips import ProjectClip

    now = {c.id: c.shot_ids for c in Breakdown.model_validate(row.data).clips}
    times = row.data["song"]["shots"]
    for clip in db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)):
        made = db.get(BreakdownVersion, clip.breakdown_id)
        was = (made.data.get("song") or {}).get("shots", {}) if made else {}
        then = {c.id: c.shot_ids for c in Breakdown.model_validate(made.data).clips} if made else {}
        shots = now.get(clip.clip_id)
        same_take = (made.data.get("song") or {}).get("take_id") == row.data["song"]["take_id"]
        sung = any(times.get(s, {}).get("sung") for s in shots or [])
        if (
            shots
            and then.get(clip.clip_id) == shots
            and (same_take or not sung)  # a Sung clip lip-syncs its own take only
            and all(was.get(s) == times.get(s) for s in shots)
        ):
            clip.breakdown_id = row.id


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
