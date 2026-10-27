"""One-click fixes for a breakdown's problems (Reed, 2026-10-26, DECISIONS #520; spec
one-click-fixes.md §1-2): free, no model call. A missing script line goes into the shot that
holds the lines around it, a changed line gets the script's words back, the clips are fitted
to the shots again, and a name the video doesn't have is taken out of a shot."""

import math
import re

from app.prompts.check import DIALOGUE, TAG, _words
from app.prompts.schemas import Breakdown

KINDS = {  # the problem as said (advice.plain), and its fix
    "add_line": re.compile(r"(?i)^line (\d+) is in no shot$"),
    "restore_line": re.compile(r"(?i)^shot ([\w.]+): line differs from the script$"),
    "recover_clips": re.compile(
        r"(?i)^(clips don't cover the shots once each, in order|clip \w+: [\d.]+ s is "
        r"shorter than its shots)$"
    ),
}
LABELS = {
    "add_line": "Add it to a shot",
    "restore_line": "Use the script's words",
    "recover_clips": "Fit the clips to the shots",
}


def kind(problem: str) -> str | None:
    return next((k for k, pattern in KINDS.items() if pattern.match(problem)), None)


def fixes(problems: list[str]) -> list[dict]:
    """The fix each problem has, for its button: [{problem, kind, label}]."""
    return [{"problem": p, "kind": k, "label": LABELS[k]} for p in problems if (k := kind(p))]


def _said(text: str) -> str:
    """A script line's spoken words ("MOM: Nate, where…" -> "Nate, where…")."""
    return DIALOGUE.sub("", TAG.sub("", text)).strip()


def repair(script: str, bd: Breakdown, problems: list[str], min_s: int, max_s: int):
    """The breakdown with these problems fixed, and what was done in plain words (for the
    toast). Problems with no fix are left as they are."""
    bd = bd.model_copy(deep=True)
    lines = script.splitlines()
    shots = [shot for scene in bd.scenes for shot in scene.shots]
    done: list[str] = []
    for p in problems:
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
            words = " ".join(_said(x) for x in spoken)
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
    return bd, done


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
