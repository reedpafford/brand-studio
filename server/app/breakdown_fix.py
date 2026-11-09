"""One-click fixes for a breakdown's problems (Reed, 2026-10-26, DECISIONS #520; spec
one-click-fixes.md §1-2): free, no model call. A missing script line goes into the shot that
holds the lines around it, a changed line gets the script's words back, the clips are fitted
to the shots again, and a name the video doesn't have is taken out of a shot."""

import math
import re

from app.prompts import without_notes
from app.prompts.check import DIALOGUE, TAG, _words
from app.prompts.schemas import Breakdown

KINDS = {  # the problem as said (advice.plain), and its fix
    "add_line": re.compile(r"(?i)^line (\d+) is in no shot$"),
    "restore_line": re.compile(r"(?i)^shot ([\w.]+): line differs from the script$"),
    "recover_clips": re.compile(
        r"(?i)^(clips don't cover the shots once each, in order|clip \w+: [\d.]+ s is "
        r"shorter than its shots)$"
    ),
    "fix_cast": re.compile(r"^Check the cast: "),  # QA-Live: no blocking line without its fix
    "split_clip": re.compile(r"(?i)^clip (c\d+): (\d+) s is outside \d+–(\d+) s$"),
}
LABELS = {
    "add_line": "Add it to a shot",
    "restore_line": "Use the script's words",
    "recover_clips": "Fit the clips to the shots",
    "fix_cast": "Put the right cast in each shot",
    "split_clip": "Split the clip",
}


def too_long(problems: list[str]) -> list[str]:
    """The clips longer than the video model makes ("c4"), from a breakdown's problems."""
    return [KINDS["split_clip"].match(p)[1] for p in problems if kind(p) == "split_clip"]


def kind(problem: str) -> str | None:
    k = next((k for k, pattern in KINDS.items() if pattern.match(problem)), None)
    if k == "split_clip" and (m := KINDS[k].match(problem)) and int(m[2]) <= int(m[3]):
        return None  # too short: only too long is split
    return k


def fixes(problems: list[str], data: dict | None = None, script: str = "") -> list[dict]:
    """The fix each problem has, for its button: [{problem, kind, label}]. With the
    breakdown (`data`), a clip of one shot is offered Split only when the `script` lets its
    shot be cut at a sentence break (Flow-QA #1013: one sentence can't be)."""

    def split_one(p: str, k: str) -> bool:
        if k != "split_clip" or data is None:
            return False
        m = KINDS[k].match(p)
        clip = next((c for c in data.get("clips", []) if c["id"] == m[1]), None)
        if clip is None:
            return False
        if not script:  # no words to cut at: only between shots
            return len(clip["shot_ids"]) < 2
        return split_into(data, script, m[1], 1, int(m[3])) < 2  # offered only when it works

    return [{"problem": p, "kind": k, "label": LABELS[k]}
            for p in problems if (k := kind(p)) and not split_one(p, k)]  # fmt: skip


def _said(text: str) -> str:
    """A script line's words ("MOM: Nate, where…" -> "Nate, where…"), never a note in
    brackets ("[she sighs]", "[quietly]"); a [tag] line's words stay, to time a split by."""
    return DIALOGUE.sub("", without_notes(TAG.sub("", text))).strip()


def repair(script: str, bd: Breakdown, problems: list[str], min_s: int, max_s: int, cast=None):
    """The breakdown with these problems fixed, and what was done in plain words (for the
    toast). Problems with no fix are left as they are. `cast(bd)` puts the right cast in each
    shot (cast_roles.fix), for "Check the cast" lines."""
    bd, done = bd.model_copy(deep=True), []
    if cast and any(kind(p) == "fix_cast" for p in problems) and (new := cast(bd)) is not None:
        bd, done = new, ["Put the right cast in each shot."]
    lines = script.splitlines()
    shots = [shot for scene in bd.scenes for shot in scene.shots]

    def later(p: str) -> tuple:  # splits after the rest, the last clip first (each renumbers)
        return (1, -int(KINDS[k].match(p)[1][1:])) if (k := kind(p)) == "split_clip" else (0, 0)

    for p in sorted(problems, key=later):
        k = kind(p)
        m = KINDS[k].match(p) if k else None
        if k == "add_line" and shots:
            n = int(m[1])
            words = _words(_said(lines[n - 1])) if 0 < n <= len(lines) else ""
            saying = [s for s in shots if words and s.line and _words(s.line) == words]
            before = [s for s in shots if s.script_lines and min(s.script_lines) < n]
            shot = saying[0] if saying else before[-1] if before else shots[0]
            if n not in shot.script_lines:
                shot.script_lines = sorted([*shot.script_lines, n])
                done.append(f"Put line {n} in shot {shot.id}.")
        elif k == "restore_line":
            shot = next((s for s in shots if s.id == m[1]), None)
            source = [lines[n - 1] for n in (shot.script_lines if shot else [])
                      if 0 < n <= len(lines)]  # fmt: skip
            spoken = [x for x in source if DIALOGUE.match(TAG.sub("", x))] or source
            words = " ".join(w for x in spoken if (w := _said(x)))
            said = _words(shot.line or "") if shot else ""
            n = next((i for i, x in enumerate(lines, 1) if said and _words(_said(x)) == said), 0)
            if shot and not shot.script_lines and n:  # the words are there: link the line
                shot.script_lines = [n]
                done.append(f"Put line {n} in shot {shot.id}.")
            elif shot and words and shot.line != words:
                shot.line = words
                done.append(f"Put the script's words back in shot {shot.id}.")
        elif k == "recover_clips" and "Fitted the clips to the shots." not in done:
            if _recover(bd, shots, min_s, max_s):
                done.append("Fitted the clips to the shots.")
        elif k == "split_clip" and _split(bd, m[1], min_s, max_s, lines):
            done.append(f"Split clip {m[1][1:]} so the video model can make it.")
    return bd, done


def split_into(data: dict, script: str, clip_id: str, min_s: int, max_s: int) -> int:
    """How many clips Split makes of this one (1: it can't be split). Free, nothing saved."""
    return len(split_preview(data, script, clip_id, min_s, max_s)) or 1


def split_preview(data: dict, script: str, clip_id: str, min_s: int, max_s: int) -> list:
    """The clips Split would make of this one, each with its shots (nothing saved); [] when
    it can't be split."""
    bd = Breakdown.model_validate(data)
    at, before = next((i for i, c in enumerate(bd.clips) if c.id == clip_id), 0), len(bd.clips)
    if not _split(bd, clip_id, min_s, max_s, script.splitlines()):
        return []
    return bd.clips[at : at + len(bd.clips) - before + 1]


def _split(bd: Breakdown, clip_id: str, min_s: int, max_s: int, lines=()) -> bool:
    """A clip longer than the video model makes, cut into clips it can (rule 29): between
    its shots, and a shot longer than the model makes at its sentence breaks (`_cut`), the
    words unchanged. Then numbered c1, c2, … again. A song video's fit sets each new clip's
    length from the song when it's saved."""
    at = next((i for i, c in enumerate(bd.clips) if c.id == clip_id), None)
    if at is None:
        return False
    new = bd.model_copy(deep=True)  # kept only when every new clip fits the model
    mine, into = set(new.clips[at].shot_ids), {}  # an over-long shot: cut at a sentence end
    for scene in new.scenes:
        for s in scene.shots:
            into[s.id] = _cut(s, lines, max_s) if s.id in mine else [s]
        scene.shots = [x for s in scene.shots for x in into[s.id]]
    new.clips[at].shot_ids = [x.id for sid in new.clips[at].shot_ids for x in into.get(sid, [])]
    seconds = {s.id: s.seconds for scene in new.scenes for s in scene.shots}
    groups, run = [[]], 0.0
    for sid in new.clips[at].shot_ids:
        if groups[-1] and run + seconds.get(sid, 0) > max_s:
            groups, run = [*groups, []], 0.0
        groups[-1].append(sid)
        run += seconds.get(sid, 0)
    if len(groups) < 2 or any(sum(seconds.get(i, 0) for i in g) > max_s + 0.5 for g in groups):
        return False  # a sentence longer than the model makes: never sent cut short
    new.clips[at : at + 1] = [
        new.clips[at].model_copy(update={"shot_ids": ids, "seconds": min(max(
            math.ceil(sum(seconds.get(i, 0) for i in ids) - 0.5), min_s), max_s)})
        for ids in groups
    ]  # fmt: skip
    for n, clip in enumerate(new.clips, 1):
        clip.id = f"c{n}"
    bd.scenes, bd.clips = new.scenes, new.clips
    return True


def _cut(shot, lines, max_s: int) -> list:
    """A shot longer than the video model makes, cut at its sentence breaks into shots of at
    most `max_s` each ("4.1" into "4.1.1", "4.1.2", …: its clip is written again), each as
    long as its share of the words; the words, the picture and the cast stay as they were.
    [shot] when it fits, or has one sentence."""
    if shot.seconds <= max_s:
        return [shot]
    said = {n: _words(_said(lines[n - 1])) for n in shot.script_lines if 0 < n <= len(lines)}
    text = shot.line or " ".join(_said(lines[n - 1]) for n in said)
    parts = _sentences(text)
    if len(parts) < 2:
        return [shot]
    per = shot.seconds / sum(max(1, len(p.split())) for p in parts)
    groups, run = [[]], 0.0  # sentence places, grouped into pieces of at most max_s
    for j, p in enumerate(parts):
        long = max(1, len(p.split())) * per
        if groups[-1] and run + long > max_s:
            groups, run = [*groups, []], 0.0
        groups[-1].append(j)
        run += long
    of = _lines_of(parts, sorted(said), said)
    out = []
    for k, idx in enumerate(groups):
        g = [parts[j] for j in idx]
        words = " ".join(g)
        mine = sorted({n for j in idx for n in of.get(j, [])}) or shot.script_lines
        out.append(shot.model_copy(update={
            "id": f"{shot.id}.{k + 1}", "script_lines": mine,
            "line": words if shot.line else None,
            "seconds": round(sum(max(1, len(x.split())) for x in g) * per, 1)}))  # fmt: skip
    left = [n for n in shot.script_lines if not any(n in x.script_lines for x in out)]
    out[0].script_lines = sorted({*out[0].script_lines, *left})  # a camera or ★ line: kept
    return out


def _lines_of(parts: list[str], order: list[int], said: dict[int, str]) -> dict[int, list[int]]:
    """Each sentence's script lines (by its place): every line its words fall on, found as
    whole words, in order, never before where the last sentence ended (a repeated sentence
    takes the next copy; one running over a line break gets both lines)."""
    words = [(w, n) for n in order for w in said[n].split()]
    out, at = {}, 0
    for j, p in enumerate(parts):
        want = _words(p).split()
        ends = range(at, len(words) - len(want) + 1) if want else range(0)
        hit = next((i for i in ends if [w for w, _ in words[i : i + len(want)]] == want), None)
        if hit is not None:
            out[j], at = sorted({n for _, n in words[hit : hit + len(want)]}), hit + len(want)
    return out


SHORT = re.compile(r"(?:\b(?:Dr|Mr|Mrs|Ms|St|Jr|Sr|vs|No|e\.g|i\.e)|\b[A-Z])\.$")


def _sentences(text: str) -> list[str]:
    """Each sentence, split after . ! ? or …, but never after a title or an initial ("Dr.
    Pickle"): a cut between clips never falls inside a name."""
    out = []
    for part in re.split(r"(?<=[.!?…])\s+", text.strip()):
        if out and SHORT.search(out[-1]):
            out[-1] = f"{out[-1]} {part}"
        elif part:
            out.append(part)
    return out


def _recover(bd: Breakdown, shots: list, min_s: int, max_s: int) -> bool:
    """Every shot in exactly one clip, in order, keeping the clips' own grouping; each clip at
    least as long as its shots (within the model's length)."""
    if not bd.clips:
        return False
    first = {}
    for i, clip in enumerate(bd.clips):
        for sid in clip.shot_ids:
            first.setdefault(sid, i)
    at, groups = 0, [[] for _ in bd.clips]
    for shot in shots:
        at = max(at, first.get(shot.id, at))  # a shot no clip had joins the one before
        groups[at].append(shot.id)
    seconds = {s.id: s.seconds for s in shots}
    old = [(c.shot_ids, c.seconds) for c in bd.clips]
    for clip, ids in zip(bd.clips, groups, strict=True):
        clip.shot_ids = ids
        total = math.ceil(sum(seconds[i] for i in ids) - 0.5)
        if clip.seconds < total:
            clip.seconds = min(max(total, min_s), max_s)
    bd.clips = [c for c in bd.clips if c.shot_ids]
    return [(c.shot_ids, c.seconds) for c in bd.clips] != old


def remove_ref(bd: Breakdown, shot_id: str, ref: str) -> Breakdown | None:
    """The breakdown with `ref` taken out of one shot (its action stays as written), or None
    when the shot doesn't name it."""
    bd = bd.model_copy(deep=True)
    shot = next((s for scene in bd.scenes for s in scene.shots if s.id == shot_id), None)
    if shot is None or ref not in [*shot.character_ids, shot.place_id, *shot.screen_ids]:
        return None
    shot.character_ids = [c for c in shot.character_ids if c != ref]
    shot.screen_ids = [s for s in shot.screen_ids if s != ref]
    shot.place_id = None if shot.place_id == ref else shot.place_id
    return bd


def drop_unknown(bd: Breakdown, known: dict, called) -> tuple[Breakdown, list[str]]:
    """What the AI named that the video doesn't have, taken out of its shots, each said as
    advice (never a problem): "Advice: Removed Nate from shot 1.3. …"."""
    notes = []
    for scene in bd.scenes:
        for shot in scene.shots:
            for ref in [*shot.character_ids, shot.place_id, *shot.screen_ids]:
                if ref and ref not in known:
                    bd = remove_ref(bd, shot.id, ref) or bd
                    who = called(ref)
                    notes.append(f"Advice: Removed {who} from shot {shot.id}. "
                                 "Nobody by that name is in this video.")  # fmt: skip
    return bd, notes
