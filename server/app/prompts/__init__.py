"""Director-owned prompts for the script-guided flow (issue #24).

A Claude call's system prompt is two cached parts: `system(step)` (the shared rules, the step's
prompt and its worked example) and `brand_block(...)` for the brand. The step's prompt file
lists the tags the user message must carry; `number_lines` formats a script for them.
Each step's output schema is `SCHEMAS[step]`."""

import json
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


def brand_block(brand: dict, screens: list[dict]) -> str:
    """`brand`: name, tone_notes, never_say, legal_line. `screens`: id, name, tags,
    default_for (the moments a screen is required at)."""
    lines = [f"<brand>\nBrand: {brand['name']}"]
    if brand.get("tone_notes"):
        lines.append(f"Tone: {brand['tone_notes']}")
    if brand.get("never_say"):
        lines.append("Never say: " + "; ".join(brand["never_say"]))
    if brand.get("legal_line"):
        lines.append(f"Legal line (added in post, don't write it): {brand['legal_line']}")
    required = [s for s in screens if s.get("default_for")]
    if required:
        moments = sorted({m for s in required for m in s["default_for"]})
        lines.append(
            "Required screens. Every shot at one of these moments shows the matching screen, "
            "attached as a reference image and shown exactly:"
        )
        lines += [_screen(s) + f" — required at: {', '.join(s['default_for'])}" for s in required]
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
    lines += [
        f"- {b['start']:.1f}–{b['end']:.1f} s {b['summary']} ({b['emotion']})" for b in ref["beats"]
    ]
    lines.append("Shots (time, framing, camera, action, emotion, line):")
    for s in ref["shots"]:
        said = f' | {s["speaker"]}: "{s["line"]}"' if s.get("line") else ""
        lines.append(
            f"{s['n']}. {s['start']:.2f}–{s['end']:.2f} {s['framing']}; {s['camera']} | "
            f"{s['action']} | {s['emotion']}{said}"
        )
    if replace:
        lines.append(f"Replace: {replace}")
    lines.append("</reference>")
    return "\n".join(lines)
