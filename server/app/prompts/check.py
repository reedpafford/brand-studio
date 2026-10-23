"""Mechanical checks on Claude's answers. Each returns a list of plain-language problems (empty
= fine). Used by the offline evals (`server/evals`) and available to the jobs that save the
answers. They check the rules a machine can see; whether a video is engaging stays a human call.

`screens` maps screen id ('screen:12') to the moments it is required at."""

import re

from app.prompts.schemas import Breakdown, ClipPrompts, EnhanceResult

DIALOGUE = re.compile(r"^[A-Z][A-Z .'-]*:\s")
SCREEN_LINE = "★"


def enhance(script: str, result: EnhanceResult, screens: dict[str, list[str]]) -> list[str]:
    lines = script.splitlines()
    problems = []
    for s in result.suggestions:
        n, quote = s.anchor.line, s.anchor.quote
        if not 1 <= n <= len(lines) or quote not in lines[n - 1]:
            problems.append(f"{s.id}: quote not found on line {n}")
            continue
        if s.kind == "cut" and (s.placement != "replace" or s.text):
            problems.append(f"{s.id}: a cut must replace the quote with nothing")
        if s.kind != "cut" and s.placement == "replace" and DIALOGUE.match(lines[n - 1]):
            problems.append(f"{s.id}: rewrites dialogue")
        if DIALOGUE.match(s.text):
            problems.append(f"{s.id}: adds dialogue")
        if s.kind == "brand_screen" and s.screen_id not in screens:
            problems.append(f"{s.id}: unknown screen {s.screen_id}")
    return problems


def breakdown(
    script: str, bd: Breakdown, screens: dict[str, list[str]], min_s: int, max_s: int
) -> list[str]:
    lines = script.splitlines()
    shots = [shot for scene in bd.scenes for shot in scene.shots]
    problems = []
    covered = {n for shot in shots for n in shot.script_lines}
    for n, text in enumerate(lines, 1):
        if text.strip() and not text.startswith("SCENE") and n not in covered:
            problems.append(f"line {n} is in no shot")
    for shot in shots:
        source = [lines[n - 1] for n in shot.script_lines if 0 < n <= len(lines)]
        if shot.line and _words(shot.line) not in _words(" ".join(source)):
            problems.append(f"shot {shot.id}: line differs from the script")
        if any(text.startswith(SCREEN_LINE) for text in source) and not shot.screen_ids:
            problems.append(f"shot {shot.id}: script has a ★ screen line but no screen")
        for sid in shot.screen_ids:
            if sid not in screens:
                problems.append(f"shot {shot.id}: unknown screen {sid}")
        needed = {sid for sid, moments in screens.items() if shot.moment in moments}
        if needed and not needed & set(shot.screen_ids):
            problems.append(f"shot {shot.id}: '{shot.moment}' moment without its screen")
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
            if shot.line and _words(shot.line) not in _words(c.prompt):
                problems.append(f"{c.clip_id}: shot {sid}'s line isn't word for word")
        if c.seconds != clip.seconds:
            problems.append(f"{c.clip_id}: {c.seconds} s but the breakdown says {clip.seconds} s")
    return problems


def _words(text: str) -> str:
    return " ".join(re.findall(r"[\w']+", text.lower()))
