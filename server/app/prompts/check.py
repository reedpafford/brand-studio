"""Mechanical checks on Claude's answers. Each returns a list of plain-language problems (empty
= fine). Used by the offline evals (`server/evals`) and available to the jobs that save the
answers. They check the rules a machine can see; whether a video is engaging stays a human call.

`screens` maps screen id ('screen:12') to the moments it is required at."""

import re
from itertools import zip_longest

from app.prompts import spoken_words
from app.prompts.schemas import (
    Breakdown,
    CastSlots,
    ClipPrompts,
    EnhanceResult,
    ImprovedPrompt,
    ReelWatch,
    StoryboardFrames,
    Variations,
)

DIALOGUE = re.compile(r"^[A-Z][A-Z .'()-]*:\s")
SCREEN_LINE = "★"
ADVICE = "Advice: "  # a problem that never blocks a step; the editor can keep it

HIS = re.compile(
    r"\b[A-Z][\w-]*'s (hands?|fingers?|thumbs?|phone|laptop|monitors?|screen|keys|car|desk)\b"
)
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
MONEY = re.compile(r"[+\-−]?\$\d+(?:,\d{3})*(?:\.\d+)?(?:\s?[kKmM]\b)?")  # "+$42", "−$80", "$348k"
SETTINGS_WORDS = re.compile(  # aspect ratios and resolutions, not a clock reading "3:12"
    r"\b(?:9:16|16:9|4:5|5:4|1:1|4:3|3:4|2:3|3:2|21:9)\b|\b(?:480|720|1080)p\b"
)


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


DEVICE = {"mobile", "desktop"}  # what a screen is shown on, not what kind of screen it is


def moment_screen(shot, screens: dict[str, list[str]], kinds: dict[str, set[str]]) -> str:
    """A brand moment's shot shows one of its screens, or a screen of the same kind (any
    "home" screen for fomo-mention: Home or Home (rich), Reed 2026-10-27). Advice, never a
    block; "" when it does."""
    needed = {sid for sid, moments in screens.items() if shot.moment in moments}
    if not needed or needed & set(shot.screen_ids):
        return ""
    wanted = {t for sid in needed for t in kinds.get(sid, set())} - DEVICE
    if any(wanted & (kinds.get(s, set()) - DEVICE) for s in shot.screen_ids):
        return ""
    return f"{ADVICE}shot {shot.id}: '{shot.moment}' moment without its screen"


def breakdown(
    script: str,
    bd: Breakdown,
    screens: dict[str, list[str]],
    min_s: int,
    max_s: int,
    end_line: str = "",
    brand: str = "",  # the brand's name: a near end line must still say it
    approved: bool = False,  # Reed approved the words: the end line never blocks (advice)
    kinds: dict[str, set[str]] | None = None,  # each screen's type tags ("home"): moment_screen
) -> list[str]:
    lines = script.splitlines()
    shots = [shot for scene in bd.scenes for shot in scene.shots]
    problems = []
    said = [TAG.sub("", text) for text in lines if text.strip()]
    said = [text for text in said if not text.startswith(("SCENE", SCREEN_LINE, "["))]
    ends = ends_on(end_line, said[-1] if said else "", brand, said[-2] if len(said) > 1 else "")
    if ends == "no" and not approved:
        problems.append("the script doesn't end on the brand's end line")
    elif ends == "no":
        problems.append(f"{ADVICE}the script doesn't end on the brand's end line")
    elif ends == "near":
        problems.append(
            f"{ADVICE}the last line is close to the brand's end line but not word for word"
        )
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
        if said := moment_screen(shot, screens, kinds or {}):
            problems.append(said)
    problems += _money_climbs(shots)
    problems += cta_screen(shots, end_line, brand)
    quick = [not shot.line and shot.seconds <= 0.6 for shot in shots]  # wordless, fast
    for i, shot in enumerate(shots):
        # a montage is 3+ quick shots in a row; is this shot inside one?
        windows = [quick[k : k + 3] for k in range(max(0, i - 2), i + 1)]
        his = shot.character_ids or shot.screen_ids or HIS.search(shot.action)  # hands, phone…
        if any(len(w) == 3 and all(w) for w in windows) and not his:
            problems.append(f"{ADVICE}shot {shot.id}: a montage shot without the main character")
    runs = [i for i in range(len(shots) - 2) if all(quick[i : i + 3])]
    if runs:  # earn the payoff: effort beats between the last line and the fast run
        start = runs[0]
        spoken = [i for i in range(start) if shots[i].line]
        grind = start - (spoken[-1] + 1 if spoken else 0)
        if grind < 3:
            problems.append(
                f"{ADVICE}shot {shots[start].id}: the montage reaches the payoff after {grind} "
                "grind beats; add a red day, a small win, another late night first"
            )
    first = next((n for n, x in enumerate(lines, 1) if DIALOGUE.match(TAG.sub("", x))), 0)
    before = {  # the script's own set-up, ahead of its first exchange
        n for n in range(1, first) if lines[n - 1].strip() and not lines[n - 1].startswith("SCENE")
    }
    opener = next((i for i, shot in enumerate(shots) if shot.line), 0)
    cutaways = [x for x in shots[:opener] if not before & set(x.script_lines)]
    if first and len(cutaways) > 1:  # shots the script doesn't have, ahead of the exchange
        problems.append(
            f"{ADVICE}shot {cutaways[0].id}: {len(cutaways)} shots come before the first "
            "line; open on the exchange itself"
        )
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


def _money(shot) -> bool:
    """A trading or win insert, where the money on screen tells the story."""
    return bool(shot.screen_ids) and (shot.moment or "").startswith(("trading", "win"))


def _figure(text: str) -> tuple[str, float, str] | None:
    """The first money figure in a shot: ('pnl' for a signed gain or loss, else 'balance'),
    its value ('$348k' is 348,000; a loss is negative) and the text as written."""
    if not (m := MONEY.search(text)):
        return None
    found, sign = m.group(), m.group()[0] if m.group()[0] in "+-−" else ""
    value = float(re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", found).group().replace(",", ""))
    value *= {"k": 1e3, "m": 1e6}.get(found[-1].lower(), 1)
    return ("pnl" if sign else "balance"), (-value if sign in ("-", "−") else value), found


def _money_climbs(shots: list) -> list[str]:
    """Reed (altar v3, 2026-10-25): the balance and P&L climb with the chart, shot by shot,
    to a clearly large payoff (six figures or more, any number). A trading insert states what
    its screen reads; a balance is never below the last balance, a gain never below the last
    gain (a loss, or a loss shot, is exempt). Advice."""
    problems, last = [], {}
    for shot in shots:
        if not shot.screen_ids or shot.moment == "loss":
            continue
        if not (fig := _figure(shot.action)):
            if _money(shot) and shot.moment.startswith("trading"):
                problems.append(
                    f"{ADVICE}shot {shot.id}: say what the trading screen reads "
                    "(e.g. “the balance reads $1,240”), bigger than the shot before"
                )
            continue
        kind, value, found = fig
        if value < 0:  # a red day
            continue
        if kind in last and value < last[kind][1]:
            problems.append(
                f"{ADVICE}shot {shot.id}: the screen reads {found}, less than shot "
                f"{last[kind][0]}; the money only climbs"
            )
        last[kind] = (shot.id, value)
    top = last.get("balance") or last.get("pnl")
    if top and any((s.moment or "").startswith("win") for s in shots) and top[1] < 100_000:
        problems.append(f"{ADVICE}shot {top[0]}: the payoff reads under $100,000; make it "
                        "clearly large (six figures or more)")  # fmt: skip
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
            if _money(shot):
                problems += [f"{ADVICE}{c.clip_id}: shot {sid}'s screen should read {x}"
                             for x in MONEY.findall(shot.action) if x not in c.prompt]  # fmt: skip
            said = [_exact(q) for q in QUOTED.findall(c.prompt)]
            line = _exact(shot.line or "")
            times = sum(_exact(shots[s].line or "") == line for s in clip.shot_ids)
            if shot.line and said.count(line) != times:
                problems.append(f"{c.clip_id}: shot {sid}'s line isn't there once, word for word")
        if _montage(clip.shot_ids, shots):  # guests and crowds elsewhere are never cast
            problems += [f"{ADVICE}{c.clip_id}: {p}" for p in _cuts_name_someone(c.prompt)]
        keep = next((x for x in c.prompt.splitlines() if x.startswith("Keep: ")), "")
        problems += [  # each attached character holds their look by name (live test, 10-26)
            f"{ADVICE}{c.clip_id}: the Keep line doesn't name {who}; give their look and outfit"
            for who in dict.fromkeys(CAST.findall(c.prompt))
            if keep and who not in keep
        ]
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
        if c.seconds != clip.seconds:
            problems.append(f"{c.clip_id}: {c.seconds} s but the breakdown says {clip.seconds} s")
    return problems


def storyboard(
    frames: StoryboardFrames, max_images: int, max_characters: int, bd: Breakdown | None = None
) -> list[str]:
    shots = {shot.id: shot for scene in bd.scenes for shot in scene.shots} if bd else {}
    problems = []
    for f in frames.frames:
        characters = [r for r in f.reference_ids if r.startswith(("char:", "slot:"))]
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


SHOT_ANY = re.compile(r"^Shot (\d+) \|(.*)$", re.M)


def _shot_times(prompt: str) -> str:
    """What's wrong with the shot times, in plain words ("" if they run back to back)."""
    shots = SHOT_ANY.findall(prompt)
    if not shots:
        return "has no shot times (each shot line starts like “Shot 1 | 0-2 s.”)"
    end = 0
    for k, (number, rest) in enumerate(shots):
        times = re.match(r" (\d+)[-–](\d+) s\.", rest)
        which = "the last shot" if k == len(shots) - 1 else f"shot {number}"
        if not times:
            return f"{which}'s times aren't whole seconds; write them like “0-2 s.”"
        start, stop = int(times[1]), int(times[2])
        if stop <= start:
            return f"has an empty {which.removeprefix('the ')} ({start}–{stop} s). " + (
                "Remove it or give it a length."
            )
        if start != end:
            before = (
                "Start the first shot at 0 s." if k == 0 else f"The shot before ends at {end} s."
            )
            return f"{which} starts at {start} s. {before}"
        end = stop
    return ""


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
    wrong = _shot_times(prompt)
    if wrong:
        problems.append(wrong)
    elif times[-1][1] != seconds:
        problems.append(f"shots end at {times[-1][1]} s, the clip is {seconds} s")
    return problems, len(times)


CAST = re.compile(r"\[Image\d+\] (?:is|are) ([A-Z][\w-]+)")  # "[Image2] is Malik."


def _montage(ids: list[str], shots: dict) -> bool:
    """3+ quick wordless shots in a row (the breakdown check's montage run)."""
    quick = [not shots[i].line and shots[i].seconds <= 0.6 for i in ids]
    return any(all(quick[k : k + 3]) for k in range(len(quick) - 2))


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


NEAR = 0.5  # share of the end line's words a near match needs (Reed: never block a near one)


def cta_screen(shots: list, end_line: str, brand: str = "") -> list[str]:
    """The end line's shot (the call to action) shows the brand's real screen, on the phone the
    hero holds up to the camera (Reed, 2026-10-27): its clip then attaches it (`clip_prompts`)."""
    said = [
        s for s in shots if end_line.strip() and s.line and ends_on(end_line, s.line, brand) != "no"
    ]
    if said and not said[-1].screen_ids:
        return [f"{ADVICE}shot {said[-1].id}: the end line's shot shows no screen; show the "
                "brand's real screen on the phone he holds up to the camera"]  # fmt: skip
    return []


def ends_on(end_line: str, last: str, brand: str = "", before: str = "") -> str:
    """Does the script's last spoken line say the brand's end line? "yes" ignoring case,
    punctuation, curly quotes, spacing and the speaker's label (FOMO or fomo, a dropped
    comma), also when it is split over the last two lines (`before`, then `last`). "near"
    when at least half its words are there (advice, never a block) and it still names the
    brand, else "no" (another app's name, or "the app", blocks). With no end line, always
    "yes". Only the end line is matched this loosely; spoken lines elsewhere stay exact."""
    if not end_line.strip():
        return "yes"
    want, got = _spoken(end_line), _spoken(last)
    both = f"{_spoken(before)} {got}".strip()
    if f" {want} " in f" {got} ":  # whole words
        return "yes"
    split = bool(before) and bool(got) and f" {got} " in f" {want} "  # last ends the end line
    if split and f" {want} " in f" {both} ":
        return "yes"
    text = both if split else got
    named = bool(_words(brand)) and f" {_words(brand)} " in f" {text} "
    said = set(text.split())
    if named and sum(w in said for w in want.split()) / len(want.split()) >= NEAR:
        return "near"
    return "no"


SPEAKER = re.compile(r"^\s*[A-Z][A-Z .'-]*(?:\([^)]*\))?:")  # "NATE:" or "NATE (V.O.):"


def _spoken(line: str) -> str:
    return _words(_straight(SPEAKER.sub("", line)))


def _straight(text: str) -> str:
    return text.translate(str.maketrans("‘’“”", "''\"\""))


def _words(text: str) -> str:
    return " ".join(re.findall(r"[\w']+", text.lower()))


STAR = re.compile(r"^★ .*?(?:screen|product): (.+?)(?: — .*)?$")  # "★ fomo screen: Home — …"
LOOSE = re.compile(r"^(#|\*\*|- |\* |Title:|Premise:|Variation )")  # markdown, not house format


def variations(
    original: str,
    result: Variations,
    screens: dict[str, list[str]],
    end_line: str,
    never_say: list[str],
    count: int,
    cast: list[str] = (),
    brand: str = "",  # the brand's name: a near end line must still say it
) -> list[str]:
    """Alternates of an approved script (workflow v2): the brand, the end line and the locked
    cast are kept (fix); length, closeness and format are advice. `cast` holds the locked
    characters' names. `screens` is accepted for the server's call; ★ lines are matched by name."""
    problems = []
    if len(result.variations) != count:
        problems.append(f"{len(result.variations)} variations, {count} asked for; regenerate")
    stars = _stars(original)
    words = spoken_words(original)
    scripts = [v.script for v in result.variations]
    for i, script in enumerate(scripts, 1):
        name = f"variation {i}"
        lines = [line.strip() for line in script.splitlines() if line.strip()]
        said = [TAG.sub("", x) for x in lines if not x.startswith(("SCENE", "INT.", "EXT.", "★"))]
        ends = ends_on(end_line, said[-1] if said else "", brand, said[-2] if len(said) > 1 else "")
        if ends == "no":  # advice: variations come from an approved original (Reed)
            problems.append(f"{ADVICE}{name} doesn't end on the brand's end line")
        elif ends == "near":
            problems.append(
                f"{ADVICE}{name}'s last line is close to the brand's end line, not word for word"
            )
        for star in sorted(stars - _stars(script)):
            problems.append(f"{name} drops the ★ line for {star}; put it back where it fits")
        for phrase in never_say:
            if phrase.lower() in script.lower():
                problems.append(f"{name} says “{phrase}”, which the brand never says")
        if re.search(r"\blive[- ]action\b", script, re.I):
            problems.append(f"{name} brings back live action; that slot is the end line")
        for who in cast:  # only names the original uses (a narrator may be "I")
            named = rf"\b{re.escape(who)}\b"
            if re.search(named, original, re.I) and not re.search(named, script, re.I):
                problems.append(f"{name} drops {who}, a locked character")
        if words and abs(spoken_words(script) - words) > 0.3 * words:
            problems.append(
                f"{ADVICE}{name} has {spoken_words(script)} spoken words, the original {words}"
            )
        total, was = len(script.split()), len(original.split())
        if was and abs(total - was) > 0.3 * was:
            problems.append(f"{ADVICE}{name} runs {total} words in all, the original {was}")
        if _close(script, original):
            problems.append(f"{ADVICE}{name} is very close to the original; regenerate with a note")
        if bad := next((x for x in lines if LOOSE.match(x)), None):
            problems.append(f"{ADVICE}{name}: “{bad[:40]}” isn't house format")
    if len(scripts) == 2 and _close(scripts[1], scripts[0]):
        problems.append(f"{ADVICE}the two variations are very close; regenerate one with a note")
    return problems


def _stars(script: str) -> set[str]:
    return {m.group(1).strip() for line in script.splitlines() if (m := STAR.match(line.strip()))}


def _close(a: str, b: str) -> bool:
    """Over 70% of a's word pairs also appear in b."""
    pairs = lambda text: set(zip(*[_words(text).split()[i:] for i in range(2)], strict=False))  # noqa: E731
    mine = pairs(a)
    return bool(mine) and len(mine & pairs(b)) / len(mine) > 0.7


AGE = re.compile(  # "17", "30s", "mid-40s", "teen", "elderly", "toddler", "puppy"
    r"\b(\d{1,2}s?|teen\w*|child|kid|toddler|baby|young|old|elderly|middle-aged|adult|senior|"
    r"puppy|kitten)\b",
    re.I,
)
GENDER = re.compile(r"\b(man|woman|men|women|boy|girl|male|female|guy|lady|non-binary)\b", re.I)
BACKGROUND = re.compile(
    r"\b(guests?|crowd|admirers?|extras?|bystanders?|passers?-by|onlookers?)\b", re.I
)


def cast_slots(versions: dict[int, str], result: CastSlots, cast: list[str] = ()) -> list[str]:
    """The roles every version needs a look for (Reed, #197). Fixes: no slots, a version that
    doesn't exist. Advice: a background-sounding role, a name a listed version never uses,
    two slots with one name, a name the cast or the scripts' speakers use that no slot carries.
    `cast` holds the cast's names."""
    if not result.slots:
        return ["no cast slots; regenerate"]
    problems, seen = [], set()
    roles = " | ".join(s.role for s in result.slots).lower()
    speakers = {
        m.group(1).split(" (")[0].title()
        for text in versions.values()
        for m in re.finditer(r"^([A-Z][A-Z .'-]*?)(?: \([^)]*\))?:", text, re.M)
    }
    speakers -= {"Voiceover", "Narrator", "Vo", "V.O.", "Off Screen", "All", "Both"}  # labels
    for name in dict.fromkeys([*cast, *sorted(speakers)]):
        if not re.search(rf"\b{re.escape(name.lower())}\b", roles):
            problems.append(f"{ADVICE}no slot carries the name {name}; use it in that role")
    for slot in result.slots:
        role = slot.role
        if missing := sorted(set(slot.appears_in) - set(versions)):
            problems.append(f"{role}: version {missing[0]} doesn't exist; edit or regenerate")
        who = [w for w, rx in (("age", AGE), ("gender", GENDER)) if not rx.search(slot.description)]
        if who:  # a teacher drawn as a child (Reed: looks must fit the role)
            problems.append(f"{ADVICE}{role}: the description doesn't say their {' or '.join(who)}")
        if BACKGROUND.search(role):
            problems.append(f"{ADVICE}{role}: sounds like background people, who are never cast")
        name = re.split(r"[ ,(]", role.strip(), maxsplit=1)[0]
        named = rf"\b{re.escape(name)}\b"
        if any(re.search(named, text, re.I) for text in versions.values()):  # a script name
            for v in sorted(set(slot.appears_in) & set(versions)):
                if not re.search(named, versions[v], re.I):
                    problems.append(f"{ADVICE}{role}: “{name}” isn't in version {v}")
            if name.lower() in seen:
                problems.append(f"{ADVICE}two slots are called {name}; merge them")
            seen.add(name.lower())
    return problems


def reference_lines(script: str, reel: list[str], new_lines: bool = False) -> list[str]:
    """When a draft adapts a reference with new_lines off, every reel line stays word for word
    (Reed, #271). Advice lists each one changed or missing, so the editor can see the swap."""
    if new_lines:
        return []
    said = _plain("\n".join(re.findall(r"^[A-Z][A-Z .'()-]*:\s*(.*)$", script, re.M)))
    return [f"{ADVICE}the reel's line “{x}” is changed or missing"
            for x in reel if _plain(x) not in said]  # fmt: skip


def _plain(text: str) -> str:
    """Curly quotes as straight ones and whitespace evened out: a phone or a model may type
    either, and only the words count."""
    return _exact(_straight(text))


def reel_watch(watch: ReelWatch, cuts: list[dict], transcript: list[dict]) -> list[str]:
    """Gemini's read of an imported reel against prep's cut list [{n, start, end}] and
    transcript [{start, end, text}]. Fixes: a shot that isn't one of the cuts, a speaker for a
    line that doesn't exist. Advice: a line with no speaker, one person under two names, a line
    in a live-action shot (it's dropped with the shot)."""
    problems = []
    got = [(s.n, s.start, s.end) for s in watch.shots]
    want = [(c["n"], c["start"], c["end"]) for c in cuts]
    off = [(w or g)[0] for w, g in zip_longest(want, got) if not (w and g and _same_cut(w, g))]
    if off:
        n = off[0]
        problems.append(
            f"shot {n} isn't the cut list's ({len(got)} shots, {len(want)} cuts); regenerate"
        )
    named = {}
    for s in watch.speakers:
        if not 1 <= s.line <= len(transcript):
            problems.append(f"a speaker for line {s.line}, which the transcript doesn't have")
        named.setdefault(s.line, s.speaker)
    for n, x in enumerate(transcript, 1):
        if not named.get(n, "").strip():
            problems.append(f"{ADVICE}no speaker for “{x['text']}”; say who says it")
    roles = {}
    for name in dict.fromkeys(named.values()):
        roles.setdefault(role_key(name), []).append(name)
    problems += [f"{ADVICE}one person under {len(v)} names ({', '.join(v)}); use one"
                 for v in roles.values() if len(v) > 1]  # fmt: skip
    problems += misheard(transcript)
    live = [s for s in watch.shots if s.live_action]
    for x in transcript:
        if any(s.start <= x["start"] < s.end for s in live):
            problems.append(f"{ADVICE}“{x['text']}” is in a live-action shot, so it's dropped")
    return problems


def _same_cut(a: tuple, b: tuple) -> bool:
    """Same shot number, times within 0.05 s (a model rounds; the server keeps prep's times)."""
    return a[0] == b[0] and abs(a[1] - b[1]) <= 0.05 and abs(a[2] - b[2]) <= 0.05


def role_key(name: str) -> str:
    """'The bride (flashback)' and 'bride' are one person."""
    return re.sub(r"^(the|a|an)\s+|\s*\(.*?\)", "", name.strip().lower()).strip()


def reel_speakers(
    script: str, speakers: list[str], cast: list[str] = (), end_line: str = "", brand: str = ""
) -> list[str]:
    """No invented speakers in a draft that adapts an imported reel: it has no more speaking
    characters than the reel (`speakers`, its kept shots' roles), not counting one who only
    says the brand's end line. Names the reel or `cast` doesn't have are listed. Advice."""
    said = {}
    for m in re.finditer(r"^([A-Z][A-Z .'-]*?)(?: \([^)]*\))?:\s*(.*)$", script, re.M):
        said.setdefault(role_key(m.group(1)), []).append(m.group(2))
    if end_line:
        said = {
            k: v for k, v in said.items() if any(ends_on(end_line, x, brand) == "no" for x in v)
        }
    reel = {role_key(x) for x in speakers if x.strip()}
    if len(said) <= len(reel):
        return []
    known = reel | {role_key(x) for x in cast}
    new = [k.title() for k in said if k not in known] or [k.title() for k in said]
    return [f"{ADVICE}{len(said)} people speak, the reel has {len(reel)}; "
            f"give {', '.join(new)}'s lines back to who says them in the reel"]  # fmt: skip


REWORD = re.compile(
    r"\b(add|cut|remove|drop|change|reword|rewrite|replace|swap|new)\s+(?:[\w'-]+\s+){0,2}"
    r"(line|lines|dialogue|words?)\b|\bsays? (something else|instead)\b",
    re.I,
)
SPEAKS = re.compile(
    r"\b([A-Z][a-z]+)(?: should| could| to)? (say|says|speak|speaks|talk|talks|shout|shouts|"
    r"whisper|whispers|reply|replies|answer|answers)\b"
)


def _first(speaker: str) -> str:
    return speaker.split(" (")[0].split()[0].lower()


def redo_note(note: str, bd: Breakdown, clip_id: str) -> list[str]:
    """A Redo note ("What's wrong?") changes how the take plays, never what is said: it can't
    quote words the clip doesn't have, ask to add, cut or reword a line, or make someone speak
    who has no line in this clip (Reed, 2026-10-25)."""
    shots = {shot.id: shot for scene in bd.scenes for shot in scene.shots}
    clip = next((c for c in bd.clips if c.id == clip_id), None)
    ids = clip.shot_ids if clip else []
    lines = [_exact(shots[i].line) for i in ids if i in shots and shots[i].line]
    who = {
        _first(shots[i].speaker) for i in ids if i in shots and shots[i].line and shots[i].speaker
    }
    known = {_first(shot.speaker) for shot in shots.values() if shot.speaker}
    problems = []
    for quote in QUOTED.findall(note):
        if _exact(quote) not in lines:
            problems.append(
                f"The note quotes “{quote}”, which nobody says in this clip. A note can change "
                "how a line is said, never its words."
            )
    if REWORD.search(note):
        problems.append(
            "The note changes what's said. The spoken lines stay exactly as written; say how "
            "they should sound instead (louder, angrier, slower)."
        )
    for name, _ in SPEAKS.findall(note):
        if name.lower() in known and name.lower() not in who:
            problems.append(
                f"{name} has no line in this clip, so the note can't make them speak."
                if who
                else "Nobody speaks in this clip, so the note can't add speech."
            )
    return list(dict.fromkeys(problems))


VO_LINE = re.compile(r"^([A-Z][A-Z .'-]*?) \((?:V\.O\.|VO|voice-over)\):\s*(.*)$", re.I)
SAID_LINE = re.compile(r"^([A-Z][A-Z .'-]*?)(?: \([^)]*\))?:\s*(.*)$")


def echo_lines(script: str) -> list[str]:
    """An echo (a V.O. from a character who also speaks on screen) repeats something they said
    earlier, so the callback lands (Reed, live test 2026-10-26). Advice naming the closest
    earlier line. A narrator heard only in V.O. is never an echo."""
    problems, said = [], {}
    for line in (x.strip() for x in script.splitlines()):
        if (m := VO_LINE.match(line)) and m.group(1).upper() in said:
            words, earlier = _words(m.group(2)), said[m.group(1).upper()]
            if words and not any(words in _words(e) for e in earlier):
                best = max(earlier, key=lambda e: len(set(words.split()) & set(_words(e).split())))
                problems.append(
                    f"{ADVICE}the echo “{m.group(2)}” calls back to nothing "
                    f"{m.group(1).title()} said; repeat “{best}”"
                )
        elif (m := SAID_LINE.match(line)) and not VO_LINE.match(line):
            said.setdefault(m.group(1).upper(), []).append(m.group(2))
    return problems


def misheard(transcript: list[dict]) -> list[str]:
    """A line that ends like an earlier one (5+ words) but starts differently is often a
    mishearing of an echo ("New position doesn't get invited to anything." after "You're just
    a loser who doesn't get invited to anything."). Advice, so the editor checks the reel."""
    problems, seen = [], []
    for x in transcript:
        words = _words(x["text"]).split()
        for earlier in seen:
            had = _words(earlier).split()
            tail = next((n for n in range(min(len(words), len(had)), 0, -1)
                         if words[-n:] == had[-n:]), 0)  # fmt: skip
            if tail >= 5 and tail < len(words) and words[:-tail] != had[:-tail]:
                problems.append(
                    f"{ADVICE}“{x['text']}” ends like “{earlier}”; if it echoes it, the "
                    "transcript may have misheard the start"
                )
                break
        seen.append(x["text"])
    return problems


PAYOFFS = {  # the got-rich run copied too often (Reed, 2026-10-27): one example among many
    "keys": r"\bkeys\b",
    "a car": r"\b(?:car|coupe|supercar|sports car|suv|lamborghini|lambo|ferrari|porsche)\b"
    r"|behind the wheel",
    "a penthouse": r"\bpenthouse\b",
    "a balcony": r"\b(?:balcony|terrace)\b",
    "a skyline": r"\bskyline\b",
    "a mansion": r"\b(?:mansion|villa)\b",
    "a yacht": r"\byacht\b",
    "a private jet": r"\bprivate jet\b",
}


def payoffs(text: str) -> list[str]:
    """The stock payoffs a montage shows, in the order it first shows them."""
    found = [(m.start(), name) for name, pat in PAYOFFS.items()
             if (m := re.search(pat, text, re.I))]  # fmt: skip
    return [name for _, name in sorted(found)]


def montage_text(script: str) -> str:
    """A script's montage action lines (the house format names them "Wordless montage, …")."""
    return " ".join(x for x in script.splitlines() if "montage" in x.lower())


def repeated_payoffs(mine: str, earlier: str, whose: str) -> list[str]:
    """Advice when a montage shows two or more of the stock payoffs an earlier one showed (the
    reference's or the original's): each video invents its own."""
    same = [x for x in payoffs(mine) if x in payoffs(earlier)]
    if len(same) < 2:
        return []
    return [f"{ADVICE}the montage repeats {whose} payoffs ({', '.join(same)}); invent ones "
            "that fit this story and its people"]  # fmt: skip


READ_AGAIN = (
    "Notes can fix who's speaking, the shots and the camera, but not the words said in the "
    "reel. Change the words in the script instead."
)


def reel_note(note: str, said: list[str]) -> str:
    """A Read it again note (reel-import.md §5) fixes the reading, never the reel's words: no
    asking to add, cut or reword a line, and no quoting words nobody says. '' if it's fine."""
    spoken = {_exact(x) for x in said}
    quoted = [q for q in QUOTED.findall(note) if q.strip()]
    if REWORD.search(note) or any(_exact(q) not in spoken for q in quoted):
        return READ_AGAIN
    return ""
