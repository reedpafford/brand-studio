"""Stand-ins for Replicate and Claude in local runs (BS_FAKE_PROVIDERS=true). Nothing is sent
anywhere and nothing is billed: images are a plain grey picture, videos a few grey seconds,
and each Claude step gets a simple answer in the right shape (made from the script and
breakdown in the request), so every page can be clicked through end to end."""

import html
import io
import itertools
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from app.prompts import SCHEMAS
from app.prompts.check import DIALOGUE
from app.providers import Result

SIZES = {"9:16": (360, 640), "16:9": (640, 360), "1:1": (512, 512), "4:5": (400, 500)}


def _tag(prompt: str, name: str) -> str:
    found = re.search(rf"<{name}>\n?(.*?)\n?</{name}>", prompt, re.S)
    return html.unescape(found.group(1)) if found else ""


def png(aspect: str) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", SIZES.get(aspect, (512, 512)), (128, 128, 128)).save(out, "PNG")
    return out.getvalue()


def mp4(aspect: str, seconds: int) -> bytes:
    w, h = SIZES.get(aspect, (512, 512))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fake.mp4"
        grey = ["-f", "lavfi", "-i", f"color=c=gray:s={w}x{h}:d={seconds}"]
        command = ["ffmpeg", "-v", "error", *grey, "-pix_fmt", "yuv420p", str(path)]
        subprocess.run(command, check=True, timeout=60)  # noqa: S603 - fixed arguments
        return path.read_bytes()


def _spoken(text: str) -> dict:
    if not DIALOGUE.match(text):
        return {"speaker": None, "line": None}
    speaker, line = text.split(":", 1)
    return {"speaker": speaker.title(), "line": line.strip()}


def _clip(clip: dict, shots: dict, framed: bool) -> dict:
    """A clip prompt in the house shape (check._shape): audio line first and last, Summary,
    whole-second shots from 0, Keep; each spoken line quoted once, word for word."""
    seconds, ids = clip["seconds"], clip["shot_ids"]
    ends = [round(seconds * (i + 1) / len(ids)) for i in range(len(ids))]
    groups = [ids] if len(set(ends)) < len(ends) or ends[0] == 0 else [[i] for i in ids]
    ends = ends if len(groups) > 1 else [seconds]
    audio = "Audio: only the spoken lines and room sound. No subtitles."
    lines = [audio, *(["[Image1] is the first frame."] if framed else []), "Summary: Test clip."]
    for k, group in enumerate(groups):
        said = [f'{shots[i]["speaker"] or "Someone"} says "{shots[i]["line"]}"' for i in group
                if shots[i].get("line")]  # fmt: skip
        what = " ".join([*(shots[i]["action"] for i in group), *(said or ["No one speaks."])])
        lines.append(f"Shot {k + 1} | {ends[k - 1] if k else 0}–{ends[k]} s. {what}")
    cast = [c for i in ids for c in shots[i]["character_ids"]]
    screens = [s for i in ids for s in shots[i]["screen_ids"]]
    images = [*([f"frame:{clip['id']}"] if framed else []), *dict.fromkeys(cast + screens)]
    shown = " ".join(f"[Image{images.index(s) + 1}]" for s in dict.fromkeys(screens))
    lines += [f"Keep: plain grey test look. {shown}".strip(), audio]
    return {
        "clip_id": clip["id"],
        "seconds": seconds,
        "references": [{"kind": "image", "id": i, "role": i} for i in images],
        "prompt": "\n".join(lines),
    }


class FakeMedia:
    """Replicate's place: every image or video job succeeds on its first check."""

    name, paid = "replicate", False

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._ids = itertools.count(1)

    def submit(self, kind: str, input: dict) -> str:
        ref = f"local-{next(self._ids)}"
        self._jobs[ref] = {"kind": kind, **input.get("input", {})}
        return ref

    def poll(self, ref: str) -> Result:
        # No usage: the job keeps its estimated credits and no fake dollars are recorded.
        return Result("succeeded", output={"url": f"fake://{ref}"}, files=[f"fake://{ref}"])

    def fetch(self, url: str) -> tuple[bytes, str]:
        job = self._jobs[url.removeprefix("fake://")]
        aspect = job.get("aspect_ratio", "9:16")
        if job["kind"] == "video":
            return mp4(aspect, int(job.get("duration", 5))), "video/mp4"
        return png(aspect), "image/png"


class FakeWriter:
    """Claude's place: answers at once with a simple, valid result for the step."""

    name, paid, sync = "claude", False, True

    def run(self, kind: str, input: dict) -> Result:
        step, prompt = input["step"], input["prompt"]
        self._system = "\n".join(input.get("system") or [])  # the brand block lists screens
        answer = getattr(self, f"_{step}")(prompt)
        return Result("succeeded", output=SCHEMAS[step].model_validate(answer).model_dump())

    def _enhance(self, prompt):
        return {"suggestions": [], "notes": []}

    def _script_draft(self, prompt):
        return {
            "drafts": [
                {"hook_idea": hook, "script": f"[{hook}]\nHERO: This is a practice script."}
                for hook in ("Local test hook A", "Local test hook B")
            ]
        }

    def _breakdown(self, prompt):
        limits = re.search(r"(\d+)–(\d+) s per clip", prompt)
        low, high = map(int, limits.groups()) if limits else (4, 15)
        lines = [ln.split("| ", 1) for ln in _tag(prompt, "script").splitlines() if "| " in ln]
        screen = next(iter(re.findall(r"- (screen:\d+)", self._system)), None)
        cast = re.findall(r"^(char:\d+) \|", _tag(prompt, "cast"), re.M)
        shots = [
            {
                "id": f"1.{i}",
                "script_lines": [int(n)],
                **_spoken(text),
                "action": text.strip(),
                "reaction": None,
                "camera": "Medium shot, static",
                "seconds": max(1.5, round(len(text.split()) / 4.8, 1)),  # spoken pace
                # A speaker is the first cast member; a ★ line shows the brand's first screen.
                "character_ids": cast[:1] if DIALOGUE.match(text) else [],
                "place_id": None,
                "moment": None,
                "screen_ids": [screen] if "★" in text and screen else [],
            }  # fmt: skip
            for i, (n, text) in enumerate((x for x in lines if x[1].strip()), 1)
        ]
        groups: list[list[dict]] = []
        for shot in shots:  # fill each clip up to the model's longest
            if not groups or sum(x["seconds"] for x in groups[-1]) + shot["seconds"] > high:
                groups.append([])
            groups[-1].append(shot)
        clips = [
            {
                "id": f"c{k}",
                "shot_ids": [s["id"] for s in group],
                "seconds": min(high, max(low, math.ceil(sum(s["seconds"] for s in group)))),
                "seam": "end" if k == len(groups) else "model length limit",
            }
            for k, group in enumerate(groups, 1)
        ]
        scene = {"id": 1, "heading": "INT. TEST — DAY", "look": "Plain grey.", "shots": shots}
        return {"hook": "Local test breakdown.", "scenes": [scene], "clips": clips}

    def _storyboard(self, prompt):
        bd = json.loads(_tag(prompt, "breakdown") or "{}")
        shots = {s["id"]: s for scene in bd.get("scenes", []) for s in scene["shots"]}
        frames = [
            {
                "clip_id": c["id"],
                "shot_id": c["shot_ids"][0],
                "prompt": "A plain test still.",
                "reference_ids": [
                    *shots[c["shot_ids"][0]]["character_ids"],
                    *shots[c["shot_ids"][0]]["screen_ids"],
                ],
            }  # fmt: skip
            for c in bd.get("clips", [])
        ]
        return {"frames": frames}

    def _clip_prompts(self, prompt):
        bd = json.loads(_tag(prompt, "breakdown") or "{}")
        shots = {s["id"]: s for scene in bd.get("scenes", []) for s in scene["shots"]}
        assets = {line.split(" | ")[0] for line in _tag(prompt, "assets").splitlines()}
        return {"clips": [_clip(c, shots, f"frame:{c['id']}" in assets) for c in bd["clips"]]}

    def _improve(self, prompt):
        refs, idea = _tag(prompt, "references"), _tag(prompt, "idea") or prompt.strip()
        return {"prompt": f"{refs}\n{idea}" if refs else idea}

    def submit(self, kind: str, input: dict) -> str:  # pragma: no cover - sync provider
        raise NotImplementedError

    def poll(self, ref: str) -> Result:  # pragma: no cover - sync provider
        raise NotImplementedError

    def fetch(self, url: str) -> tuple[bytes, str]:  # pragma: no cover - no files
        raise NotImplementedError
