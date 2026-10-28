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
FLAGGED = re.compile(  # Nano Banana refused frames with these (E005 "sensitive"), 2026-10-23;
    # not everyday words that over-flag: a dog's "crusty eyes", "her lap" (Reed's frame, 10-28)
    r"\b(leggings|thighs?|cleavage|pus|ooz\w*|discharge|blood\w*|wounds?|vomit\w*)\b",
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


def payoff(shots: list) -> list:
    """Where the montage lands: the last 3 shots of its first run of 3+ quick wordless shots
    (as the montage checks below count them); [] without a montage."""
    quick = [not s.line and s.seconds <= 0.6 for s in shots]
    start = next((i for i in range(len(shots) - 2) if all(quick[i : i + 3])), None)
    if start is None:
        return []
    end = start
    while end + 1 < len(shots) and quick[end + 1]:
        end += 1
    return shots[end - 2 : end + 1]


DEVICE = {"mobile", "desktop"}  # what a screen is shown on, not what kind of screen it is
BALANCE = "$balance"  # a screen that prints a balance (the win needs one: Home (rich))


def kinds_of(screens) -> dict[str, set[str]]:
    """Each brand screen's kind tags, with BALANCE when its picture prints one."""
    return {f"screen:{s.id}": {*s.tags, *([BALANCE] if s.balance else [])} for s in screens}


def moment_screen(shot, screens: dict[str, list[str]], kinds: dict[str, set[str]]) -> str:
    """A brand moment's shot shows one of its screens, or a screen of the same kind (any
    "home" screen for fomo-mention: Home or Home (rich), Reed 2026-10-27). A screen that
    prints a balance (the win's) is only stood in for by one that prints one too. Advice,
    never a block; "" when it does."""
    needed = {sid for sid, moments in screens.items() if shot.moment in moments}
    if not needed or needed & set(shot.screen_ids):
        return ""

    def stands_in(shown: str, want: str) -> bool:
        a, b = kinds.get(shown, set()), kinds.get(want, set())
        same = (a & b) - DEVICE - {BALANCE}
        return bool(same) and (BALANCE not in b or BALANCE in a)

    if any(stands_in(s, n) for s in shot.screen_ids for n in needed):
        return ""
    return f"{ADVICE}shot {shot.id}: '{shot.moment}' moment without its screen"


def breakdown(
    script: str,
    bd: Breakdown,
    screens: dict[str, list[str]],
    min_s: int,
    max_s: int,
    end_line: str = "",
    brand: str = "",  # the brand's name: the closing call to action says it
    kinds: dict[str, set[str]] | None = None,  # each screen's type tags ("home"): moment_screen
    recent: list[str] = (),  # recent videos' payoff actions (montage variety, Reed 2026-10-27)
) -> list[str]:
    lines = script.splitlines()
    shots = [shot for scene in bd.scenes for shot in scene.shots]
    problems = []
    said = [TAG.sub("", text) for text in lines if text.strip()]
    said = [text for text in said if not text.startswith(("SCENE", SCREEN_LINE, "["))]
    if end_line.strip() and not says_brand(said[-1] if said else "", brand):
        problems.append(f"{ADVICE}{NO_CTA}")
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
    seen = {_words(a) for a in recent}
    problems += [f"{ADVICE}shot {s.id}: this payoff repeats one of a recent video; show a new one"
                 for s in payoff(shots) if _words(s.action) in seen]  # fmt: skip
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
    scene_of = {shot.id: scene.id for scene in bd.scenes for shot in scene.shots}
    for clip in bd.clips:
        total = sum(by_id[s].seconds for s in clip.shot_ids if s in by_id)
        if not min_s <= clip.seconds <= max_s:
            problems.append(f"clip {clip.id}: {clip.seconds} s is outside {min_s}–{max_s} s")
        if clip.seconds < total - 0.5:
            problems.append(f"clip {clip.id}: {clip.seconds} s is shorter than its shots")
        screens = {sid for s in clip.shot_ids if s in by_id for sid in by_id[s].screen_ids}
        if len(screens) > 3:  # the model mixes them up (fomo montage run 3, 2026-10-24)
            problems.append(f"clip {clip.id}: {len(screens)} screens; keep the 3 its beats need")
        scenes = list(dict.fromkeys(scene_of[s] for s in clip.shot_ids if s in scene_of))
        if len(scenes) > 1:  # one scene per clip, for continuity (rule 29, Reed 2026-10-28)
            problems.append(f"{ADVICE}clip {clip.id} crosses scenes {', '.join(map(str, scenes))}; "
                            "end it where the place or time changes")  # fmt: skip
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


def _screens_climb(prompt: str) -> list[str]:
    """Reed (#650, rule 14): each invented trading screen in a clip's shots reads bigger than
    the last; a red day (a loss) is exempt. Advice."""
    problems, last = [], {}
    for n, text in SHOT_ANY.findall(prompt):
        for part in text.split("trading screen")[1:]:
            if not (fig := _figure(part)) or fig[1] < 0:
                continue
            kind, value, found = fig
            if kind in last and value <= last[kind][1]:
                problems.append(f"shot {n}'s trading screen reads {found}, not more than shot "
                                f"{last[kind][0]}'s; make each win bigger")  # fmt: skip
            last[kind] = (n, value)
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
                    problems.append(  # attached in code when there's room: never a block
                        f"{ADVICE}{c.clip_id}: shot {sid}'s screen {screen} isn't attached"
                    )
                elif f"[Image{images.index(screen) + 1}]" not in c.prompt:
                    problems.append(f"{c.clip_id}: screen {screen} is attached but never shown")
            said = [_exact(q) for q in QUOTED.findall(c.prompt)]
            line = _exact(shot.line or "")
            times = sum(_exact(shots[s].line or "") == line for s in clip.shot_ids)
            if shot.line and said.count(line) != times:
                problems.append(f"{c.clip_id}: shot {sid}'s line isn't there once, word for word")
        if _montage(clip.shot_ids, shots):  # guests and crowds elsewhere are never cast
            problems += [f"{ADVICE}{c.clip_id}: {p}" for p in _cuts_name_someone(c.prompt)]
            problems += [f"{ADVICE}{c.clip_id}: {p}" for p in _screens_climb(c.prompt)]
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
            problems.append(  # Advice: the editor can draw it as is (Reed, 2026-10-28)
                f"{ADVICE}{f.clip_id}: the image model may refuse “{', '.join(flagged)}”; "
                "soften it or draw it as is"
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
        which = "the last shot" if k == len(shots) - 1 else f"shot {number}"
        times = re.match(r" ?(\d+(?:\.\d+)?) ?[-–] ?(\d+(?:\.\d+)?) ?s\b(\.?)", rest)
        if not times:
            return f"{which} has no times; write them like “0-2 s.”"
        if "." in times[1] + times[2]:  # the real reason, never when they are whole (c4)
            return f"{which}'s times aren't whole seconds; write them like “0-2 s.”"
        if not times[3]:
            return f"{which}'s times need a full stop after “s”, like “0-2 s.”"
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
    lines = prompt.strip().splitlines() or [""]  # an empty prompt is a problem, never a crash
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


NO_CTA = "the last line doesn't mention the brand or where to find it"


def cta_screen(shots: list, end_line: str, brand: str = "") -> list[str]:
    """The end line's shot (the call to action) shows the brand's real screen, on the phone the
    hero holds up to the camera (Reed, 2026-10-27): its clip then attaches it (`clip_prompts`)."""
    said = [s for s in shots if end_line.strip() and s.line and says_brand(s.line, brand)]
    if said and not said[-1].screen_ids:
        return [f"{ADVICE}shot {said[-1].id}: the end line's shot shows no screen; show the "
                "brand's real screen on the phone he holds up to the camera"]  # fmt: skip
    return []


def says_brand(line: str, brand: str) -> bool:
    """Does a spoken line name the brand (whole words, any case: "Download FOMO…")? A video
    ends on a call to action that names it; the saved end line is only the default wording,
    so this is all the end check asks (Current rules 18, Reed 2026-10-28). Advice."""
    return bool(_words(brand)) and f" {_words(brand)} " in f" {_spoken(line)} "


SPEAKER = re.compile(r"^\s*[A-Z][A-Z .'-]*(?:\([^)]*\))?:")  # "NATE:" or "NATE (V.O.):"


def _spoken(line: str) -> str:
    return _words(_straight(SPEAKER.sub("", line)))


def _straight(text: str) -> str:
    return text.translate(str.maketrans("‘’“”", "''\"\""))


def _words(text: str) -> str:
    return " ".join(re.findall(r"[\w']+", text.lower()))


STAR = re.compile(r"^★ .*?(?:screen|product): (.+?)(?: — .*)?$")  # "★ fomo screen: Home — …"
LOOSE = re.compile(r"^(#|\*\*|- |\* |Title:|Premise:|Variation )")  # markdown, not house format


def asked_seconds(note: str) -> int | None:
    """The length a variations note asks for, in seconds ("about 45 s", "1 minute"), or None."""
    if m := re.search(r"(\d+)\s*(?:s|secs?|seconds)\b", note, re.I):
        return int(m[1])
    if m := re.search(r"(\d+)\s*(?:mins?|minutes?)\b", note, re.I):
        return int(m[1]) * 60
    return None


def variations(
    original: str,
    result: Variations,
    screens: dict[str, list[str]],
    end_line: str,
    never_say: list[str],
    count: int,
    cast: list[str] = (),
    brand: str = "",  # the brand's name: the closing call to action says it
    note: str = "",  # the author's note: a length it asks for ("about 45 s") is the target
) -> list[str]:
    """Alternates of an approved script (workflow v2): the brand, the end line and the locked
    cast are kept (fix); length, closeness and format are advice. `cast` holds the locked
    characters' names. `screens` is accepted for the server's call; ★ lines are matched by name."""
    asked = asked_seconds(note)
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
        if end_line.strip() and not says_brand(said[-1] if said else "", brand):
            problems.append(f"{ADVICE}{name}: {NO_CTA}")
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
        n = spoken_words(script)
        if asked:  # the house guide: 30 s is about 50-75 spoken words
            low, high = round(asked * 5 / 3), round(asked * 5 / 2)
            if not low <= n <= high:
                problems.append(f"{ADVICE}{name} has {n} spoken words; about {low}–{high} fit "
                                f"the {asked} s asked for")  # fmt: skip
        elif words and abs(n - words) > 0.3 * words:
            problems.append(f"{ADVICE}{name} has {n} spoken words, the original {words}")
        total, was = len(script.split()), len(original.split())
        if not asked and was and abs(total - was) > 0.3 * was:
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
    two slots with one name, a name the cast or the scripts' speakers use that no slot carries,
    a `may_be_same_as` that names no other slot. `cast` holds the cast's names."""
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
        part = re.sub(r"\([^)]*\)", "", role.split(",", 1)[-1]).split()  # "Nate's rich friend"
        noun = rf"\b{re.escape(part[-1])}\b" if "," in role and part else named
        if any(re.search(named, text, re.I) for text in versions.values()):  # a script name
            for v in sorted(set(slot.appears_in) & set(versions)):  # or "his rich friend" there
                if not re.search(named, versions[v], re.I) and not re.search(
                    noun, versions[v], re.I
                ):
                    problems.append(f"{ADVICE}{role}: “{name}” isn't in version {v}")
            if name.lower() in seen:
                problems.append(f"{ADVICE}two slots are called {name}; merge them")
            seen.add(name.lower())
    others = {s.role for s in result.slots}
    for slot in result.slots:  # a possible duplicate the editor confirms (Reed, 2026-10-27)
        if slot.may_be_same_as and slot.may_be_same_as not in others - {slot.role}:
            problems.append(
                f"{ADVICE}{slot.role}: may be the same as “{slot.may_be_same_as}”, which isn't "
                "another slot; name that slot's role word for word"
            )
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
    says the closing call to action. Names the reel or `cast` doesn't have are listed. Advice."""
    said = {}
    for m in re.finditer(r"^([A-Z][A-Z .'-]*?)(?: \([^)]*\))?:\s*(.*)$", script, re.M):
        said.setdefault(role_key(m.group(1)), []).append(m.group(2))
    if end_line:
        said = {k: v for k, v in said.items() if any(not says_brand(x, brand) for x in v)}
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
