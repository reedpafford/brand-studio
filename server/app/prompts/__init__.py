"""Director-owned prompts for the script-guided flow (issue #24).

A Claude call's system prompt is two cached parts: `system(step)` (the shared rules, the step's
prompt and its worked example) and `brand_block(...)` for the brand. The step's prompt file
lists the tags the user message must carry; `number_lines` formats a script for them.
Each step's output schema is `SCHEMAS[step]`."""

import json
import re
from functools import cache
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
    "variations": schemas.Variations,
    "cast_slots": schemas.CastSlots,
}


@cache
def system(step: str) -> str:
    parts = [(HERE / "rules.md").read_text(), (HERE / f"{step}.md").read_text()]
    example = HERE / "examples" / f"{step}.json"
    if example.exists():
        ex = json.loads(example.read_text())
        parts.append(
            f"## Worked example ({ex['source']})\n{ex['note']}\n\n"
            f"<example_input>\n{ex['input']}\n</example_input>\n\n"
            f"<example_output>\n{json.dumps(ex['output'], indent=1)}\n</example_output>"
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
    default_for (the moments a screen is required at). `product`: the one product this project
    picked (id, name), e.g. the Iron Paws peanut butter bag."""
    lines = [f"<brand>\nBrand: {brand['name']}"]
    if brand.get("tone_notes"):
        lines.append(f"Tone: {brand['tone_notes']}")
    if brand.get("never_say"):
        lines.append("Never say: " + "; ".join(brand["never_say"]))
    if brand.get("end_line"):
        lines.append(f"End line (every video ends on it, word for word): {brand['end_line']}")
    if brand.get("legal_line"):
        lines.append(f"Legal line (added in post, don't write it): {brand['legal_line']}")
    needed = [s for s in screens if s.get("default_for")]
    if needed:
        lines.append(
            "Required screens. Every shot at one of these moments shows the matching screen, "
            "attached as a reference image: logo, colours and layout exact, numbers free:"
        )
        lines += [_screen(s) + f" — required at: {', '.join(s['default_for'])}" for s in needed]
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
    return f'- screen:{s["id"]} "{s["name"]}" ({", ".join(s.get("tags", []))})'


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
    kind: str, description: str = "", from_photo: bool = False, change: str = ""
) -> str:
    """The Nano Banana prompt for a library item's reference picture. kind "character": a front
    / side / back turnaround sheet, from a description or (from_photo) an uploaded photo of a
    real person as image 1; "place": an empty establishing still. `change` is the editor's note
    when redoing a sheet (the last sheet goes in as the final image). `description` is the
    item's notes; names stay out so none is drawn."""
    sections = (HERE / "sheet.md").read_text().split("\n## ")[1:]
    parts = {name: body.strip() for name, body in (s.split("\n", 1) for s in sections)}
    out = [parts[kind]]
    if kind == "character" and from_photo:
        out.append(parts["photo"])
    if description.strip():
        out.append(f"The {kind}: {description.strip()}")
    if change.strip():
        out.append(parts["redo"].format(change=change.strip()))
    return " ".join(out)


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
