"""The guides (server/app/guides/, its README for Reed): every format and style is one guide.md,
and this module is the only reader of them. A guide is `key: value` lines, a blank line, then
`## name` sections: the look tokens and the data below are read by the code; every other
section is guidance for the writing steps, sent as Reed wrote it."""

import json
import re
from functools import cache
from pathlib import Path

ROOT = Path(__file__).parent / "guides"
TOKENS = ("sheet_look", "place_look", "still_look", "clip_style", "fit_look")
DATA = {"banned", "fixes", "sample"}  # never sent to a model as guidance (flows ST2, ST3)
FIXED = {*TOKENS, *DATA, "lanes"}
# Every writing step gets the whole brief (Reed, 2 Nov: one director, briefed by the guides).
BRIEFED = {"treatment", "plan", "plan_scene", "breakdown", "song_breakdown", "narrated_breakdown",
           "storyboard", "clip_prompts", "song_clip_prompts", "narrated_clip_prompts",
           "review_stills", "watch_cut", "take_watch", "director"}  # fmt: skip
# The steps after the plan: the story's words and shape are settled, so a guide's script
# sections (`Script`, and any named "Script: …") would only add words (speed, Reed 8 Nov).
AFTER_PLAN = BRIEFED - {"treatment", "plan", "plan_scene", "director"}
KIND = {"": "dialogue", "story": "dialogue"}  # a script's kind names its format (song, narrated)
TOKEN = re.compile(r"\{\{(\w+)\}\}")


def _read(path: Path) -> tuple[dict, dict]:
    """(front matter, sections). A `## ` line inside a ``` block is the block's, not a heading."""
    meta, sections, name, fence, top = {}, {}, None, False, True
    for line in path.read_text().splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            name = line[3:].strip()
            if name in sections:
                raise ValueError(f"{path}: two sections named {name}")
            sections[name] = []
        elif name is not None:
            sections[name].append(line)
        elif top and line.strip():
            key, _, value = line.partition(": ")
            meta[key.strip()] = value.strip()
        else:
            top = False  # the front matter ends at its first blank line
    return meta, {k: "\n".join(v).strip() for k, v in sections.items()}


def _style(path: Path, parent: dict | None = None) -> dict:
    meta, sections = _read(path)
    if parent:  # a lane holds only what differs: the rest is its style's (never its lanes)
        meta = {
            k: v for k, v in parent["meta"].items() if k not in ("name", "order", "hidden")
        } | meta  # a hidden style, not its lanes
        sections = {k: v for k, v in parent["sections"].items() if k != "lanes"} | sections
    return {
        "id": path.stem if parent else path.parent.name,
        "name": meta["name"],
        "kind": "lane" if parent else "look",  # a lane: one way of making a look (Reed, 1 Nov)
        "parent": parent["id"] if parent else "",
        "order": float(meta["order"]),
        "on": meta.get("on") == "yes",  # only the starting switch: the server keeps Reed's own
        "own_sample": meta.get("own_sample") == "yes",  # ST3: never the brand's hero
        "hidden": meta.get("hidden") == "yes",  # a lane kept but off the picker (Reed, 3 Nov)
        "image_model": meta.get("image_model", "auto"),
        "video_model": meta.get("video_model", ""),  # its default video model (a catalogue id)
        # its characters' lips follow their spoken lines (model_map.lip_synced); a guide opts out
        # with `lip_sync: no` (a style whose speakers don't lip-sync, e.g. flap mouths)
        "lip_sync": meta.get("lip_sync", "yes") != "no",
        "blurb": meta["blurb"],
        "card": meta.get("card", ""),  # New video's card: a short line, then its B-roll look
        "broll": meta.get("broll", ""),
        # the formats it's made in, when only some ("formats: dialogue"; none: any), and why
        "formats": [f.strip() for f in meta.get("formats", "").split(",") if f.strip()],
        "formats_why": meta.get("formats_why", ""),
        "sections": sections,
        "meta": meta,
    }


@cache
def styles() -> list[dict]:
    """Every style and lane, in Reed's order (a lane sits just after its style)."""
    out = []
    for path in (ROOT / "styles").glob("*/guide.md"):
        look = _style(path)
        out += [look, *(_style(x, look) for x in path.parent.glob("lanes/*.md"))]
    return sorted(out, key=lambda s: s["order"])


@cache
def formats() -> list[dict]:
    """Every format, in Reed's order: {id, name, order, on, engine, host, blurb, sections}.
    `host`: a host says the narration on camera over the B-roll (app/host.py, Presenter)."""
    out = []
    for path in (ROOT / "formats").glob("*/guide.md"):
        meta, sections = _read(path)
        out.append({"id": path.parent.name, "name": meta["name"], "order": float(meta["order"]),
                    "on": meta.get("on") == "yes", "engine": meta["engine"],
                    "host": meta.get("host") == "yes", "blurb": meta["blurb"],
                    "card": meta.get("card", ""),
                    "sections": sections})  # fmt: skip
    return sorted(out, key=lambda f: f["order"])


def style(style_id: str) -> dict:
    found = [s for s in styles() if s["id"] == style_id]
    if not found:
        raise ValueError(f"unknown style: {style_id}")
    return found[0]


def format_(format_id: str) -> dict:
    found = [f for f in formats() if f["id"] == format_id]
    if not found:
        raise ValueError(f"unknown format: {format_id}")
    return found[0]


def video_format(kind: str, style_id: str, picked: str = "") -> str:
    """The format of a video: its script's own pick (a format id), else from the script's kind
    (story, song, narrated), where a style that is also a format (Zack D) brings its own,
    except to a song."""
    ids = {f["id"] for f in formats()}
    if picked in ids:
        return picked
    base = style(style_id)["parent"] or style_id
    if kind in ("", "story", "narrated") and base in ids:
        return base
    return KIND.get(kind, kind)


def guidance(sections: dict, only: tuple = (), step: str = "") -> list[tuple[str, str]]:
    """A guide's sections for a model: everything but the tokens and data (`only`: those);
    for a `step` after the plan, none of its script sections."""
    late = step in AFTER_PLAN
    return [(k, v) for k, v in sections.items() if k not in FIXED and v
            and (not only or k in only) and not (late and _script(k))]  # fmt: skip


def _script(name: str) -> bool:
    """A section on writing the script: `Script`, or one named "Script: …"."""
    return name == "Script" or name.startswith("Script:")


def fill(text: str, style_id: str) -> str:
    """The step text with the style's look tokens ({{sheet_look}}…) filled in."""
    looks = style(style_id)["sections"]
    return TOKEN.sub(lambda m: looks[m.group(1)], text)


PACE = re.compile(r"(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?) words a second")
PAUSE = re.compile(r"pauses of about (\d+(?:\.\d+)?)")  # Movie: "pauses of about 0.6–0.7 s"


def _measured(pattern: re.Pattern, style_id: str, format_id: str) -> re.Match | None:
    """The first match in the style's guide, else in its format's."""
    for sections in (style(style_id)["sections"], format_(format_id)["sections"]):
        for _, text in guidance(sections):
            if found := pattern.search(text):
                return found
    return None


def pace(style_id: str, format_id: str) -> tuple[float, float] | None:
    """The words a second a narrator keeps, as the guide measured it ("3.3–3.5 words a second
    while talking"; Movie's "2–3 words a second"): the style's own, else its format's; None
    when neither says."""
    found = _measured(PACE, style_id, format_id)
    return (float(found[1]), float(found[2])) if found else None


def pause(style_id: str, format_id: str) -> float | None:
    """The pause after a sentence in dialogue, the shorter end of what the guide measured
    ("pauses of about 0.6–0.7 s"): the style's own, else its format's; None when neither says."""
    found = _measured(PAUSE, style_id, format_id)
    return float(found[1]) if found else None


def tokens(style_id: str) -> dict[str, str]:
    return {k: v for k, v in style(style_id)["sections"].items() if k in TOKENS}


def banned(style_id: str) -> list[tuple[str, str]]:
    """The style's banned words and their replacements ("" deletes): its `## banned` lines."""
    lines = style(style_id)["sections"].get("banned", "").splitlines()
    return [(a.strip(), b.strip()) for a, _, b in (x.partition("→") for x in lines if "→" in x)]


def fixes(style_id: str) -> dict[str, str]:
    """The style's fix for each failure id (refused, face, outfit, product): `## fixes`."""
    lines = style(style_id)["sections"].get("fixes", "").splitlines()
    return {a.strip(): b.strip() for a, _, b in (x.partition(":") for x in lines if ":" in x)}


def sample(style_id: str) -> str:
    """The person in the style's sample still (flows ST3), or "" when it has none."""
    return style(style_id)["sections"].get("sample", "").strip()


def example(format_id: str, step: str) -> dict | None:
    """The step's worked example in this format (formats/<id>/examples/<step>.json), if any:
    the fomo shorts' reach only the dialogue format."""
    path = ROOT / "formats" / format_id / "examples" / f"{step}.json"
    return json.loads(path.read_text()) if path.exists() else None


def studies(format_id: str, style_id: str) -> list[tuple[str, str]]:
    """Up to 3 studied examples (examples/<name>/study.md): the format's, then the style's."""
    base = style(style_id)["parent"] or style_id
    paths = [*sorted((ROOT / "formats" / format_id / "examples").glob("*/study.md")),
             *sorted((ROOT / "styles" / base / "examples").glob("*/study.md"))]  # fmt: skip
    return [(p.parent.name, p.read_text().strip()) for p in paths[:3]]


def _part(title: str, intro: str, sections: list[tuple[str, str]]) -> str:
    return f"## {title}\n{intro}\n\n" + "\n\n".join(f"### {k}\n{v}" for k, v in sections)


@cache
def brief(format_id: str, style_id: str, step: str, broll: str = "") -> str:
    """What a writing step knows of the video's format and style: craft.md, then the format's
    guide, then the style's (with its lane; its `lanes` for the plan), then up to 3 studies.
    `broll`: a hosted video's B-roll look (n31): the style stays the host's, voice's and cast's
    and the B-roll look's guide follows it for every B-roll shot, both as Reed wrote them."""
    chosen, form = style(style_id), format_(format_id)
    parts = [
        "## Producer craft (Reed's: the story, for every video)\nHow the team makes a short "
        "people watch to the end: the why, the hook, something happening, review and "
        "rewatch.\n\n" + (ROOT / "craft.md").read_text()
    ]
    if own := guidance(form["sections"], step=step):
        parts.append(fill(_part(
            f"Format: {form['name']}",
            f"This video is a {form['name']} video in the {chosen['name']} style: how its script "
            "reads, its structure, pacing, beats and sound. On anything visual the style below "
            "wins. Where this names a studio or a render style that isn't this video's look (a "
            "song guide's \"Pixar\" on a Claymation song), follow this video's look, and never "
            "write a studio's name.", own), style_id))  # fmt: skip
    own = guidance(chosen["sections"], step=step)
    if step == "plan" and chosen["sections"].get("lanes"):
        own.append(("lanes", chosen["sections"]["lanes"]))  # the plan picks this video's lane
    if own and not broll:
        parts.append(_part(
            f"Style: {chosen['name']}",
            f"This video is in the {chosen['name']} style: how it looks, and how its camera, "
            "shots, motion and transitions work. Where this section and anything above (the "
            "worked example included) differ on anything visual, this section wins; where the "
            "steps above are more specific about the site's own fields and limits, they win.",
            own))  # fmt: skip
    elif own:
        parts.append(_part(
            f"Style: {chosen['name']} (the host, the voice and the cast)",
            f"This video is in the {chosen['name']} style for its host, its voice and its cast: "
            "how they look, sound and move, and everything this style must keep. Its B-roll is "
            "drawn in another look, below. Where this section and anything above (the worked "
            "example included) differ on the host or the cast, this section wins.",
            own))  # fmt: skip
    if broll and (shots := guidance(style(broll)["sections"], step=step)):
        parts.append(_part(
            f"B-roll look: {style(broll)['name']}",
            f"Every B-roll shot of this video (every shot but the host) is drawn, lit and moves "
            f"in the {style(broll)['name']} look. On a B-roll shot, where this section and "
            "anything above differ on anything visual, this section wins; the host, the voice "
            f"and the cast keep {chosen['name']}.", shots))  # fmt: skip
    if found := studies(format_id, style_id):
        parts.append(_part("Studied examples", "Ads that worked, studied: their shape, never "
                           "their words.", found))  # fmt: skip
    return "\n\n".join(parts)
