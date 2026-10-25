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


def two_scenes(path: Path, *, sound: bool = True) -> Path:
    """A 6 s stand-in reel: 3 s of testsrc, then 3 s of smptebars (one cut at 3 s)."""
    scenes = ["-f", "lavfi", "-i", "testsrc=s=160x284:d=3:r=10"]
    scenes += ["-f", "lavfi", "-i", "smptebars=s=160x284:d=3:r=10"]
    audio = ["-f", "lavfi", "-i", "sine=d=6"] if sound else []
    joined = "[0:v][1:v]concat=n=2:v=1[v]"
    args = ["ffmpeg", "-v", "error", *scenes, *audio, "-filter_complex", joined, "-map", "[v]"]
    args += ["-map", "2:a", "-shortest"] if sound else []
    subprocess.run([*args, "-pix_fmt", "yuv420p", "-y", str(path)], check=True)  # noqa: S603
    return path


def transcript(path: Path) -> list[dict]:
    """Stand-in transcription (no model download): two lines, whatever the video says."""
    return [
        {"start": 0.5, "end": 2.0, "text": "Will you marry me?", "speaker": None},
        {"start": 3.5, "end": 5.0, "text": "No.", "speaker": None},
    ]


def refuse_link(url: str, folder: Path) -> Path:
    """Local runs never reach Instagram: a link always says to upload instead."""
    from app.reel import BLOCKED, Refused

    raise Refused("blocked", BLOCKED)


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
    spoken = any(shots[i].get("line") for i in ids)
    audio = ("Audio: only the spoken lines and room sound. No subtitles." if spoken else
             "Audio: no one speaks (no voices, narration or dialogue), only room sound. "
             "No subtitles.")  # fmt: skip
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


def watch(job: dict) -> dict:
    """Stand-in Gemini for a reel: one plain shot per cut it was given, the transcript's lines
    said by two roles in turn."""
    prompt = job["prompt"]
    cuts = re.findall(r"^(\d+)\. ([\d.]+)–([\d.]+)$", _tag(prompt, "cuts"), re.M)
    lines = re.findall(r"^\d+\| ", _tag(prompt, "transcript"), re.M)
    shot = dict(framing="medium", camera="static", on_screen="two people", action="they talk")
    return {
        "logline": "A proposal goes wrong, and he wins in the end",
        "style": "3D animated",
        "hook": {"seconds": 1.5, "mechanic": "A proposal answered with a no"},
        "beats": [{"start": 0, "end": float(cuts[-1][2]), "summary": "No, then a win",
                   "emotion": "shock"}],
        "montage": None,
        "shots": [
            {**shot, "n": int(n), "start": float(a), "end": float(b), "emotion": "calm",
             "live_action": False, "text_on_screen": ""}
            for n, a, b in cuts
        ],
        "speakers": [{"line": i + 1, "speaker": ("groom", "bride")[i % 2]}
                     for i in range(len(lines))],
        "why_it_works": ["An instant no"],
    }  # fmt: skip


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
        if self._jobs[ref]["kind"] == "watch-gemini":
            return Result("succeeded", output={"text": json.dumps(watch(self._jobs[ref]))})
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
        """A practice script; adapting a reel, it says the reel's lines word for word (each
        by its speaker), unless <new_lines> asks for fresh ones."""
        said = re.findall(r'\| ([^|:\n]+): "(.*)"$', _tag(prompt, "reference"), re.M)
        keep = said and not _tag(prompt, "new_lines")
        name = (re.split(r" \(| / ", who)[0].upper() for who, _ in said)  # "groom (likely)"
        lines = [f"{n}: {line}" for n, (_, line) in zip(name, said, strict=True)] if keep else []
        body = "\n".join(lines) or "HERO: This is a practice script."
        return {
            "drafts": [
                {"hook_idea": hook, "script": f"[{hook}]\n{body}"}
                for hook in ("Local test hook A", "Local test hook B")
            ]
        }

    def _variations(self, prompt):
        """The original with each spoken line's words turned around (the second variation
        also starts mid-line), keeping headings, action, ★ lines and the last line as-is."""
        lines = [ln.split("| ", 1)[-1] for ln in _tag(prompt, "script").splitlines()]
        spoken = [i for i, ln in enumerate(lines) if DIALOGUE.match(ln)]
        count = int(_tag(prompt, "count") or 1)
        first = 2 if _tag(prompt, "keep_apart") else 1  # a regenerate: unlike the one kept
        out = []
        for k in range(first, first + count):
            new = list(lines)
            for i in spoken[:-1]:
                name, words = lines[i].split(":", 1)
                turned = words.split()[::-1]
                turned = turned[k - 1 :] + turned[: k - 1]
                new[i] = f"{name}: {' '.join(turned)}"
            out.append({
                "title": f"Local variation {k}",
                "premise": "A practice variation with the lines turned around.",
                "script": "\n".join(new),
                "changes": ["The spoken lines are reworded."],
            })  # fmt: skip
        return {"variations": out}

    def _cast_slots(self, prompt):
        """The original's first two speakers, in every version."""
        slots = [int(n) for n in re.findall(r'<version slot="(\d+)">', prompt)]
        original = re.search(r'<version slot="0">\n(.*?)\n</version>', prompt, re.S)
        lines = [
            ln.split("| ", 1)[-1] for ln in (original.group(1) if original else "").splitlines()
        ]
        names = dict.fromkeys(
            ln.split(":")[0].split(" (")[0].title() for ln in lines if DIALOGUE.match(ln)
        )
        return {
            "slots": [
                {
                    "role": name,
                    "kind": "Main",
                    "description": "A practice look.",
                    "appears_in": slots,
                    "recurring": True,
                }
                for name in list(names)[:2]
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
                # Not the script's words: an action that reads like speech fails #135's check.
                "action": f"A plain test shot for script line {n}.",
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
