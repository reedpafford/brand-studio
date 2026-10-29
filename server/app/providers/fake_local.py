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

from app.prompts import SCHEMAS, check
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


# The stand-in song (Producer: a fixed track with known timings): a click on every beat at
# 120 BPM from 0.25 s, 24 s long; its words are sung one a beat from the fifth beat on.
# A marker in the style line picks another outcome, so every state can be walked (Flow-QA):
# fake:fail, fake:refuse (unsafe words), fake:copyright (the style names an artist),
# fake:drop-line (the last line isn't sung), fake:repeat-line (it's sung twice) or
# fake:long (150 s; fake:long=800 for a song whose video goes over the cap) or
# fake:one-song (the reply holds only one of the two songs).
SONG = {"seconds": 24, "bpm": 120, "first_beat": 0.25, "first_word_beat": 4}
OUTCOMES = {
    "fake:fail": "Internal error while generating music",
    "fake:refuse": "Input flagged as sensitive content (E005)",
    "fake:copyright": "Prompt may reference copyrighted artist or song",
}
LINE_MARKERS = ("drop-line", "repeat-line")


def song(style: str = "") -> bytes:
    beat = 60 / SONG["bpm"]
    long = re.search(r"fake:long(?:=(\d+))?", style)
    seconds = int(long.group(1) or 150) if long else SONG["seconds"]
    t0 = SONG["first_beat"]
    click = f"sin(2*PI*880*t)*exp(-40*mod(t-{t0},{beat}))*gte(t,{t0})"
    marker = next((m for m in LINE_MARKERS if f"fake:{m}" in style), "")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "song.mp3"
        source = ["-f", "lavfi", "-i", f"aevalsrc='{click}':s=22050:d={seconds}"]
        tag = ["-metadata", f"comment=fake:{marker}"]  # read back by hear_song
        command = ["ffmpeg", "-v", "error", *source, *tag, "-c:a", "libmp3lame", "-b:a", "64k"]
        subprocess.run([*command, str(path)], check=True, timeout=120)  # noqa: S603
        return path.read_bytes()


def hear_song(path: Path, lyrics: str) -> list[dict]:
    """Stand-in Whisper for the stand-in song: every lyric word, one a beat, 0.3 s each (the
    last line left out, or sung twice, for those markers)."""
    beat = 60 / SONG["bpm"]
    sung_lines = [line.split() for line in check.sung_lines(lyrics)]
    head = path.read_bytes()[:256]  # the ID3 tag song() wrote
    if b"fake:drop-line" in head:
        sung_lines = sung_lines[:-1]
    elif b"fake:repeat-line" in head:
        sung_lines = [*sung_lines, sung_lines[-1]]
    sung = [w for line in sung_lines for w in line]
    start = SONG["first_beat"] + SONG["first_word_beat"] * beat
    times = (round(start + k * beat, 2) for k in range(len(sung)))
    return [
        {"word": w, "start": t, "end": round(t + 0.3, 2)} for w, t in zip(sung, times, strict=True)
    ]


# The stand-in narrator: each sentence a tone, 0.3 s a word, with 0.8 s of silence after it
# (so the pause trim has something to shorten). "fake:fail" in the words fails the voice
# call; "fake:clip-word" makes the trimmed narration lose its last word when heard again
# (so it's kept untrimmed: "Kept the pauses").
WORD, GAP = 0.3, 0.8


def narration(text: str) -> bytes:
    from app.narration import sentences

    parts, t = [], GAP
    for sentence in sentences(text):
        end = t + WORD * len(sentence.split())
        parts.append(f"between(t,{t:.2f},{end:.2f})")
        t = end + GAP
    tone = f"sin(2*PI*220*t)*({'+'.join(parts) or '0'})"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "voice.mp3"
        source = ["-f", "lavfi", "-i", f"aevalsrc='{tone}':s=22050:d={t:.2f}"]
        command = ["ffmpeg", "-v", "error", *source, "-c:a", "libmp3lame", "-b:a", "64k"]
        subprocess.run([*command, str(path)], check=True, timeout=120)  # noqa: S603
        return path.read_bytes()


def hear_voice(path: Path, text: str) -> list[dict]:
    """Stand-in Whisper for the stand-in narrator: each run of sound is a sentence, its words
    spread evenly over it."""
    from app import song_timing
    from app.narration import sentences

    samples, step = song_timing._samples(path), song_timing.RATE // 100
    loud = [max(map(abs, samples[i : i + step]), default=0) > 1000
            for i in range(0, len(samples), step)]  # fmt: skip
    runs, start = [], None
    for k, on in enumerate([*loud, False]):
        if on and start is None:
            start = k
        elif not on and start is not None:
            runs.append((start / 100, k / 100))
            start = None
    said = sentences(text)
    if len(runs) != len(said):  # not one run a sentence: share the words over the whole file
        runs, said = [(0.0, song_timing.length(path))], [" ".join(said)]
    heard = []
    for (a, b), sentence in zip(runs, said, strict=True):
        words = sentence.split()
        each = (b - a) / len(words)
        heard += [{"word": w, "start": round(a + n * each, 2), "end": round(a + (n + 1) * each, 2)}
                  for n, w in enumerate(words)]  # fmt: skip
    if "fake:clip-word" in text and path.name == "trimmed.mp3":
        heard = heard[:-1]
    return heard


# The stand-in song ad's words (no model download): verse, chorus, verse, chorus, so every
# section of a study shows. Its lines are spread over the video's first 90 %.
STUDY = [
    "Morning walk and he won't eat his bowl",
    "Scratching at his ears from dawn to dark",
    "That's my gut breaking down",
    "That's my gut breaking down",
    "Found a scoop that turned his whole day round",
    "Now he's running every lap around the park",
    "That's my gut breaking down",
    "That's my gut breaking down",
]


def hear_study(path: Path, watch=None) -> list[dict]:
    """Stand-in Whisper for a song-ad study: STUDY's lines, a short pause after each pair."""
    from app.song_timing import length

    step = length(path) * 0.9 / (len(STUDY) + len(STUDY) // 2)
    out, t = [], step / 2
    for n, text in enumerate(STUDY):
        words = text.split()
        each = step * 0.8 / len(words)
        out.append({"start": round(t, 2), "end": round(t + step * 0.8, 2), "text": text,
                    "words": [{"word": w, "start": round(t + k * each, 2),
                               "end": round(t + (k + 1) * each, 2)}
                              for k, w in enumerate(words)]})  # fmt: skip
        t += step * (2 if n % 2 else 1)
    return out


def refuse_link(url: str, folder: Path) -> Path:
    """Local runs never reach Instagram: a link always says to upload instead."""
    from app.reel import BLOCKED, Refused

    raise Refused("blocked", BLOCKED)


def study_link(url: str, folder: Path) -> Path:
    """A song-ad study's link on the stand-ins: the 6 s test clip, so a walk reaches the
    finished study; a reel id with "blocked" in it is refused, as Instagram would."""
    if "blocked" in url:
        return refuse_link(url, folder)
    return two_scenes(folder / "reel.mp4")


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

    video_failures = 0  # tests: fail this many video watches, like Gemini's upload did (E001)

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
            if self._jobs[ref].get("videos") and FakeMedia.video_failures > 0:
                FakeMedia.video_failures -= 1
                return Result("failed", error="ModelError: Failed to upload video (E001)")
            return Result("succeeded", output={"text": json.dumps(watch(self._jobs[ref]))})
        if self._jobs[ref]["kind"] == "speech" and "fake:fail" in self._jobs[ref]["prompt"]:
            return Result("failed", error="The voice service failed (stand-in)")
        return Result("succeeded", output={"url": f"fake://{ref}"}, files=[f"fake://{ref}"])

    def fetch(self, url: str) -> tuple[bytes, str]:
        job = self._jobs[url.removeprefix("fake://")]
        aspect = job.get("aspect_ratio", "9:16")
        if job["kind"] == "video":
            return mp4(aspect, int(job.get("duration", 5))), "video/mp4"
        if job["kind"] == "speech":
            return narration(job["prompt"]), "audio/mpeg"
        return png(aspect), "image/png"


class FakeSuno:
    """Suno's place (app/music.py): each request gives 2 songs on its first check, or the
    outcome a style-line marker asks for."""

    name, paid = "suno", False

    def __init__(self):
        self._styles: dict[str, str] = {}
        self._ids = itertools.count(1)

    def submit(self, kind: str, input: dict) -> str:
        ref = f"suno-{next(self._ids)}"
        self._styles[ref] = input["input"]["style"]
        return ref

    def poll(self, ref: str) -> Result:
        style = self._styles[ref]
        if failed := next((e for marker, e in OUTCOMES.items() if marker in style), None):
            return Result("failed", error=failed)
        count = 1 if "fake:one-song" in style else 2  # a reply with fewer songs than asked
        return Result("succeeded", files=[f"fake://{ref}/{n}" for n in range(1, count + 1)])

    def fetch(self, url: str) -> tuple[bytes, str]:
        return song(self._styles[url.removeprefix("fake://").split("/")[0]]), "audio/mpeg"


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
        # Who plays whom, as the cast lines now say ("char:5 | Leo | plays Nate, the groom")
        plays = {
            re.sub(r"^(the|a|an) ", "", m[1].split(",")[0].split("(")[0].strip().lower()): m[0]
            for m in re.findall(
                r"^(char:\d+) \|[^|\n]*\| plays ([^:|\n]+)", _tag(prompt, "cast"), re.M
            )
        }

        def who(text):  # the speaker's own look, else the first cast member
            label = DIALOGUE.match(text)
            name = text.split(":", 1)[0].split("(")[0].strip().lower() if label else ""
            hits = [c for key, c in plays.items() if re.search(rf"\b{re.escape(key)}\b", name)]
            return hits[:1] or cast[:1]

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
                "character_ids": who(text) if DIALOGUE.match(text) else [],
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

    def _song_directions(self, prompt):
        """Two plain directions; adapting a <source>, its lines become the first one's lyrics
        and the second leaves its last line out. The first style line names the "sounds
        like" (as a model might). A note with fake:three answers 3 directions until it's
        asked to fix them; fake:three-always never fixes them."""
        source = [ln.split("| ", 1)[-1] for ln in _tag(prompt, "source").splitlines() if ln]
        lines = source or ["Wake up hungry, bowl is bright", "Iron Paws, it feels so right"]
        like = f" like {_tag(prompt, 'sounds_like')}" if _tag(prompt, "sounds_like") else ""

        def song(rows):
            return "[Verse 1]\n" + "\n".join(rows)

        note = _tag(prompt, "note")
        three = "fake:three-always" in note or ("fake:three" in note and "<fix>" not in prompt)
        answer = {
            "directions": [
                {"title": "Local song A", "concept": "A practice song.", "lyrics": song(lines),
                 "style_line": f"indie pop{like}, warm female lead, 104 BPM, playful",
                 "visual_concept": "Plain test B-roll.", "left_out": [],
                 "unchecked_claims": []},
                {"title": "Local song B", "concept": "A shorter practice song.",
                 "lyrics": song(lines[:-1] or lines), "style_line": "folk, male lead, 90 BPM",
                 "visual_concept": "Plain test B-roll.",
                 "left_out": [lines[-1]] if len(lines) > 1 else [],
                 "unchecked_claims": ["It feels so right"]},
            ],
            "recommended": 1,
        }  # fmt: skip
        if three:
            answer["directions"].append({**answer["directions"][1], "title": "Local song C"})
        return answer

    def _song_breakdown(self, prompt):
        """The story stand-in's plan, its shots back to back over the song's beats, all
        B-roll (no [Lip-sync] asked)."""
        plan = self._breakdown(prompt)
        seconds = float(re.search(r'<song seconds="([\d.]+)"', prompt).group(1))
        beats = [float(b) for b in re.search(r"Beats: ([\d. ]*)", prompt).group(1).split()]
        shots = [s for scene in plan["scenes"] for s in scene["shots"]]
        beats = beats or [seconds * k / len(shots) for k in range(len(shots))]  # a narration
        edges = [0.0, *(beats[len(beats) * k // len(shots)] for k in range(1, len(shots)))]
        for shot, a, b in zip(shots, edges, [*edges[1:], seconds], strict=True):
            shot.update(song_start=a, song_end=b, sung=False)
        return plan

    _narrated_breakdown = _song_breakdown  # the narration's sentences are the clock

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

    def _plan(self, prompt):
        """Every script line once, in order: one scene per heading, the cast in each."""
        cast = re.findall(r"^((?:char|slot):\d+)", _tag(prompt, "cast"), re.M)
        heading, scenes = ("SCENE", "INT.", "EXT."), []
        for n, words in re.findall(r"^(\d+)\| ?(.*)$", _tag(prompt, "script"), re.M):
            if not words.strip():
                continue
            head = words.strip().startswith(heading)
            if head or not scenes:
                place = words.strip() if head else "INT. HOME — DAY"
                scenes.append({"id": len(scenes) + 1, "part": "Story", "place": place,
                               "cast": cast, "lines": []})  # fmt: skip
            if not head:
                scenes[-1]["lines"].append({"line": int(n), "action": "They react, big.",
                                            "product": None})  # fmt: skip
        scenes = [s for s in scenes if s["lines"]]
        for i, s in enumerate(scenes, 1):
            s["id"] = i
        shape = {"name": "Stand-in", "parts": ["Story"], "based_on": "pattern"}
        return {"structure": shape, "cast": cast, "scenes": scenes}

    def _item_check(self, prompt):
        """The first character sheet "may differ" on every check (so Advice, Looks fine and
        Change this… can all be walked for free); an item with only a product matches."""
        who = re.search(r"\b(char|slot):\d+", prompt)
        if not who:
            return {"findings": []}
        return {"findings": [{"kind": "face", "who": who[0], "says": "Their face may differ "
                              "from their sheet", "note": "Keep their face exactly as on "
                              "their sheet."}]}  # fmt: skip

    def _look_fit(self, prompt):  # every look fits
        return {"fits": True, "seen": _tag(prompt, "character"), "problem": ""}

    def _change(self, prompt):  # the note, added as one more line
        return {"prompt": f"{_tag(prompt, 'prompt')}\n{_tag(prompt, 'note')}".strip()}

    def _improve(self, prompt):
        refs, idea = _tag(prompt, "references"), _tag(prompt, "idea") or prompt.strip()
        return {"prompt": f"{refs}\n{idea}" if refs else idea}

    def submit(self, kind: str, input: dict) -> str:  # pragma: no cover - sync provider
        raise NotImplementedError

    def poll(self, ref: str) -> Result:  # pragma: no cover - sync provider
        raise NotImplementedError

    def fetch(self, url: str) -> tuple[bytes, str]:  # pragma: no cover - no files
        raise NotImplementedError
