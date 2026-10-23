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
