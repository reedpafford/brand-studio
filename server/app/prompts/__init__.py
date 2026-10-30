"""Director-owned prompts for the script-guided flow (issue #24).

A Claude call's system prompt is two cached parts: `system(step)` (the shared rules, the step's
prompt and its worked example) and `brand_block(...)` for the brand. The step's prompt file
lists the tags the user message must carry; `number_lines` formats a script for them.
Each step's output schema is `SCHEMAS[step]`."""

import json
import re
from functools import cache
from html import escape
from pathlib import Path

from app.prompts import schemas

HERE = Path(__file__).parent
SCHEMAS = {
    "enhance": schemas.EnhanceResult,
    "script_draft": schemas.ScriptDrafts,
    "breakdown": schemas.Breakdown,
    "storyboard": schemas.StoryboardFrames,
    "clip_prompts": schemas.ClipPrompts,
    "improve": schemas.ImprovedPrompt,
    "change": schemas.ChangedPrompt,
    "variations": schemas.Variations,
    "cast_slots": schemas.CastSlots,
    "look_fit": schemas.LookFit,
    "song_directions": schemas.SongDirections,
    "song_breakdown": schemas.SongBreakdown,
    "song_clip_prompts": schemas.ClipPrompts,
    "narrated_breakdown": schemas.SongBreakdown,  # flows V6n: the narration is the clock
    "narrated_clip_prompts": schemas.ClipPrompts,
    "plan": schemas.ScenePlan,  # flows P1: the scene plan, before the breakdown
    "plan_scene": schemas.PlanScene,  # P1's "Change this scene…"
    "item_check": schemas.ItemCheck,  # flows P4: the advisory check on a still or a take
    "narration_music": schemas.NarrationMusic,  # flows N1: the bed under the narrator
    "site_read": schemas.SiteRead,  # flows BR2: Import from website
    "language_sample": schemas.ScriptDrafts,  # flows VS1: a language's sample test
}
# A song video's step is the story step plus its own part (story prompts stay as they were).
EXTENDS = {
    "song_breakdown": "breakdown",
    "song_clip_prompts": "clip_prompts",
    "narrated_breakdown": "breakdown",
    "narrated_clip_prompts": "clip_prompts",
    "plan_scene": "plan",
    "language_sample": "script_draft",
}
NO_RULES = {
    "look_fit",
    "narration_music",
    "item_check",
    "site_read",
}  # not script writers: the rules would only add tokens


# A style's extra guidance, by the steps it's added to (styles/*.md); its look sections fill
# the {{tokens}} in the step files instead.
GUIDES = {
    "still": ["storyboard"],
    "clip": ["clip_prompts", "song_clip_prompts", "narrated_clip_prompts", "improve"],
    "breakdown": ["breakdown", "song_breakdown", "narrated_breakdown", "plan", "plan_scene"],
    "script": ["script_draft", "enhance", "variations"],
}
TOKEN = re.compile(r"\{\{(\w+)\}\}")


@cache
def styles() -> list[dict]:
    """The style registry, in Reed's order: one styles/<id>.md each (Reed, 2026-10-28). Each is
    {id, name, kind ("look" or "format"), order, on, image_model, blurb, sections}.
    `on` is only the starting switch (House alone); the server keeps Reed's own."""
    out = []
    for path in (HERE / "styles").glob("*.md"):
        head, *sections = path.read_text().split("\n## ")
        meta = dict(m.groups() for m in re.finditer(r"^(\w+): (.+)$", head, re.M))
        out.append({
            "id": path.stem,
            "name": head.splitlines()[0].removeprefix("# "),
            "kind": meta["kind"],
            "order": int(meta["order"]),
            "on": meta["on"] == "yes",
            "own_sample": meta.get("own_sample") == "yes",  # ST3: never the brand's hero
            "image_model": meta["image_model"],
            "blurb": meta["blurb"],
            "sections": {k: v.strip() for k, v in (x.split("\n", 1) for x in sections)},
        })  # fmt: skip
    return sorted(out, key=lambda s: s["order"])


# A look's data, never sent to a model as guidance (flows ST2, ST3): words repaired in its picture
# descriptions, the fix offered for each failure, and the sample still's person.
DATA = {"banned", "fixes", "sample"}


def look_banned(look_id: str) -> list[tuple[str, str]]:
    """The look's banned words and their replacements ("" deletes): its `## banned` lines."""
    lines = style(look_id)["sections"].get("banned", "").splitlines()
    return [(a.strip(), b.strip()) for a, _, b in (x.partition("→") for x in lines if "→" in x)]


def look_sample(look_id: str) -> str:
    """The person in the look's sample still when the brand has no hero (flows ST3): its
    `## sample` line, or "" when it has none (the server then uses its own default)."""
    return style(look_id)["sections"].get("sample", "").strip()


def sample_still_prompt(look_id: str, name: str = "", from_picture: bool = False) -> str:
    """The prompt for a look's sample still (flows ST3). With `from_picture`, [Image1] is the
    brand's hero drawn in another look: it says who they are, never how they're drawn, so
    the sample doesn't copy the House look (Reed, 2026-10-29: samples read as generic Pixar).
    Without it, the look's own `## sample` person."""
    look = style(look_id)["sections"]
    if from_picture:
        who = (f"{name}, the same person as in [Image1]: the same face, hair, colouring, age and "
               "outfit, redrawn completely in this look. [Image1] is drawn in another style: "
               "copy who they are, never how they are drawn.")  # fmt: skip
    else:
        who = look_sample(look_id) or "A friendly adult in their thirties in one plain outfit"
    return (
        f"{look['still_look'].strip()}\nThe character, drawn in this look: "
        f"{look['sheet_look'].strip()}\n{who.rstrip('.')}.\nA calm, friendly portrait, "
        "looking into the camera, the whole figure in frame. No text on screen."
    )


def look_fixes(look_id: str) -> dict[str, str]:
    """The look's fix for each failure id (refused, face, outfit, product): `## fixes`."""
    lines = style(look_id)["sections"].get("fixes", "").splitlines()
    return {a.strip(): b.strip() for a, _, b in (x.partition(":") for x in lines if ":" in x)}


def style(style_id: str) -> dict:
    found = [s for s in styles() if s["id"] == style_id]
    if not found:
        raise ValueError(f"unknown style: {style_id}")
    return found[0]


def _styled(text: str, style_id: str) -> str:
    looks = style(style_id)["sections"]
    return TOKEN.sub(lambda m: looks[m.group(1)], text)


@cache
def system(step: str, style_id: str = "house") -> str:
    parts = [] if step in NO_RULES else [(HERE / "rules.md").read_text()]
    for name in filter(None, [EXTENDS.get(step), step]):
        parts.append(_styled((HERE / f"{name}.md").read_text(), style_id))
    example = HERE / "examples" / f"{step}.json"
    if example.exists():
        ex = json.loads(example.read_text())
        parts.append(
            f"## Worked example ({ex['source']})\n{ex['note']}\n\n"
            f"<example_input>\n{ex['input']}\n</example_input>\n\n"
            f"<example_output>\n{json.dumps(ex['output'], indent=1)}\n</example_output>"
        )
    chosen = style(style_id)
    guide = [chosen["sections"][k] for k, steps in GUIDES.items()
             if step in steps and k in chosen["sections"]]  # fmt: skip
    if guide:
        parts.append(
            f"## Style: {chosen['name']}\nThis video is in the {chosen['name']} style. Where "
            "this section and anything above (the worked example included, which is in the "
            "House style) differ, this section wins.\n\n" + "\n\n".join(guide)
        )
    return "\n\n".join(parts)


def number_lines(script: str) -> str:
    return "\n".join(f"{n}| {line}" for n, line in enumerate(script.splitlines(), 1))


# The moments the project's product (e.g. the Iron Paws bag) must be on screen.
PRODUCT_MOMENTS = ["product", "feeding", "brand-mention", "end"]


def required(screens: list[dict], product: dict | None = None) -> dict[str, list[str]]:
    """Asset id -> the moments it must be shown at, as `check.*` takes it ('screens')."""
    out = {f"screen:{s['id']}": s.get("default_for", []) for s in screens}
    if product:
        out[f"product:{product['id']}"] = PRODUCT_MOMENTS
    return out


def brand_block(brand: dict, screens: list[dict], product: dict | None = None) -> str:
    """`brand`: name, tone_notes, never_say, legal_line, end_line. `screens`: id, name, tags,
    default_for (the moments a screen is required at) and, when its picture prints one,
    balance (e.g. "$348,920.15": the got-rich payoff uses it). `product`: the one product
    this project picked (id, name), e.g. the Iron Paws peanut butter bag."""
    lines = [f"<brand>\nBrand: {brand['name']}"]
    if brand.get("tone_notes"):
        lines.append(f"Tone: {brand['tone_notes']}")
    if brand.get("never_say"):
        lines.append("Never say: " + "; ".join(brand["never_say"]))
    if brand.get("end_line"):
        lines.append(  # Current rules 18: the default wording, adapted to the story if needed
            "End line (the default call to action every video ends on; it may be adapted to "
            f"the story if it still names the brand and where to find it): {brand['end_line']}"
        )
    if brand.get("legal_line"):
        lines.append(f"Legal line (added in post, don't write it): {brand['legal_line']}")
    needed = [s for s in screens if s.get("default_for")]
    if needed:
        lines.append(
            "Required screens. Every shot at one of these moments shows the matching screen, "
            "attached as a reference image: logo, colours and layout exact, numbers free; a "
            "logo-only screen comes as the logo alone, and the screen is invented around it:"
        )
        lines += [_screen(s) + f" — required at: {', '.join(s['default_for'])}" for s in needed]
        by_moment: dict[str, list[str]] = {}
        for s in needed:
            for m in s["default_for"]:
                by_moment.setdefault(m, []).append(s["name"])
        lines += [f"At {m}, one of these is enough: {' or '.join(names)}."  # Home or Home (rich)
                  for m, names in by_moment.items() if len(names) > 1]  # fmt: skip
    if product:
        lines.append(
            f'Required product: product:{product["id"]} "{product["name"]}", attached as a '
            "reference image and shown exactly (label to camera, no face) — required at: "
            + ", ".join(PRODUCT_MOMENTS)
        )
    if needed or product:
        moments = sorted(set(sum((m for m in required(needed, product).values()), [])))
        lines.append(f"Moments: {', '.join(moments)}")
    else:
        lines.append("This brand has no required screens.")
    others = [s for s in screens if not s.get("default_for")]
    if others:
        lines.append("Other screens (use where they fit):")
        lines += [_screen(s) for s in others]
    lines.append("</brand>")
    return "\n".join(lines)


def _screen(s: dict) -> str:
    shows = f", shows a balance of {s['balance']}" if s.get("balance") else ""  # printed on it
    shows += ", logo-only: the logo is attached, the screen invented" * bool(s.get("logo_only"))
    return f'- screen:{s["id"]} "{s["name"]}" ({", ".join(s.get("tags", []))}){shows}'


def reference_block(ref: dict, replace: str = "") -> str:
    """A reference reel's breakdown (docs/references/*/BREAKDOWN.json shape) as a <reference>
    tag: hook, beats and the shot list with timing, framing, action, emotion and lines.
    On-screen text is left out on purpose (never copied). `replace` says which part the
    editor wants rebuilt (e.g. the montage)."""
    hook = ref["hook"]
    lines = [
        f"<reference>\nStory: {ref['logline']}",
        f"Length: {ref['duration_seconds']:.0f} s. "
        f"Hook (0–{hook['seconds']} s): {hook['mechanic']}",
        "Beats:",
    ]
    live = [s for s in ref["shots"] if live_action(s)]
    live_from = live[0]["start"] - 0.05 if live else float("inf")
    for b in ref["beats"]:
        what = f"{b['summary']} ({b['emotion']})"
        if b["start"] >= live_from:
            what = "Live-action tag: removed; the brand's end line goes here."
        lines.append(f"- {b['start']:.1f}–{b['end']:.1f} s {what}")
    if m := ref.get("montage"):
        lines.append(
            f"Montage: {m['start']:.1f}–{m['end']:.1f} s ({m['end'] - m['start']:.1f} s): keep "
            "about this length (grind beats, then the payoff run)."
        )
    lines.append("Shots (time, framing, camera, action, emotion, line):")
    for s in ref["shots"]:
        if live_action(s):
            continue
        said = f' | {s["speaker"]}: "{s["line"]}"' if s.get("line") else ""
        lines.append(
            f"{s['n']}. {s['start']:.2f}–{s['end']:.2f} {s['framing']}; {s['camera']} | "
            f"{s['action']} | {s['emotion']}{said}"
        )
    if live:
        lines.append(
            f"Shots {live[0]['n']}–{live[-1]['n']} ({live[0]['start']:.2f}–{live[-1]['end']:.2f} s)"
            " are live action: always removed; that slot becomes the brand's end line."
        )
    if replace:
        lines.append(f"Replace: {replace}")
    lines.append("</reference>")
    return "\n".join(lines)


def watch_system() -> str:
    """Gemini's system prompt for watching an imported reel: reel_watch.md, its worked example
    and the ReelWatch JSON schema (Gemini has no structured output on Replicate, so it's in the
    text). The video and contact sheet go with the call; reel_watch_input(...) is the message."""
    ex = json.loads((HERE / "examples" / "reel_watch.json").read_text())
    schema = json.dumps(schemas.ReelWatch.model_json_schema())
    return (
        f"{(HERE / 'reel_watch.md').read_text()}\n\n## Worked example ({ex['source']})\n"
        f"{ex['note']}\n\n<example_input>\n{ex['input']}\n</example_input>\n\n"
        f"<example_output>\n{json.dumps(ex['output'])}\n</example_output>\n\n"
        f"## Answer\nOnly JSON matching this schema, no other text:\n{schema}"
    )


def reel_watch_input(transcript: list[dict], cuts: list[dict], frames_only: bool = False) -> str:
    """Prep's cut list [{n, start, end}] and transcript [{start, end, text}], numbered.
    `frames_only` when the video couldn't be sent and the watch gets frames instead."""
    shots = [f"{c['n']}. {c['start']:.2f}–{c['end']:.2f}" for c in cuts]
    said = [
        f"{n}| {x['start']:.2f}–{x['end']:.2f} {x['text']}" for n, x in enumerate(transcript, 1)
    ]
    head = ["<watched_from>frames</watched_from>"] if frames_only else []
    return "\n".join([*head, "<cuts>", *shots, "</cuts>", "<transcript>", *said, "</transcript>"])


def watch_breakdown(
    watch: "schemas.ReelWatch", transcript: list[dict], cuts: list[dict] = ()
) -> dict:
    """The watch answer plus prep's transcript as a BREAKDOWN.json-shaped dict, what
    reference_block(...) and the script's `reference_breakdown` take. Each line goes into the
    shot that holds its start; a live-action shot's style says so, and reference_block drops it.
    With prep's `cuts` [{n, start, end}], shot times are prep's, not the model's rounding."""
    times = {c["n"]: (c["start"], c["end"]) for c in cuts}
    who = {s.line: s.speaker for s in watch.speakers}
    lines = [x | {"speaker": who.get(n, "")} for n, x in enumerate(transcript, 1)]
    shots, last = [], watch.shots[-1] if watch.shots else None
    for s in watch.shots:
        start, end = times.get(s.n, (s.start, s.end))
        said = [x for x in lines if start <= x["start"] < (end if s is not last else 1e9)]
        shot = s.model_dump(exclude={"live_action"}) | {"start": start, "end": end}
        shot["dur"] = round(end - start, 2)
        shot["style"] = "live action" if s.live_action else watch.style
        shot["line"] = " / ".join(x["text"] for x in said)
        shot["speaker"] = " / ".join(dict.fromkeys(x["speaker"] for x in said))
        shots.append(shot)
    first = next((x["text"] for x in lines if x["start"] < watch.hook.seconds), "")
    return watch.model_dump(exclude={"shots", "speakers", "hook"}) | {
        "source": "imported reel",
        "duration_seconds": shots[-1]["end"] if shots else 0.0,
        "hook": watch.hook.model_dump() | {"first_line": first},
        "shots": shots,
        "lines": lines,
    }


def live_action(shot: dict) -> bool:
    style = shot.get("style", "").lower()
    return "live action" in style or "photoreal" in style


def reference_lines(refs: list[dict]) -> str:
    """The lines the server puts before an editor's Quick clip prompt, binding each attached
    image to what it is, in upload order. `refs`: one dict per image with `kind` (character,
    place, prop, screen, product), `name` and, for screens and products, `brand`.
    E.g. '[Image1] and [Image2] are Aiden. [Image3] is the fomo "Token chart up" screen,
    logo and layout exact.'"""
    groups: dict[tuple, list[int]] = {}
    for n, ref in enumerate(refs, 1):
        groups.setdefault((ref["kind"], ref["name"], ref.get("brand", "")), []).append(n)
    lines = []
    for (kind, name, brand), numbers in groups.items():
        tags = " and ".join(f"[Image{n}]" for n in numbers)
        verb = "are" if len(numbers) > 1 else "is"
        if kind == "screen":
            what = f'the {brand} "{name}" screen, logo and layout exact'
        elif kind == "product":
            what = f"the {brand} {name}, shown exactly"
        elif kind == "character":
            what = name
        else:
            what = f"the {name}"
        lines.append(f"{tags} {verb} {what}.")
    return " ".join(lines)


def sheet_prompt(
    kind: str,
    description: str = "",
    from_photo: bool = False,
    change: str = "",
    role: str = "",
    style_id: str = "house",
) -> str:
    """The Nano Banana prompt for a library item's reference picture. kind "character": a front
    / side / back turnaround sheet, from a description or (from_photo) an uploaded photo of a
    real person as image 1; "place": an empty establishing still. `change` is the editor's note
    when redoing a sheet (the last sheet goes in as the final image). `description` is the
    item's notes; `role` is the script's part for a look made from a cast slot ("Omar, the
    boyfriend"), given without its name. Names stay out so none is drawn. `style_id` is the
    style the sheet is drawn in (a sheet is per style)."""
    sections = _styled((HERE / "sheet.md").read_text(), style_id).split("\n## ")[1:]
    parts = {name: body.strip() for name, body in (s.split("\n", 1) for s in sections)}
    out = [parts[kind]]
    if kind == "character" and from_photo:
        out.append(parts["photo"])
    if description.strip():
        out.append(f"The {kind}: {description.strip()}")
    if part := role.split(",", 1)[-1].strip():  # "Omar, the boyfriend" -> "the boyfriend"
        out.append(f"In the story they are {part}; the age, gender and look fit that part.")
    if change.strip():
        out.append(parts["redo"].format(change=change.strip()))
    return " ".join(out)


SUNG_RATE = (2.0, 2.4)  # words a second Suno sang Reed's Iron Paws songs (365 words, 2:38–2:59)


def song_directions_input(
    brief: str,
    cast: list[str],
    music_style: str = "",
    seconds: int | None = None,
    note: str = "",
    source: str = "",
    sounds_like: str = "",
    reference: str = "",
) -> str:
    """The user message for the song_directions step (with brand_block in the system prompt).
    `music_style` is the brand's genre line; `seconds` only when the editor asked for a length;
    `source` a script or voice-over to adapt into lyrics; `sounds_like` a song or artist the
    editor wants it to feel like (the style line describes it, never names it); `reference` a
    winning song ad's study (its transcript, tempo and sections) whose shape to follow."""
    parts = [f"<brief>\n{brief}\n</brief>", "<cast>\n" + "\n".join(cast) + "\n</cast>"]
    if music_style:
        parts.append(f"<music_style>{music_style}</music_style>")
    if sounds_like:
        parts.append(f"<sounds_like>{sounds_like}</sounds_like>")
    if reference.strip():
        parts.append(f"<reference>\n{reference.strip()}\n</reference>")
    if source.strip():
        parts.append(f"<source>\n{number_lines(source.strip())}\n</source>")
    if seconds:
        words = round(seconds * sum(SUNG_RATE) / 2)
        parts.append(f"<length>{seconds} s (about {words} sung words)</length>")
    if note:
        parts.append(f"<note>{note}</note>")
    return "\n".join(parts)


def song_study_block(study: dict) -> str:
    """A song-ad study (flows S3a), for song_directions_input(reference=...): its length,
    tempo and sections, each with its lines (someone else's song: a guide to the shape, never
    words to reuse; check.copied_lines holds that). `study` is {seconds, bpm, sections:
    [{name, start, end, lines}], words}; words are left out."""
    from app.prompts.check import _clock  # check imports this module: import here

    head = f"A song ad that works: {_clock(study['seconds'])} long"
    if study.get("bpm"):
        head += f", about {round(study['bpm'])} BPM"
    out = [head + ".", "Sections (follow their order, their lengths and their pace):"]
    for x in study.get("sections", []):
        lines = x.get("lines") or []
        lines = lines if isinstance(lines, list) else []
        words = sum(len(str(t).split()) for t in lines)
        out.append(f"- {x['start']:.0f}–{x['end']:.0f} s {x['name']}: {len(lines)} lines, "
                   f"{words} words")  # fmt: skip
        out += [f"  | {t}" for t in lines]
    out.append("Its lines are someone else's song: never reuse one, word for word or nearly.")
    return "\n".join(out)


def song_block(song: dict) -> str:
    """The preferred take, measured, for the song_breakdown step: Next-Server's song timing
    {seconds, bpm, beats, sections [{name, start, end, cuts}], lines [{section, text, start,
    end, heard}]} (words and peaks are for the screens, left out). Sections start on bar lines;
    `cuts` are bar lines inside one that fall outside any sung word, the best shot edges. A
    line heard 0 times has guessed times."""
    lines = [f'<song seconds="{song["seconds"]:.2f}" bpm="{song.get("bpm") or "?"}">', "Sections:"]
    for x in song.get("sections", []):
        cuts = " ".join(f"{c:.2f}" for c in x.get("cuts", []))
        lines.append(
            f"- {x['start']:.2f}–{x['end']:.2f} {x['name']}" + (f" (cuts: {cuts})" * bool(cuts))
        )
    lines.append("Beats: " + " ".join(f"{b:.2f}" for b in song.get("beats", [])))
    lines.append("Sung lines:")
    for n, x in enumerate(song.get("lines", []), 1):
        guessed = " (times guessed)" if x.get("heard", 1) == 0 else ""
        lines.append(f"{n}| {x['start']:.2f}–{x['end']:.2f} {x['text']}{guessed}")
    return "\n".join([*lines, "</song>"])


SUNO_PACE = (
    ", vocals start immediately, no instrumental intro, no instrumental breaks, continuous "
    "singing, tight ending"
)


def song_request(lyrics: str, style_line: str) -> dict:
    """What the music provider (Suno) is sent for a picked direction: the lyrics word for word
    with our [Lip-sync] marks taken out (they're for the breakdown, never sung), opened and
    closed so the vocals start at once and end tight; the style line plus the pacing, outside
    its 25 words; and the styles to avoid (Starpop's measured Suno settings)."""
    from app.prompts.check import LIP_SYNC

    sung = "\n".join(LIP_SYNC.sub("", x).rstrip() for x in lyrics.strip().splitlines())
    return {
        "lyrics": f"[Intro: vocals start immediately]\n{sung}\n[End]",
        "style": style_line.strip().rstrip(".") + SUNO_PACE,
        "exclude_styles": "instrumental intro, instrumental break, long outro, spoken word",
    }


HEADING = ("SCENE", "INT.", "EXT.")


def plan_lines(script: str) -> list[int]:
    """The script lines a scene plan covers, each once and in order (flows P1): every line
    with words that isn't a scene heading."""
    lines = enumerate(script.splitlines(), 1)
    return [n for n, x in lines if x.strip() and not x.strip().startswith(HEADING)]


def plan_input(
    brief: str,
    cast: list[str],
    script: str,
    fmt: str,
    video_model: str,
    places: list[str] = (),
    reference: str = "",
    study: dict | None = None,
    note: str = "",
) -> str:
    """The user message for the plan step. `cast` and `places` are one 'id name: description'
    line each; `video_model` names the model and its max seconds per clip."""
    parts = [f"<brief>\n{brief}\n</brief>", "<cast>\n" + "\n".join(cast) + "\n</cast>"]
    if places:
        parts.append("<places>\n" + "\n".join(places) + "\n</places>")
    parts += [f"<video_model>{video_model}</video_model>", f"<format>{fmt}</format>"]
    parts.append(f"<script>\n{number_lines(script)}\n</script>")
    if reference.strip():
        parts.append(f"<reference>\n{reference.strip()}\n</reference>")
    if study:
        parts.append(f"<study>\n{json.dumps(study, indent=1)}\n</study>")
    if note.strip():
        parts.append(f"<note>{note.strip()}</note>")
    return "\n".join(parts)


# In the breakdown's user message, never its system prompt: the breakdown prompts stay as they
# were for a video without a plan, and their cache with them (QA on #892).
PLAN_RULE = (
    "**The plan.** The <plan> below is the editor's approved plan: it is the story, and the "
    "breakdown films it. Make its scenes, in order: each breakdown scene is one plan scene, with "
    "its place and time as the heading (split a long one into two at a natural turn, never join "
    "two). Its shots stage the plan's actions for those lines, made vivid and exact, and keep its "
    "cast: nobody added, nobody dropped. A ★ line's shot shows that product or screen (list it in "
    "`screen_ids`), the label or logo to camera. Everything in the step's rules still applies to "
    "how you shoot it."
)


def plan_block(plan: schemas.ScenePlan, script: str) -> str:
    """A plan as later steps read it: the structure and cast, then each scene's place, who's
    in it, and each line's words with its action and ★ (the plan_scene step, the breakdown)."""
    words = dict(enumerate(script.splitlines(), 1))
    shape = f"{' → '.join(plan.structure.parts)} ({plan.structure.name})"
    out = [f"Structure: {shape}", f"Cast: {', '.join(plan.cast)}"]
    for sc in plan.scenes:
        out.append(f"\nScene {sc.id} ({sc.part}): {sc.place} · {', '.join(sc.cast)}")
        for x in sc.lines:
            star = f" ★ {x.product}" if x.product else ""
            out.append(f"{x.line}| {words.get(x.line, '').strip()}\n   → {x.action}{star}")
    return f"{PLAN_RULE}\n<plan>\n" + "\n".join(out) + "\n</plan>"


def plan_scene_input(
    plan_message: str, plan: schemas.ScenePlan, script: str, scene: int, note: str
) -> str:
    """The user message for "Change this scene…": the plan's own input, the plan, the scene
    and the note."""
    ask = f"<scene>{scene}</scene>\n<note>{note.strip()}</note>"
    return f"{plan_message}\n{plan_block(plan, script)}\n{ask}"


def plan_from_breakdown(bd: schemas.Breakdown) -> schemas.ScenePlan:
    """The plan read from a breakdown made before plans existed (flows 1b), in code and free:
    one scene per breakdown scene, its lines and actions as written."""
    scenes, cast = [], []
    for sc in bd.scenes:
        lines, seen = [], set()
        for shot in sc.shots:
            ids = [x for x in shot.screen_ids if x.startswith(("product:", "screen:"))]
            for n in shot.script_lines:
                if n not in seen:
                    seen.add(n)
                    lines.append(schemas.PlanLine(line=n, action=shot.action,
                                                  product=ids[0] if ids else None))  # fmt: skip
        who = list(dict.fromkeys(c for shot in sc.shots for c in shot.character_ids))
        cast += [c for c in who if c not in cast]
        scenes.append(schemas.PlanScene(id=sc.id, part="", place=sc.heading, cast=who,
                                        lines=sorted(lines, key=lambda x: x.line)))  # fmt: skip
    shape = schemas.Structure(name="From the breakdown", parts=[], based_on="pattern")
    return schemas.ScenePlan(structure=shape, cast=cast, scenes=scenes)


def narration_music_input(script: str, seconds: float, note: str = "") -> str:
    """The user message for the narration_music step."""
    out = f"<script>\n{script.strip()}\n</script>\n<seconds>{round(seconds)}</seconds>"
    return out + (f"\n<note>{note.strip()}</note>" if note.strip() else "")


def music_prompt(result: schemas.NarrationMusic) -> str:
    """What the music model is sent: the Director's prompt, said to be an instrumental with no
    voice in it (flows N1). The length goes as the model's own duration setting."""
    return (
        result.prompt.strip().rstrip(".")
        + ". Instrumental only: no vocals, no choir, no spoken word."
    )


def spoken_words(script: str) -> int:
    """Words that are heard: `NAME: words` lines in a dialogue script; in pure voiceover prose,
    every line that isn't a heading, a ★ brand line or a [tag] line."""
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    said = [m.group(1) for line in lines if (m := re.match(r"^[A-Z][A-Z .'()-]*:\s*(.*)$", line))]
    if not said:
        said = [x for x in lines if not x.startswith(("SCENE", "INT.", "EXT.", "★", "["))]
    return len(" ".join(said).split())


def variations_input(
    script: str,
    cast: list[str],
    count: int,
    reference: str = "",
    keep_apart: str = "",
    note: str = "",
) -> str:
    """The user message for the variations step (with brand_block in the system prompt).
    `cast` is the locked characters as 'char:1 Nate'; `reference` is reference_block(...)."""
    words = spoken_words(script)
    parts = [
        f"<script>\n{number_lines(script)}\n</script>",
        "<cast>\n" + "\n".join(cast) + "\n</cast>",
        f"<length>{words} spoken words (about {round(words / 4.8)} s of talk); "
        f"{len(script.split())} words in all</length>",
    ]
    if reference:
        parts.append(reference)
    parts.append(f"<count>{count}</count>")
    if keep_apart:
        parts.append(f"<keep_apart>\n{keep_apart}\n</keep_apart>")
    if note:
        parts.append(f"<note>{note}</note>")
    return "\n".join(parts)


def cast_slots_input(
    versions: dict[int, str], reference: str = "", cast: list[str] = (), brief: str = ""
) -> str:
    """The user message for the cast_slots step: every approved version, numbered, by slot
    (0 = the original); the locked cast ('char:1 Bruno, the pitbull (narrator)') and the
    script's title and description, where names and looks the words don't say live; and
    optionally reference_block(...) for helpers from the reel."""
    parts = []
    if brief:
        parts.append(f"<brief>{brief}</brief>")
    if cast:
        parts.append("<cast>\n" + "\n".join(cast) + "\n</cast>")
    parts += [
        f'<version slot="{slot}">\n{number_lines(text)}\n</version>'
        for slot, text in sorted(versions.items())
    ]
    if reference:
        parts.append(reference)
    return "\n".join(parts)


def look_fit_input(description: str, role: str = "", role_text: str | None = None) -> str:
    """The user message for the look_fit check; the sheet image goes before it. `role` is
    the cast slot's role ("Omar, the boyfriend"); its name is left out of <role>. With
    `role_text` (the slot's description) the role's own words are read against the sheet."""
    part = role.split(",", 1)[-1].strip()
    lines = [f"<character>{description.strip()}</character>"]
    if part:
        lines.append(f"<role>{part}</role>")
    if role_text is not None:
        lines.append(f'<role_text name="{escape(role, quote=True)}">{escape(role_text.strip())}'
                     "</role_text>")  # fmt: skip
    return "\n".join(lines)


def item_check_input(
    shot: str,
    sheets: list[tuple[str, str]],
    product: tuple[str, str] | None = None,
    frames: int = 0,
) -> str:
    """The user message for item_check; the images go before it, in this order: the item (a
    still, or a take's `frames` in order), each sheet in `sheets` ((id, "Mia: ...")), then the
    product's image when the shot shows it ((id, "Iron Paws peanut butter bag")).
    `shot` is what the item should show (its action and who's in it)."""
    seen = (
        f"Images 1–{frames} are frames of one take, in order"
        if frames > 1
        else "Image 1 is the still"
    )
    n, refs = max(frames, 1), []
    for ref_id, what in sheets:
        n += 1
        refs.append(f'<sheet image="{n}" id="{ref_id}">{what.strip()}</sheet>')
    if product:
        refs.append(f'<product image="{n + 1}" id="{product[0]}">{product[1].strip()}</product>')
    return (f"<item>{seen}.</item>\n<shot>{shot.strip()}</shot>\n"
            "<references>\n" + "\n".join(refs) + "\n</references>")  # fmt: skip


def look_fit_redo(description: str, fit: "schemas.LookFit") -> str:
    """The change note for the one automatic redo of a sheet that doesn't fit its role."""
    return f"The character must read clearly as: {description.strip()}. {fit.problem.strip()}"
