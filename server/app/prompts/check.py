"""Mechanical checks on Claude's answers. Each returns a list of plain-language problems (empty
= fine). Used by the offline evals (`server/evals`) and available to the jobs that save the
answers. They check the rules a machine can see; whether a video is engaging stays a human call.

`screens` maps screen id ('screen:12') to the moments it is required at."""

import re

from app.prompts.schemas import (
    Breakdown,
    ClipPrompts,
    EnhanceResult,
    ImprovedPrompt,
    StoryboardFrames,
)

DIALOGUE = re.compile(r"^[A-Z][A-Z .'()-]*:\s")
SCREEN_LINE = "★"
TAG = re.compile(r"^\[[A-Za-z ]+\] ")  # accepted Enhance lines: "[Camera] …", "[Brand screen] ★ …"
SILENT = "Audio: no one speaks (no voices, narration or dialogue), only "
AUDIO_LINE = re.compile(
    r"^Audio: (only the spoken lines and|no one speaks \(no voices, narration or dialogue\), "
    r"only) .+ No subtitles\.$"
)
SAYS = re.compile(  # action that reads like a line; the model voices it (fomo montage, 2026-10-23)
    r"\b(says?|tells?|repl(y|ies)|answers?|shouts?|whispers?|yells?|refuses?"
    r"|(does not|doesn't|won't|will not) (sell|say|speak|answer|reply|agree|give in))\b",
    re.I,
)
QUOTED = re.compile(r'["“]([^"”]*)["”]')  # straight or curly (phones type curly)
FLAGGED = re.compile(  # Nano Banana refused frames with these (E005 "sensitive"), 2026-10-23
    r"\b(leggings|laps?|thighs?|cleavage|crust\w*|pus|ooz\w*|discharge|blood\w*|wounds?|vomit\w*)\b",
    re.I,
)
SETTINGS_WORDS = re.compile(r"\b\d+:\d+\b|\b(480|720|1080)p\b")


def enhance(script: str, result: EnhanceResult, screens: dict[str, list[str]]) -> list[str]:
    lines = script.splitlines()
    problems = []
    for s in result.suggestions:
        n, quote = s.anchor.line, s.anchor.quote
        if not 1 <= n <= len(lines) or quote not in lines[n - 1]:
            problems.append(f"{s.id}: quote not found on line {n}")
            continue
        if DIALOGUE.match(s.text) or '"' in s.text:
            problems.append(f"{s.id}: adds spoken words")
        if s.kind == "brand_screen" and s.screen_id not in screens:
            problems.append(f"{s.id}: unknown screen {s.screen_id}")
    return problems


def breakdown(
    script: str,
    bd: Breakdown,
    screens: dict[str, list[str]],
    min_s: int,
    max_s: int,
    end_line: str = "",
) -> list[str]:
    lines = script.splitlines()
    shots = [shot for scene in bd.scenes for shot in scene.shots]
    problems = []
    said = [TAG.sub("", text) for text in lines if text.strip()]
    said = [text for text in said if not text.startswith(("SCENE", SCREEN_LINE, "["))]
    if end_line and not (said and _exact(end_line) in _exact(said[-1])):
        problems.append("the script doesn't end on the brand's end line")
    covered = {n for shot in shots for n in shot.script_lines}
    shown = {n for shot in shots if shot.screen_ids for n in shot.script_lines}
    for n, text in enumerate(lines, 1):
        if text.strip() and not text.startswith("SCENE") and n not in covered:
            problems.append(f"line {n} is in no shot")
        elif TAG.sub("", text).startswith(SCREEN_LINE) and n not in shown:
            problems.append(f"line {n} is a ★ screen line but no shot shows a screen")
    for shot in shots:
        source = [lines[n - 1] for n in shot.script_lines if 0 < n <= len(lines)]
        if shot.line and _words(shot.line) not in _words(" ".join(source)):
            problems.append(f"shot {shot.id}: line differs from the script")
        for sid in shot.screen_ids:
            if sid not in screens:
                problems.append(f"shot {shot.id}: unknown screen {sid}")
        needed = {sid for sid, moments in screens.items() if shot.moment in moments}
        if needed and not needed & set(shot.screen_ids):
            problems.append(f"shot {shot.id}: '{shot.moment}' moment without its screen")
    quick = [not shot.line and shot.seconds <= 0.6 for shot in shots]  # wordless, fast
    for i, shot in enumerate(shots):
        # a montage is 3+ quick shots in a row; is this shot inside one?
        windows = [quick[k : k + 3] for k in range(max(0, i - 2), i + 1)]
        if any(len(w) == 3 and all(w) for w in windows) and not shot.character_ids:
            problems.append(f"shot {shot.id}: a montage shot without the main character")
    order = [shot.id for shot in shots]
    if [sid for clip in bd.clips for sid in clip.shot_ids] != order:
        problems.append("clips don't cover the shots once each, in order")
    by_id = {shot.id: shot for shot in shots}
    for clip in bd.clips:
        total = sum(by_id[s].seconds for s in clip.shot_ids if s in by_id)
        if not min_s <= clip.seconds <= max_s:
            problems.append(f"clip {clip.id}: {clip.seconds} s is outside {min_s}–{max_s} s")
        if clip.seconds < total - 0.5:
            problems.append(f"clip {clip.id}: {clip.seconds} s is shorter than its shots")
        screens = {sid for s in clip.shot_ids if s in by_id for sid in by_id[s].screen_ids}
        if len(screens) > 3:  # the model mixes them up (fomo montage run 3, 2026-10-24)
            problems.append(f"clip {clip.id}: {len(screens)} screens; keep the 3 its beats need")
    return problems


def clip_prompts(bd: Breakdown, cp: ClipPrompts, max_images: int, max_audios: int) -> list[str]:
    shots = {shot.id: shot for scene in bd.scenes for shot in scene.shots}
    clips = {clip.id: clip for clip in bd.clips}
    problems = []
    for c in cp.clips:
        clip = clips.get(c.clip_id)
        if not clip:
            problems.append(f"{c.clip_id}: not a clip in the breakdown")
            continue
        images = [r.id for r in c.references if r.kind == "image"]
        audios = [r for r in c.references if r.kind == "audio"]
        if len(images) > max_images or len(audios) > max_audios:
            problems.append(f"{c.clip_id}: more references than the model takes")
        used = {int(n) for n in re.findall(r"\[Image(\d+)\]", c.prompt)}
        if used and max(used) > len(images):
            problems.append(f"{c.clip_id}: prompt names an image that isn't attached")
        for sid in clip.shot_ids:
            shot = shots[sid]
            for screen in shot.screen_ids:
                if screen not in images:
                    problems.append(f"{c.clip_id}: shot {sid}'s screen {screen} isn't attached")
                elif f"[Image{images.index(screen) + 1}]" not in c.prompt:
                    problems.append(f"{c.clip_id}: screen {screen} is attached but never shown")
            said = [_exact(q) for q in QUOTED.findall(c.prompt)]
            line = _exact(shot.line or "")
            times = sum(_exact(shots[s].line or "") == line for s in clip.shot_ids)
            if shot.line and said.count(line) != times:
                problems.append(f"{c.clip_id}: shot {sid}'s line isn't there once, word for word")
        problems += [f"{c.clip_id}: {p}" for p in _cuts_name_someone(c.prompt)]
        shape, _ = _shape(c.prompt, c.seconds)
        problems += [f"{c.clip_id}: {p}" for p in shape]
        problems += [
            f"{c.clip_id}: {p}"
            for p in _silence(c.prompt, any(shots[s].line for s in clip.shot_ids))
        ]
        if (
            images
            and images[0].startswith("frame:")
            and "[Image1] is the first frame." not in c.prompt
        ):
            problems.append(f"{c.clip_id}: doesn't name [Image1] the first frame")
        cast = [r.id for r in c.references if r.id.startswith("char:")]
        first_seen = list(dict.fromkeys(i for s in clip.shot_ids for i in shots[s].character_ids))
        for i in first_seen:
            if i not in cast:
                problems.append(f"{c.clip_id}: {i} is in the clip but its sheet isn't attached")
        if cast != [i for i in first_seen if i in cast]:
            problems.append(f"{c.clip_id}: characters aren't attached in the order they appear")
        if c.seconds != clip.seconds:
            problems.append(f"{c.clip_id}: {c.seconds} s but the breakdown says {clip.seconds} s")
    return problems


def storyboard(
    frames: StoryboardFrames, max_images: int, max_characters: int, bd: Breakdown | None = None
) -> list[str]:
    shots = {shot.id: shot for scene in bd.scenes for shot in scene.shots} if bd else {}
    problems = []
    for f in frames.frames:
        characters = [r for r in f.reference_ids if r.startswith("char:")]
        if len(f.reference_ids) > max_images or len(characters) > max_characters:
            problems.append(f"{f.clip_id}: more references than the image model keeps")
        cast = shots[f.shot_id].character_ids if f.shot_id in shots else []
        missing = [i for i in cast if i not in characters]
        if missing and len(characters) < max_characters:
            problems.append(f"{f.clip_id}: {', '.join(missing)} in the shot without a sheet")
        flagged = sorted({w.lower() for w in FLAGGED.findall(f.prompt)})
        if flagged:
            problems.append(
                f"{f.clip_id}: the image model may refuse “{', '.join(flagged)}”; say it gently"
            )
    return problems


SHOT_LINE = re.compile(r"^Shot \d+ \| (\d+)[-–](\d+) s\.", re.M)  # hyphen or en dash


def _shape(prompt: str, seconds: float) -> tuple[list[str], int]:
    """The Seedance prompt shape (Reed, 2026-10-23): the same audio line first and last, a
    Summary line, whole-second shots back to back from 0 to `seconds`, a Keep line before the
    closing audio line, and no settings words. Returns the problems and the shot count."""
    lines = prompt.strip().splitlines()
    problems = []
    if not (AUDIO_LINE.match(lines[0]) and lines[-1] == lines[0]):
        problems.append("doesn't open and close with the same audio line")
    if not any(line.startswith("Summary: ") for line in lines):
        problems.append("has no Summary line")
    if len(lines) < 2 or not lines[-2].startswith("Keep: "):
        problems.append("has no Keep line before the closing audio line")
    if SETTINGS_WORDS.search(QUOTED.sub("", prompt)):
        problems.append("writes aspect or resolution (those are settings)")
    times = [(int(a), int(b)) for a, b in SHOT_LINE.findall(prompt)]
    ends = [0] + [end for _, end in times]
    if not times or any(start != ends[i] or end <= start for i, (start, end) in enumerate(times)):
        problems.append("shot times aren't whole seconds back to back from 0")
    elif times[-1][1] != seconds:
        problems.append(f"shots end at {times[-1][1]} s, the clip is {seconds} s")
    return problems, len(times)


CAST = re.compile(r"\[Image\d+\] (?:is|are) ([A-Z][\w-]+)")  # "[Image2] is Malik."


def _cuts_name_someone(prompt: str) -> list[str]:
    """In a "Two quick cuts: …; then …" segment every cut names a cast member, so the model
    never opens on an empty room (fomo montage, 2026-10-24)."""
    refs = next((line for line in prompt.splitlines() if line.startswith("References: ")), "")
    names = set(CAST.findall(refs)) - {"The"}
    if not names:
        return []
    problems = []
    for line in prompt.splitlines():
        if m := re.match(r"^Shot (\d+) \|[^:]*quick cuts[^:]*: (.*)$", line, re.I):
            for cut in m.group(2).split("; then "):
                if not any(re.search(rf"\b{re.escape(n)}\b", cut) for n in names):
                    problems.append(f"shot {m.group(1)}: a quick cut names nobody (“{cut[:40]}”)")
    return problems


def _silence(prompt: str, spoken: bool) -> list[str]:
    """Nobody speaks unless the script says so: a clip without lines carries the no-speech
    audio line; every shot without a line says "No one speaks." and no action reads like one."""
    problems = []
    if spoken == prompt.lstrip().startswith(SILENT):
        problems.append("the audio line doesn't match whether anyone speaks")
    starts = [m.start() for m in SHOT_LINE.finditer(prompt)]
    end = prompt.find("\nKeep: ")
    for n, (a, b) in enumerate(
        zip(starts, starts[1:] + [end if end > 0 else len(prompt)], strict=False), 1
    ):
        shot = prompt[a:b]
        if QUOTED.search(shot):
            continue
        if "No one speaks." not in shot:
            problems.append(f"shot {n} has no line but doesn't say no one speaks")
        if m := SAYS.search(shot):
            problems.append(f"shot {n}: '{m.group(0)}' reads like a line; show what the body does")
    return problems


def improve(
    idea: str, result: ImprovedPrompt, references: str, shots: int, seconds: float
) -> list[str]:
    """Quick clip Improve prompt: the editor's quoted words survive exactly, the server's
    reference lines are copied, the shape and timing match the brief."""
    prompt = result.prompt.strip()
    said = [_exact(q) for q in QUOTED.findall(prompt)]
    asked = [_exact(q) for q in QUOTED.findall(idea)]
    problems = []
    for quote in dict.fromkeys(QUOTED.findall(idea)):
        if said.count(_exact(quote)) != asked.count(_exact(quote)):
            problems.append(f"the line “{quote}” isn't there once, word for word")
    if references and f"References: {references}" not in prompt.splitlines():
        problems.append("the reference lines aren't copied exactly")
    shape, count = _shape(prompt, seconds)
    problems += shape + _silence(prompt, bool(asked))
    if count != shots:
        problems.append(f"{count} shots, the brief asks for {shots}")
    return problems


def _exact(text: str) -> str:
    """Spoken words as written: case and punctuation count (they carry delivery); only runs
    of whitespace are evened out."""
    return " ".join(text.split())


def _words(text: str) -> str:
    return " ".join(re.findall(r"[\w']+", text.lower()))
