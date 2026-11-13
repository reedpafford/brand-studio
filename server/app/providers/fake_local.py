"""Stand-ins for Replicate and Claude in local runs (BS_FAKE_PROVIDERS=true). Nothing is sent
anywhere and nothing is billed: images are a plain grey picture, videos a few grey seconds,
and each Claude step gets a simple answer in the right shape (made from the script and
breakdown in the request), so every page can be clicked through end to end."""

import base64
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
from app.providers import STAND_IN, Result

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


def hear_take(path: Path, job: dict) -> list[dict]:
    """Stand-in hearing of a take: its script lines at a speaking pace inside the take. A
    marker in the take's prompt walks each finding (QA): fake:drop-line (the last line isn't said),
    fake:extra-line (an unscripted line after them), fake:misname (the brand said "Fobo"),
    fake:says-brand (said right, "fomo") or fake:gasp (a gasp after the lines). Each line has
    its words and when, as whisper gives them."""
    lines, prompt = [x["text"] for x in job["lines"]], job.get("prompt", "")
    if "fake:drop-line" in prompt:
        lines = lines[:-1]
    if "fake:misname" in prompt:
        lines = [f"{lines[0]} I love Fobo." if lines else "I love Fobo.", *lines[1:]]
    if "fake:extra-line" in prompt:
        lines = [*lines, "Can't believe it worked."]
    if "fake:gasp" in prompt:
        lines = [*lines, "(gasps)"]
    if "fake:says-brand" in prompt:  # the brand said right (a clean copy for a splice)
        lines = [f"{lines[0]} I love fomo." if lines else "I love fomo.", *lines[1:]]
    from app.song_timing import length

    try:
        seconds = length(path)
    except ValueError:  # not a real video (a unit test's path): the lines as they come
        seconds = 0.0
    return _timed(lines, seconds)


SAY_PACE, SAY_GAP, SAY_LEAD = (
    1 / 3.4,
    0.7,
    0.5,
)  # a word (narration's measured 3.3-3.5 a second), a pause


def _timed(lines: list[str], seconds: float) -> list[dict]:
    """The lines as a person says them in the take: about 3.4 words a second from 0.5 s in,
    0.7 s between lines, always inside the take (squeezed when it's shorter, as a real take
    is cut to its clip), so every word sits where the cut can keep it."""
    need = sum(len(t.split()) * SAY_PACE for t in lines) + SAY_GAP * max(len(lines) - 1, 0)
    room = seconds - 2 * SAY_LEAD if seconds > 2 * SAY_LEAD else need
    fit = min(1.0, room / need) if need else 1.0
    out, at = [], SAY_LEAD if seconds > 2 * SAY_LEAD else 0.0
    for text in lines:
        took = len(text.split()) * SAY_PACE * fit
        out.append({"start": round(at, 2), "end": round(at + took, 2), "text": text,
                    "speaker": None, "words": _spread(text, at, at + took)})  # fmt: skip
        at += took + SAY_GAP * fit
    return out


def _spread(text: str, start: float, end: float) -> list[dict]:
    """A line's words, evenly over its time (whisper gives each word's own)."""
    words = text.split()
    each = (end - start) / max(len(words), 1)
    return [{"word": w.strip(".,!?"), "start": round(start + k * each, 2),
             "end": round(start + (k + 1) * each, 2)} for k, w in enumerate(words)]  # fmt: skip


def hear_cut(path: Path, job: dict) -> list[dict]:
    """Stand-in hearing of a cut: nobody speaks (so a stand-in mute never covers a script
    word); its frames and clips are found as for a real cut."""
    return []


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


def hear_song(path: Path, lyrics: str, prompted: bool = True) -> list[dict]:
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
# call; "fake:misheard" makes the word after it heard one letter off ("fomo" as "foma")
# unless the request carries the `say` tag ("[clearly]"): the voice is read quieter then,
# which the stand-in Whisper tells by its peak. v3 tags are never read.
WORD, GAP, MISHEARD, LONG = 0.3, 0.8, 0.3, 80


def narration(text: str) -> bytes:
    from app.narration import MARK, SAY, sentences

    told = f"[{SAY}]" in text
    loud = MISHEARD if "fake:misheard" in text and not told else 1
    text = MARK.sub("", re.sub(r"\[[^\]]*\]\s*", "", text))  # MiniMax's marks aren't read
    said = sentences(text)
    if len(said) > LONG:  # ffmpeg takes only so long an expression: made in halves, joined
        from app.narration import join

        with tempfile.TemporaryDirectory() as tmp:
            halves = [Path(tmp) / "a.mp3", Path(tmp) / "b.mp3"]
            for path, half in zip(halves, (said[: len(said) // 2], said[len(said) // 2 :]),
                                  strict=True):  # fmt: skip
                path.write_bytes(narration(f"[{SAY}] " * told + " ".join(half)))
            return join(halves, Path(tmp) / "voice.mp3").read_bytes()
    parts, t = [], GAP
    for sentence in said:
        end = t + WORD * len(sentence.split())
        parts.append(f"between(t,{t:.2f},{end:.2f})")
        t = end + GAP
    tone = f"{loud}*sin(2*PI*220*t)*({'+'.join(parts) or '0'})"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "voice.mp3"
        source = ["-f", "lavfi", "-i", f"aevalsrc='{tone}':s=22050:d={t:.2f}"]
        command = ["ffmpeg", "-v", "error", *source, "-c:a", "libmp3lame", "-b:a", "64k"]
        subprocess.run([*command, str(path)], check=True, timeout=120)  # noqa: S603
        return path.read_bytes()


def bed(seconds: int) -> bytes:
    """The stand-in music bed: a soft low chord the length asked for."""
    tone = "0.2*sin(2*PI*110*t)+0.15*sin(2*PI*165*t)"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bed.mp3"
        source = ["-f", "lavfi", "-i", f"aevalsrc='{tone}':s=22050:d={seconds}"]
        command = ["ffmpeg", "-v", "error", *source, "-c:a", "libmp3lame", "-b:a", "64k"]
        subprocess.run([*command, str(path)], check=True, timeout=120)  # noqa: S603
        return path.read_bytes()


def hear_voice(path: Path, text: str, prompted: bool = True) -> list[dict]:
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
    if "fake:misheard" in text and max(map(abs, samples), default=0) < 16000:  # no `say` tag
        k = next((n + 1 for n, w in enumerate(heard) if w["word"] == "fake:misheard"), len(heard))
        if k < len(heard):
            w = heard[k]["word"]
            heard[k] = {**heard[k], "word": w[:-1] + ("e" if w[-1:] == "a" else "a")}
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
    """A reel's link on the stand-ins (Import a reel, or a song-ad study): the 6 s test clip,
    never fetched, so a walk reaches the read reel or the finished study; a reel id with
    "blocked" in it is refused, as Instagram would."""
    if "blocked" in url:
        return refuse_link(url, folder)
    return two_scenes(folder / "reel.mp4")


def png(aspect: str) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", SIZES.get(aspect, (512, 512)), (128, 128, 128)).save(out, "PNG")
    return out.getvalue()


def mp4(aspect: str, seconds: int, sound: bool = False) -> bytes:
    """A few grey seconds; with `sound` a soft tone too (MMAudio's stand-in: the take with the
    sound it made)."""
    w, h = SIZES.get(aspect, (512, 512))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fake.mp4"
        grey = ["-f", "lavfi", "-i", f"color=c=gray:s={w}x{h}:d={seconds}"]
        grey += ["-f", "lavfi", "-i", f"sine=f=330:d={seconds}", "-c:a", "aac"] if sound else []
        command = ["ffmpeg", "-v", "error", *grey, "-pix_fmt", "yuv420p", str(path)]
        subprocess.run(command, check=True, timeout=60)  # noqa: S603 - fixed arguments
        return path.read_bytes()


def _spoken(text: str) -> dict:
    if not DIALOGUE.match(text):
        return {"speaker": None, "line": None}
    speaker, line = text.split(":", 1)
    return {"speaker": speaker.title(), "line": line.strip()}


def _talks(who: str, text: str) -> dict:
    return {"speaker": who, "line": _spoken(text)["line"] or text.strip()}


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
        ref = f"{STAND_IN}local-{next(self._ids)}"
        said = input.get("input", {})
        self._jobs[ref] = {"kind": kind, "prompt": said.get("text", ""), **said,  # MiniMax: text
                           "model_id": input.get("model"), "parts": input.get("parts")}  # fmt: skip
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
        if self._jobs[ref]["kind"] == "speech":  # a voice's own limit, as the real ones refuse
            from app.narration import MOST, MOST_ELSE

            texts = self._jobs[ref]["parts"] or [self._jobs[ref]["prompt"]]
            most = MOST.get(self._jobs[ref]["model_id"], MOST_ELSE)
            if long := next((t for t in texts if len(t) > most), None):
                return Result("failed", error=f"Request text length ({len(long)}) exceeds the "
                              f"maximum text length of {most} characters")  # fmt: skip
            return Result("succeeded", output={},
                          files=[f"fake://{ref}#{k}" for k in range(len(texts))])  # fmt: skip
        if self._jobs[ref]["kind"] == "voice":  # a clone: its voice id and a preview
            fields = {
                "voice_id": f"stand-in-voice-{ref.rsplit('-', 1)[-1]}",
                "model": self._jobs[ref].get("model", ""),
                "preview": f"fake://{ref}",
            }
            return Result("succeeded", output={"fields": fields}, files=[f"fake://{ref}"])
        return Result("succeeded", output={"url": f"fake://{ref}"}, files=[f"fake://{ref}"])

    def fetch(self, url: str) -> tuple[bytes, str]:
        url, _, part = url.partition("#")  # a narration read in parts: this part's words
        job = self._jobs[url.removeprefix("fake://")]
        if part and job["parts"]:
            job = {**job, "prompt": job["parts"][int(part)]}
        aspect = job.get("aspect_ratio", "9:16")
        if job.get("isolate_stem"):  # Demucs's stand-in: the voice is the take's sound as given
            kind, _, data = job["audio"].removeprefix("data:").partition(";base64,")
            return base64.b64decode(data), kind
        if job["kind"] in ("video", "sound"):
            return mp4(aspect, int(job.get("duration", 5)), job["kind"] == "sound"), "video/mp4"
        if job["kind"] in ("speech", "voice"):
            return narration(job["prompt"] or "This is the cloned voice."), "audio/mpeg"
        if job["kind"] == "music_bed":
            return bed(int(job.get("duration", 10))), "audio/mpeg"
        return png(aspect), "image/png"


class FakeSuno:
    """Suno's place (app/music.py): each request gives 2 songs on its first check, or the
    outcome a style-line marker asks for."""

    name, paid = "suno", False

    def __init__(self):
        self._styles: dict[str, str] = {}
        self._ids = itertools.count(1)

    def submit(self, kind: str, input: dict) -> str:
        ref = f"{STAND_IN}suno-{next(self._ids)}"
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

    def _director(self, prompt):
        """The stand-in director: the agents' order, from the video's state (app/director)."""
        from app.director import NOT_MADE, choose

        allowed = json.loads(_tag(prompt, "allowed") or "{}")
        asked = json.loads(_tag(prompt, "chat") or "[]")
        done = [a["tool"] for a in json.loads(_tag(prompt, "last_actions") or "[]")
                if a.get("result") != NOT_MADE]  # held for Make it: still to make  # fmt: skip
        questions = json.loads(_tag(prompt, "asks") or "[]")
        return choose({**json.loads(_tag(prompt, "video")), "allowed": allowed, "chat": asked,
                       "done": done, "asks": questions})  # fmt: skip

    def _review_stills(self, prompt):
        """The stand-in look at the stills: they tell the treatment (a test that walks a
        redraw gives its own finding)."""
        return {"ready": True, "findings": []}

    def _treatment(self, prompt):
        """The stand-in treatment: one beat a spoken line (the Director's)."""
        from app import prompts

        return prompts.stand_in_treatment(_tag(prompt, "script") or "")

    def _one_pass(self, prompt):
        """The stand-in shooting plan (app/one_pass.py): a clip for each scene heading's lines,
        filled up to the model's longest, a shot for each spoken line, by its number; each
        speaker not in <cast> a role, each heading a place. With <notes> and <plan>, the plan
        again with only the clips a note names changed. Markers in the script walk the checks
        (QA): fake:skip-line leaves the last line out of the first answer (the re-ask gives
        it), fake:skip-line-twice out of both; fake:drop-line goes into the first clip's
        prompt, so its take's listen misses a line (`hear_take`)."""
        from app.one_pass_assemble import spoken

        notes, before = _tag(prompt, "notes"), _tag(prompt, "plan")
        if notes and before:
            plan = json.loads(before)
            for n in re.findall(r"\bclip (\d+)", notes, re.I):
                for c in plan["clips"]:
                    if c["id"] == f"c{n}":
                        c["shots"][0]["action"] += " Made again as the note asks."
            return plan
        limits = re.search(r"(\d+)–(\d+) s per clip", prompt)
        low, high = map(int, limits.groups()) if limits else (4, 15)
        text = "\n".join(x.split("| ", 1)[-1] if "|" in x else ""
                         for x in _tag(prompt, "script").splitlines())  # fmt: skip
        if "<song " in prompt:
            return self._timed_plan(prompt, text, high)
        films = re.match(r"(.+?) presents this video", _tag(prompt, "talker"))
        said = spoken(text, films[1] if films else "")
        skip = "fake:skip-line" in text and ("<fix>" not in prompt or "-twice" in text)
        cast = " ".join(_tag(prompt, "cast").splitlines()).lower()
        who = list(dict.fromkeys(name.split(" (")[0] for name, _ in said.values()))
        clips, places, head = [], [], ""
        for n, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith(("SCENE", "INT.", "EXT.")):
                head = line.strip()
                places += [{"name": head, "description": "A plain grey test room."}]
            if n not in said or (skip and n == max(said)):
                continue
            name, words = said[n]
            shot = {
                "seconds": math.ceil(len(words.split()) / 3) + 1,
                "camera": "Medium shot",
                "action": f"{name.split(' (')[0]} says line {n} to the room.",
                "people": [name.split(" (")[0]],
                "extras": "",
                "line": n,
                "how": "plainly",
            }
            last = clips[-1] if clips else None
            if (
                last is None
                or last["place"] != head
                or sum(x["seconds"] for x in last["shots"]) + shot["seconds"] > high
            ):
                clips.append({"id": f"c{len(clips) + 1}", "name": f"Clip {len(clips) + 1}",
                              "purpose": "escalate", "summary": "A plain test scene.",
                              "place": head, "setting": "Plain grey daylight.", "assets": [],
                              "sound": "room tone", "shots": []})  # fmt: skip
            clips[-1]["shots"].append(shot)
        for c in clips:  # never shorter than the model makes
            c["shots"][-1]["seconds"] += max(low - sum(x["seconds"] for x in c["shots"]), 0)
        if films and clips:  # an Omni talker: one B-roll clip, of the first line, after its clip
            show = {**clips[0], "kind": "broll", "name": "Cutaway", "shots": [
                {**clips[0]["shots"][0], "seconds": low, "people": [], "how": "",
                 "action": "What the first line names, shown plainly."}]}  # fmt: skip
            real = re.search(r"- (footage:\d+) \| [\d.]+ s", self._system)
            if real and "may BE one of these clips" in self._system:  # UGC: the brand's own
                show.update(footage=real[1], footage_at=0)
            clips.insert(1, show)
            for k, c in enumerate(clips, 1):
                c["id"] = f"c{k}"
        if clips:
            clips[0]["purpose"], clips[-1]["purpose"] = "hook", "payoff"
            clips[0]["assets"] = re.findall(r"^(prop:\d+)", _tag(prompt, "products"), re.M)
            if "fake:drop-line" in text:
                clips[0]["shots"][0]["action"] += " fake:drop-line"
        return {
            "treatment": {"hook": "The first line, on the conflict, at once.",
                          "logline": "The story as the script tells it.",
                          "why_it_holds": "Each clip raises the stakes to the payoff.",
                          "ending": "The payoff, then the script's ending."},
            "voices": [{"who": w, "sounds": "a plain test voice, mid pitch, even pace"}
                       for w in who],
            "roles": [{"name": w, "description": "A plain test person in a grey sweatshirt."}
                      for w in who if w.lower() not in cast],
            "places": places, "clips": clips,
        }  # fmt: skip

    def _timed_plan(self, prompt, text, high):
        """The stand-in plan of a video timed to <song> (a narration or a song): a B-roll shot
        for each timed line, its `at` the line's start (a line under a second after the last
        shares its shot), in clips filled up to the model's longest; the first cast member is
        in every shot (never a host who stands in a corner: they are in no shot; a host who
        acts is the one in every shot). With a <host> who talks to camera, the first and the
        last clip are the talker's. fake:bad-at in the script starts the second shot too soon
        (code leaves it out: one_pass_timed.snapped)."""
        heard = prompt.split("Sung lines:", 1)[1].split("</song>", 1)[0]
        starts = [float(a) for a in re.findall(r"^\d+\| (\d+\.\d+)–", heard, re.M)]
        ats = [0.0]
        for at in starts[1:]:
            if at >= ats[-1] + 1:
                ats.append(at)
        if "fake:bad-at" in text and len(ats) > 1:
            ats[1] = ats[0] + 0.2
        cast = [x.split(" | ")[1] for x in _tag(prompt, "cast").splitlines() if " | " in x]
        host = _tag(prompt, "host")
        talks, acts = ", talking to camera" in host, "by acting in it" in host
        who = host.split(" presents this video")[0]
        roles = [{"name": who, "description": "A plain test person in a grey sweatshirt."}] * (
            acts and who not in cast)  # fmt: skip
        cast = [who] if acts else [] if host else cast
        groups: list[list[float]] = []
        for k, at in enumerate(ats):
            apart = talks and k in (1, len(ats) - 1)  # the talker's own first and last clip
            if not groups or apart or at - groups[-1][0] + 2 > high:
                groups.append([])
            groups[-1].append(at)
        clips = [{"id": f"c{k}", "name": f"Clip {k}", "purpose": "escalate",
                  "summary": "A plain test scene.", "place": "The test room",
                  "setting": "Plain grey daylight.", "assets": [], "sound": "room tone",
                  "kind": "host" if talks and k in (1, len(groups)) else "broll",
                  "footage": "", "footage_at": 0,
                  "shots": [{"seconds": 1, "at": at, "camera": "Medium shot",
                             "action": f"The picture for the words heard at {at:.2f} s.",
                             "people": cast[:1], "extras": "", "line": None, "how": ""}
                            for at in group]}
                 for k, group in enumerate(groups, 1)]  # fmt: skip
        clips[0]["purpose"], clips[-1]["purpose"] = "hook", "payoff"
        return {
            "treatment": {"hook": "The first words, on the most striking picture.",
                          "logline": "The story as the script tells it.",
                          "why_it_holds": "Each picture shows its words as they are heard.",
                          "ending": "The payoff, then the script's ending."},
            "voices": [], "roles": roles,
            "places": [{"name": "The test room", "description": "A plain grey test room."}],
            "clips": clips,
        }  # fmt: skip

    def _enhance(self, prompt):
        """Up to three directions on the script's first lines that have words (a camera move,
        a movement, a reaction), each quoting its line exactly, and one note: enough to walk
        Directions on the test site for free."""
        numbered = re.findall(r"^(\d+)\| (.*\S)\s*$", _tag(prompt, "script"), re.M)
        said = [
            (int(n), line) for n, line in numbered if not re.match(r"^(SCENE|INT\.|EXT\.)", line)
        ]
        kinds = [
            ("camera", "Slow push in as this line lands.", "Draws the eye to the moment."),
            (
                "action",
                "A small move that shows the line, not just says it.",
                "Gives the line a picture.",
            ),
            (
                "reaction",
                "Hold on the listener's face for a beat.",
                "Lets the line land before the cut.",
            ),
        ]
        suggestions = [
            {
                "id": f"s{i + 1}",
                "kind": kind,
                "anchor": {"line": n, "quote": line},
                "placement": "after",
                "text": text,
                "screen_id": None,
                "reason": reason,
            }
            for i, ((n, line), (kind, text, reason)) in enumerate(zip(said, kinds, strict=False))
        ]
        notes = (
            [{"line": said[-1][0], "text": "A practice note: the last line could name the brand."}]
            if said
            else []
        )
        return {"suggestions": suggestions, "notes": notes}

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

    def _language_sample(self, prompt):
        """A practice script that names the language it was asked for."""
        said = _tag(prompt, "language")
        line = f"[Hook]\nHERO: ({said}) A practice line."
        return {"drafts": [{"hook_idea": f"Test hook {n}", "script": line} for n in "AB"]}

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

    def _video_variations(self, prompt):
        """<count> practice hooks (each remakes the first clip) or endings (the last one); with
        quoted words in <note>, the first uses them on the line that clip says."""
        clips = json.loads(_tag(prompt, "clips") or "[]")
        hook = _tag(prompt, "part") == "hook"
        clip = clips[0] if hook else clips[-1]
        line = next((n for s in clip["shots"] for n in s["script_lines"]), 0)
        words = re.findall(r"“([^”]+)”", _tag(prompt, "note"))
        return {"variations": [
            {"title": f"Practice {'hook' if hook else 'ending'} {n}",
             "direction": f"A practice {'opening' if hook else 'payoff'}, idea {n}.",
             "clips": [clip["id"]], "note": f"Stage it as practice idea {n}.",
             **({"line": line, "words": words[0]} if words and n == 1 else {})}
            for n in range(1, int(_tag(prompt, "count") or 2) + 1)]}  # fmt: skip

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

        # An Omni talker (talker.PIECE) says every line on camera, a line with no label too
        talks = re.match(r"(.+?) is the presenter", _tag(prompt, "talker"))
        shots = [
            {
                "id": f"1.{i}",
                "script_lines": [int(n)],
                **(_talks(talks[1], text) if talks else _spoken(text)),
                # Not the script's words: an action that reads like speech fails #135's check.
                "action": f"A plain test shot for script line {n}.",
                "reaction": None,
                "camera": "Medium shot, static",
                "seconds": max(1.5, round(len(text.split()) / 4.8, 1)),  # spoken pace
                # A speaker is the first cast member; a ★ line shows the brand's first screen.
                "character_ids": cast[:1] if talks else who(text) if DIALOGUE.match(text) else [],
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
        if talks:  # after each of their pieces, one B-roll shot of its first line, laid over it
            broll = {"speaker": None, "line": None, "character_ids": [], "seconds": float(low),
                     "action": "B-roll of what it says."}  # fmt: skip
            groups = [g for k, group in enumerate(groups, 1)
                      for g in (group, [{**group[0], **broll, "id": f"1.b{k}"}])]  # fmt: skip
            shots = [s for group in groups for s in group]
            real = re.search(r"- (footage:\d+) \| ([\d.]+) s", self._system)
            if real and "This video is UGC" in self._system:  # its first B-roll is the real clip
                end = min(float(real[2]), float(low))
                groups[1][0]["footage"] = {"id": real[1], "start": 0.0, "end": end, "sound": False}
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
        B-roll (no [Lip-sync] asked), its clips cut at the video model's longest by the song's
        own times (a 0:24 song on a 15 s model is two clips, never one it can't make)."""
        plan = self._breakdown(prompt)
        seconds = float(re.search(r'<song seconds="([\d.]+)"', prompt).group(1))
        beats = [float(b) for b in re.search(r"Beats: ([\d. ]*)", prompt).group(1).split()]
        shots = [s for scene in plan["scenes"] for s in scene["shots"]]
        # A narration under a style with talker shots (UGC): every other shot is the talker's
        talker = not beats and "in every talker shot" in self._system  # the UGC guide's
        beats = beats or [seconds * k / len(shots) for k in range(len(shots))]  # a narration
        edges = [0.0, *(beats[len(beats) * k // len(shots)] for k in range(1, len(shots)))]
        for k, (shot, a, b) in enumerate(zip(shots, edges, [*edges[1:], seconds], strict=True)):
            shot.update(song_start=a, song_end=b, sung=talker and k % 2 == 0,
                        seconds=round(b - a, 2))  # fmt: skip
        limits = re.search(r"(\d+)–(\d+) s per clip", prompt)
        high = int(limits.group(2)) if limits else 15
        groups: list[list[dict]] = []
        for shot in shots:  # clips fill up to the model's longest, by the song's clock
            if not groups or shot["song_end"] - groups[-1][0]["song_start"] > high:
                groups.append([])
            groups[-1].append(shot)
        plan["clips"] = [
            {"id": f"c{k}", "shot_ids": [s["id"] for s in group],
             "seconds": math.ceil(group[-1]["song_end"] - group[0]["song_start"] - 0.01),
             "seam": "end" if k == len(groups) else "model length limit"}
            for k, group in enumerate(groups, 1)
        ]  # fmt: skip
        return plan

    _narrated_breakdown = _song_breakdown  # the narration's sentences are the clock

    def _narration_music(self, prompt):
        """A plain instrumental bed; a note with fake:vocals asks for a choir until it's fixed."""
        sing = "fake:vocals" in _tag(prompt, "note") and "<fix>" not in prompt
        words = (
            "Warm acoustic documentary bed: soft piano, light strings, brushed drums and a "
            "low bass, about 90 BPM. Starts calm and curious, lifts in the middle third and "
            "lands hopeful in the last third. Steady and low under the narration."
        )
        return {"prompt": words + (" A choir sings the hook." if sing else ""),
                "arc": "Calm, then hopeful"}  # fmt: skip

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

    def _plan_scene(self, prompt):
        """The asked scene, its lines as they are, each action made bigger."""
        want = int(_tag(prompt, "scene"))
        block = prompt[prompt.rfind("<plan>") :]
        head = re.search(rf"^Scene {want} \((.*?)\): (.*?) · (.*)$", block, re.M)
        rest = block[head.end() :]
        rest = rest[: m.start()] if (m := re.search(r"^Scene \d+ ", rest, re.M)) else rest
        lines = [{"line": int(n), "action": "Bigger: they react twice as hard.", "product": None}
                 for n in re.findall(r"^(\d+)\|", rest, re.M)]  # fmt: skip
        cast = [c.strip() for c in head[3].split(",") if c.strip()]
        return {"id": want, "part": head[1], "place": head[2], "cast": cast, "lines": lines}

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
        """The first character sheet "may differ" on every still's check (so Advice, Looks
        fine and Change this… can all be walked for free); a still with only a product
        matches. A marker in a shot's action walks slice 2's kinds (QA): fake:eyes,
        fake:extra-person, and fake:screen when the check was given the brand's screens."""
        found = []
        who = re.search(r"<sheet[^>]*id=\"((?:char|slot):\d+)\"", prompt)
        if who:
            found.append(
                {
                    "kind": "face",
                    "who": who[1],
                    "says": "Their face may differ from their sheet",
                    "note": "Keep their face exactly as on their sheet.",
                }
            )
        if "fake:eyes" in prompt:
            found.append(
                {
                    "kind": "eyes",
                    "who": "",
                    "says": "Their eyes glow red",
                    "note": "Keep normal human eyes the whole time, never glowing or red.",
                }
            )
        if "fake:extra-person" in prompt:
            found.append(
                {
                    "kind": "cast",
                    "who": "extra",
                    "says": "Someone who isn't in the cast is in the shot",
                    "note": "Only the cast in this shot: no other characters.",
                }
            )
        if "fake:screen" in prompt and "<screens>" in prompt:
            found.append(
                {
                    "kind": "screen",
                    "who": "screen",
                    "says": "The phone shows another app",
                    "note": "Show the brand's Home screen on the phone, logo readable.",
                }
            )
        return {"findings": found}  # fmt: skip

    def _take_watch(self, prompt):
        """The stand-in watch of a take: it plays as its shot says, unless a marker in the
        shot's action walks a finding (QA): fake:redo (cartoon eyes on the stomach: remade
        with its prompt rewritten), fake:text (words burned in: remade with no text),
        fake:face (the face differs from its sheet: remade), fake:music (music under the
        voice, from the spectrogram only: not confirmed, never remade), fake:keep (a small
        fault, kept), fake:screen (an invented app screen: the director's, never remade)."""
        shot = _tag(prompt, "shot") or ""
        who = re.search(r"<sheet[^>]*id=\"((?:char|slot):\d+)\"", prompt)
        found = {"fake:redo": ("action", "Cartoon eyes landed on the stomach",
                               "no face on the organs", "", "picture"),
                 "fake:text": ("text", "Garbled words burned into the picture", "no text", "",
                               "picture"),
                 "fake:face": ("cast", "Their face differs from their sheet",
                               "the face as on their sheet", who[1] if who else "", "picture"),
                 "fake:music": ("sound", "Music may run under the voice", "no music", "",
                                "sound"),
                 "fake:screen": ("screen", "The phone shows an invented app, not fomo's Home",
                                 "fomo's real Home screen", "screen", "picture")}  # fmt: skip
        for marker, (kind, says, note, ref, evidence) in found.items():
            if marker in shot:
                return {"seen": f"{says} at 0:00.4.", "verdict": "redo", "note": note,
                        "faults": [{"kind": kind, "at": 0.4, "says": says, "who": ref,
                                    "evidence": evidence}],
                        "prompt": f"{_tag(prompt, 'prompt')}\nShow {note}."}  # fmt: skip
        if "fake:keep" in shot:
            return {"seen": "A small wobble in the background at 0:00.5; kept.", "verdict": "keep",
                    "faults": [{"kind": "motion", "at": 0.5, "says": "A small wobble",
                                "who": "", "evidence": "picture"}]}  # fmt: skip
        return {"seen": "It plays as the shot says.", "verdict": "keep", "faults": []}

    def _watch_cut(self, prompt):
        """The stand-in watch of a cut (so the director's fixes can be walked, Next-Server's
        e2e): a redo of the first clip and a half-second mute in the last, every time; the
        ending lands. A fake:watch-pick marker in a clip's shot adds a pick of its other take."""
        cut = json.loads(_tag(prompt, "cut") or "[]")
        if not cut:
            return {"lands": True, "summary": "Nothing to watch.", "findings": []}
        first, last = cut[0], cut[-1]
        mid = round((last["start"] + last["end"]) / 2, 2)
        found = [
            {"clip_id": first["clip_id"], "start": first["start"],
             "end": min(first["start"] + 1, first["end"]),
             "says": f"{first['clip_id']}: the opening face changes between shots",
             "fix": "redo", "take_id": None, "kind": "cast", "evidence": "picture",
             "note": "Keep the same face in every shot, as on their sheet."},
            {"clip_id": last["clip_id"], "start": mid, "end": round(mid + 0.5, 2),
             "says": f"{last['clip_id']}: a stray sound nobody asked for", "fix": "mute",
             "kind": "sound", "evidence": "sound",
             "take_id": None, "note": "a stray sound"},
        ]  # fmt: skip
        for c in cut:
            if "fake:watch-pick" in json.dumps(c["shots"]) and c["other_takes"]:
                found.append({"clip_id": c["clip_id"], "start": c["start"], "end": c["end"],
                              "says": f"{c['clip_id']}: another take reads better",
                              "fix": "pick", "take_id": c["other_takes"][0]["take_id"],
                              "kind": "picture", "evidence": "picture",
                              "note": "The other take keeps the line."})  # fmt: skip
        return {"lands": True, "summary": "It plays; two small fixes.", "findings": found}

    def _footage_describe(self, prompt):  # a brand's real clip: of its first product
        first = next(iter(_tag(prompt, "products").splitlines()), "")
        product = "" if first == "(none)" else first
        return {"description": f"The {product or 'product'} shown working, close up, on a desk.",
                "product": product}  # fmt: skip  # named as a model might: never saved

    def _look_fit(self, prompt):  # every look fits
        return {"fits": True, "seen": _tag(prompt, "character"), "problem": ""}

    def _fold_note(self, prompt):  # the note in the description's place of the same words
        was, note = _tag(prompt, "description"), _tag(prompt, "note")
        return {"description": f"{was.rstrip('. ')}, {note[:1].lower()}{note[1:]}".strip(", ")}

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
