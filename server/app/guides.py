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
           "review_stills", "watch_cut", "director"}  # fmt: skip
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
        meta = {k: v for k, v in parent["meta"].items() if k not in ("name", "order")} | meta
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
        "blurb": meta["blurb"],
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


def guidance(sections: dict, only: tuple = ()) -> list[tuple[str, str]]:
    """A guide's sections for a model: everything but the tokens and data (`only`: those)."""
    return [(k, v) for k, v in sections.items()
            if k not in FIXED and v and (not only or k in only)]  # fmt: skip


def fill(text: str, style_id: str) -> str:
    """The step text with the style's look tokens ({{sheet_look}}…) filled in."""
    looks = style(style_id)["sections"]
    return TOKEN.sub(lambda m: looks[m.group(1)], text)


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
def brief(format_id: str, style_id: str, step: str) -> str:
    """What a writing step knows of the video's format and style: craft.md, then the format's
    guide, then the style's (with its lane; its `lanes` for the plan), then up to 3 studies."""
    chosen, form = style(style_id), format_(format_id)
    parts = [
        "## Producer craft (Reed's: the story, for every video)\nHow the team makes a short "
        "people watch to the end: the why, the hook, something happening, review and "
        "rewatch.\n\n" + (ROOT / "craft.md").read_text()
    ]
    if own := guidance(form["sections"]):
        parts.append(fill(_part(
            f"Format: {form['name']}",
            f"This video is a {form['name']} video in the {chosen['name']} style: how its script "
            "reads, its structure, pacing, beats and sound. On anything visual the style below "
            "wins. Where this names a studio or a render style that isn't this video's look (a "
            "song guide's \"Pixar\" on a Claymation song), follow this video's look, and never "
            "write a studio's name.", own), style_id))  # fmt: skip
    own = guidance(chosen["sections"])
    if step == "plan" and chosen["sections"].get("lanes"):
        own.append(("lanes", chosen["sections"]["lanes"]))  # the plan picks this video's lane
    if own:
        parts.append(_part(
            f"Style: {chosen['name']}",
            f"This video is in the {chosen['name']} style: how it looks, and how its camera, "
            "shots, motion and transitions work. Where this section and anything above (the "
            "worked example included) differ on anything visual, this section wins; where the "
            "steps above are more specific about the site's own fields and limits, they win.",
            own))  # fmt: skip
    if found := studies(format_id, style_id):
        parts.append(_part("Studied examples", "Ads that worked, studied: their shape, never "
                           "their words.", found))  # fmt: skip
    return "\n\n".join(parts)
