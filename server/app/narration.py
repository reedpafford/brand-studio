"""Narrated ads (flows N1, V6n): one voice reads the version's words. A narration is a song
take of kind "narration" (docs/next/data.md), so Use, out of date, Undo and the video's own
choice work as for a song; its lyrics are the words it reads and its style line is empty.

Made with one voice call (ElevenLabs v3, or MiniMax Speech 2.8 HD for its emotion and pause
control, through Replicate, priced from the catalogue per 1,000 characters); then, free on our
server: every pause is cut down in its quiet middle only (never into a word), the trimmed
narration is heard, and each sentence's start and end are measured (the breakdown's clock, as
a song's lines are), with any words it says that the script doesn't have (`extras`: such a
take is never used). A UGC talker's narration then gets its room sound (app/room.py)."""

import math
import re
import subprocess
from pathlib import Path

from app import song_timing
from app.prompts import check

KIND = "narration"
TIMED = ("song", "narrated")  # script kinds whose videos are timed to a take
MODEL = "elevenlabs-v3"
VOICE = "Sarah"
# Natural v3 voices (song-ad-workflow.md); the names are ElevenLabs v3's own (Replicate's enum).
# Austin (deep, ~81 Hz) and Roger (relaxed, ~115 Hz) are male, from the presenter-1 test.
# Words a second at our slowest voice (the paid test: 2.6, at v3's own speed 1; Reed's reference
# narrator reads 3.37)
SLOWEST = 2.6
# v3 does take a speed: Replicate's elevenlabs/v3 schema (recorded 29 Oct, fixtures) has
# `speed`, 0.7 to 1.2, default 1. A remake may set it for pace (`job`); the first read is at 1.
V3_SPEED = (0.7, 1.2)
FINAL_HOLD = 1.5  # seconds the last shot may hold past the last word, planned and kept
# (CRITIQUE-268: "And so do you" got 0.87 s and the video ended 0.06 s after it)
VOICED = 0.84  # the least of a narration the voice is on in the guides (84%: the rest pauses)
ELEVENLABS = (VOICE, "Alexandra", "Hope", "Jane", "Austin", "Roger")
# MiniMax Speech 2.8 HD (replicate.com/minimax/speech-2.8-hd; platform.minimax.io's system
# voice list): two men, three women in natural English for someone talking to their phone
# (UGC, Reed 3 Nov: "emotion inflection from minimax"); English_Graceful_Lady is the older
# woman (th-20s: of 4 older-woman voices the lowest, 186 Hz, with the widest range). Its own
# controls: an emotion, pause marks <#0.4#> and sounds like (breath) in the text; no free-text
# note. Speed 1.1 with emotion auto read at 3.2-3.4 words a second in the batch-b test (the UGC
# references: 3.3-3.5), but that was a clone on speech-02-hd: each voice's differs (below).
MINIMAX, MINIMAX_SPEED = "minimax-speech-2.8-hd", 1.1
MINIMAX_VOICES = ("English_FriendlyPerson", "English_Trustworth_Man", "English_Upbeat_Woman",
                  "English_ConfidentWoman", "English_Graceful_Lady")  # fmt: skip
# A voice's own start, where measured: English_FriendlyPerson read 4.9 words a second at 1.1, in
# auto and calm alike (video 281, takes 1-2); its speed scales that, so 0.76 is about 3.4.
VOICE_SPEEDS = {"English_FriendlyPerson": 0.76}
# An emotion slows MiniMax, so its speed rises (th-20s, English_Graceful_Lady: fearful 2.4 words a
# second at 1.25, 3.4-3.6 at 1.5; sad 1.6 at 1.1, 2.0 at 1.3), scaled to each voice's own start
SPEEDS = {"fearful": 1.5, "sad": 1.3}
FASTEST, SLOWEST_SPEED = 2.0, 0.5  # MiniMax's speed range
VOICES = ELEVENLABS + MINIMAX_VOICES
EMOTIONS = ("auto", "happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm",
            "fluent", "neutral")  # Replicate's enum for speech-2.8-hd and -turbo  # fmt: skip
# platform.minimax.io T2A: interjections are "only supported when using speech-2.8-hd or
# speech-2.8-turbo"; a pause mark <#x#> goes between words, never two in a row
SOUNDS = ("laughs", "chuckle", "coughs", "clear-throat", "groans", "breath", "pant", "inhale",
          "exhale", "gasps", "sniffs", "sighs", "snorts", "burps", "lip-smacking", "humming",
          "hissing", "emm", "sneezes")  # fmt: skip
MARK = re.compile(r"<#(\d{1,2}(?:\.\d{1,2})?)#>|\((?:" + "|".join(SOUNDS) + r")\)")
# A reading's longest mark, and the most quiet the trim keeps for one: it keeps that at EVERY
# gap, beside fades and a breath (281's 0.5 s marks: gaps near 0.8 s; the references: 0.5 s)
LONGEST_PAUSE, MARKED_KEEP = 0.6, 0.3
PAUSE = 0.25  # a gap between heard words longer than this isn't talking (`pace`)
# The quiet kept where the trim cuts a pause: half after the last word, half before the next.
# With each word's own fade (about 0.15-0.25 s above the quiet), sentences sit about 0.3 s
# apart. Video 261 kept every 0.5-0.8 s pause: its trim was cut, then refused because two
# Whisper reads of the same words differed (junk glued to a word), so it's now heard once.
KEEP = 0.2
# A blip this long inside a pause is the pause (`cuts`): MiniMax's gaps flicker around the quiet
# line, so 281's 0.6-1.3 s gaps stayed whole (0.9 s cut of 24 s); bridged, they're 0.6 s or under
BLIP = 0.05
# A v3 delivery tag, at most this many words: a longer note is read aloud (F1, video 261: "[A
# touch quicker and more animated, about 3.4 words a second…]" was spoken before the script)
TAG_WORDS = 3
# The tag a narration that said the brand's name wrong is read again with (`say`). v3 has no
# documented way to steer one word's sound without changing the words (elevenlabs.io's v3
# prompting guide: phoneme tags are Flash v2 only, and pronunciation dictionaries aren't among
# Replicate's v3 inputs; a respelling would change the script's words), and a sentence in a
# tag ("Say fomo as FOH-moh.") is read aloud.
SAY = "clearly"


def video_script(db, project):
    """A video's script; None for a video with no script (the earlier New video form)."""
    from app.models.script_library import Script, ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    return db.get(Script, draft.script_id) if draft else None


def video_kind(db, project) -> str:
    """A video's type is its script's kind: story, song or narrated (the engine of its format).
    A video with no script is a story. Its look is a setting apart (Song in any look)."""
    script = video_script(db, project)
    return script.kind if script else "story"


def longest(db, draft, video=None) -> int:
    """A narrated version's length for a quote (rule 36: up to, never below): the narration
    made for it (the video's own, else the version's Preferred), else its words at the
    slowest pace its style's guide allows (`slowest`; the dry run quoted 70 s for a script
    read in 104 s)."""
    from app import song_takes
    from app.models.songs import SongTake

    made = video is not None and video.song_take_id and db.get(SongTake, video.song_take_id)
    made = made or song_takes.preferred(db, draft)
    if made and made.seconds:
        return math.ceil(made.seconds)
    return math.ceil(
        len(check.narration_text(draft.text or "").split()) / slowest(db, draft, video)
    )


def slowest(db, draft, video=None) -> float:
    """Words a second a narration is quoted at, over its whole length: the lower bound of its
    style's pace while speaking (its guide's "3.3–3.5 words a second", its format's when the
    style says none; a read outside the range is made again at the speed that brings it in,
    `retimed`), with the pauses the guides measured around it (VOICED); else SLOWEST."""
    from app import guides
    from app.models.script_library import Script
    from app.script_library import format_id

    script = db.get(Script, draft.script_id)
    look = (video.look if video is not None else None) or script.look or "house"
    found = guides.pace(look, format_id(script))
    return round(found[0] * VOICED, 2) if found else SLOWEST


NO_WORDS = "Write the words first: the narrator reads them as written."
FAILED = "The narration didn't finish. Nothing was charged."
MAKING = "A narration is being made. It's ready in a moment."
LONG_NOTE = (
    f"A voice note is a short delivery tag of 1 to {TAG_WORDS} words with no numbers, "
    "like “quickly” or “warm, upbeat”: a longer one is read aloud."
)
SAYS_MORE = "This narration says words the script doesn't have (“{}”): make it again."
TIMING_FAILED = "We couldn't read this narration's timing. It's free to try again."
TIMING_UNREADABLE = "This narration's file can't be read. Make the narration again."


def sentences(text: str) -> list[str]:
    """One per line of the timing: each line split after . ! ? or …"""
    return [s for line in text.splitlines() for s in re.split(r"(?<=[.!?…])\s+", line) if s]


NOT_THE_WORDS = "The reading must say the script's words exactly, adding only pauses and sounds."
NO_NOTE = "A MiniMax voice takes no note: give it an emotion, or pause marks in its reading."


def job(script: str, voice: str = VOICE, note: str = "", emotion: str | None = None,
        reading: str = "", speed: float | None = None) -> dict:  # fmt: skip
    """The voice call. A remake's note ("quickly") goes in as a v3 delivery tag (`tag`) on
    this request only, never into the version's words, and its `speed` (pace, within
    V3_SPEED; None or 1 leaves v3's own); the voice is the Director's pick. A
    MiniMax voice reads `reading` when given (the words exactly, with pause marks and sounds
    added) in `emotion` (auto: its own choice), at `speed` (None: the emotion's own)."""
    text = check.narration_text(script)  # the Director's: what the narrator reads
    if not text:
        raise ValueError(NO_WORDS)
    if voice not in VOICES:
        raise ValueError(f"The narrator's voice is one of {', '.join(VOICES)}.")
    if voice in MINIMAX_VOICES:
        return _minimax(text, voice, note, emotion or "auto", (reading or "").strip(), speed)
    said, (low, high) = tag(note), V3_SPEED
    pace = {"speed": round(min(max(speed, low), high), 2)} if speed and speed != 1 else {}
    return {"model": MODEL, "input": {"prompt": f"[{said}] {text}" if said else text,
                                      "voice": voice, **pace}}  # fmt: skip


def tag(note: str) -> str:
    """A remake's note as the v3 audio tag it's sent as: a short delivery cue ("quickly",
    "warm, upbeat"), as ElevenLabs' examples are. A longer note, or one with a number, is
    refused (LONG_NOTE): v3 reads it aloud."""
    said = re.sub(r"[\[\]\s]+", " ", note).strip().rstrip(".")
    if len(said.split()) > TAG_WORDS or re.search(r"\d", said):
        raise ValueError(LONG_NOTE)
    return said


def speed_for(emotion: str | None, voice: str = "") -> float:
    """The speed a read starts at: its voice's own (`VOICE_SPEEDS`, else 1.1), raised as its
    emotion's was on the voice it was measured on (`SPEEDS`, at 1.1)."""
    own = VOICE_SPEEDS.get(voice, MINIMAX_SPEED)
    return round(own * SPEEDS.get(emotion or "auto", MINIMAX_SPEED) / MINIMAX_SPEED, 2)


def _minimax(text: str, voice: str, note: str, emotion: str, reading: str,
             speed: float | None = None) -> dict:  # fmt: skip
    """minimax/speech-2.8-hd's own inputs, at the batch-b test's settings (44.1 kHz, 256k)."""
    if note.strip():
        raise ValueError(NO_NOTE)
    if emotion not in EMOTIONS:
        raise ValueError(f"The voice's emotion is one of {', '.join(EMOTIONS)}.")
    pauses = [float(s) for s in MARK.findall(reading) if s]
    if reading and (plain(MARK.sub(" ", reading)) != plain(text) or re.search(r"#>\s*<#", reading)
                    or any(not 0.01 <= s <= LONGEST_PAUSE for s in pauses)):  # fmt: skip
        raise ValueError(NOT_THE_WORDS)
    return {"model": MINIMAX, "input": {
        "text": reading or text, "voice_id": voice, "emotion": emotion,
        "speed": round(min(max(speed or speed_for(emotion, voice), SLOWEST_SPEED), FASTEST), 2),
        "language_boost": "English", "english_normalization": True, "sample_rate": 44100,
        "bitrate": 256000, "audio_format": "mp3"}}  # fmt: skip


def characters(job_input: dict) -> int:
    said = job_input["input"]
    return len(said.get("prompt") or said.get("text") or "")


def delivery(job_input: dict) -> dict:
    """A MiniMax narration's emotion, reading and speed (a system voice on 2.8, or a clone on
    the model it was cloned for), to make it again the same way; else {}."""
    said = job_input.get("input") or {}
    if not str(job_input.get("model") or "").startswith("minimax-speech"):
        return {}
    return {"emotion": said.get("emotion"), "reading": said.get("text", ""),
            "speed": said.get("speed")}  # fmt: skip


def pace(heard: list[dict], gap: float = PAUSE) -> float | None:
    """Words a second while speaking, as the guides measure it: the words over the time they
    take, pauses longer than `gap` left out. None with too few words to say."""
    if len(heard) < 2:
        return None
    talking, start, end = 0.0, heard[0]["start"], heard[0]["end"]
    for w in heard[1:]:
        if w["start"] - end > gap:
            talking, start = talking + end - start, w["start"]
        end = max(end, w["end"])
    talking += end - start
    return round(len(heard) / talking, 2) if talking > 0 else None


def retimed(speed: float, heard: float, want: tuple[float, float]) -> float | None:
    """The speed that brings a narration read at `heard` words a second (at `speed`) to the
    middle of the style's range `want`, from the measurement, not a guess; None when it's
    inside the range already."""
    low, high = want
    if low <= heard <= high:
        return None
    scaled = speed * (low + high) / 2 / heard
    return round(min(max(scaled, SLOWEST_SPEED), FASTEST), 2)


def kept_pause(job_input: dict) -> float:
    """The longest quiet the trim keeps: the longest pause the reading marks, up to
    MARKED_KEEP, else KEEP."""
    said = (job_input.get("input") or {}).get("text") or ""
    return min(max([KEEP, *(float(s) for s in MARK.findall(said) if s)]), MARKED_KEEP)


def cuts(levels: list[float], keep: float = KEEP, heard=()) -> list[tuple[float, float]]:
    """The stretches to cut, in seconds: the middle of every quiet run (song_timing.quiet:
    breath and room tone) longer than `keep`, leaving half of `keep` after the sound before it
    and half before the sound after it (only the sound's side at the ends), and never inside
    a word Whisper heard, with that much to spare (`_words`: a soft or whispered word stays).
    A blip of sound up to BLIP long between quiet frames is part of the pause."""
    floor, step, found, start = song_timing.quiet(levels), song_timing.HOP, [], None
    quiet = "".join("q" if level < floor else "x" for level in levels)
    quiet = re.sub(rf"(?<=q)x{{1,{round(BLIP / step)}}}(?=q)", lambda m: "q" * len(m[0]), quiet)
    for k, still in enumerate(f"{quiet}x"):
        if still == "q":
            start = k if start is None else start
        elif start is not None:
            after = keep / 2 if start else 0.0  # the quiet kept after the word before
            before = keep / 2 if k < len(levels) else 0.0  # and before the word after
            a, b = start * step + after, k * step - before
            if b - a >= step:
                found.append((round(a, 2), round(b, 2)))
            start = None
    for s, e in _words(heard, levels):  # what's left of each cut beside every heard word
        found = [piece for a, b in found
                 for piece in ((a, min(b, s - keep / 2)), (max(a, e + keep / 2), b))
                 if piece[1] - piece[0] >= step]  # fmt: skip
    return [(round(a, 2), round(b, 2)) for a, b in found]


def _words(heard, levels: list[float]) -> list[tuple[float, float]]:
    """Each heard word's span; one with junk glued on from where its sound starts (its glued
    part spans the pause before it)."""
    return [((song_timing.sounds_from(w["start"], w["end"], levels) or w["end"])
             if song_timing.glued(w["word"]) else w["start"], w["end"]) for w in heard]  # fmt: skip


def moved(heard: list[dict], found: list[tuple[float, float]]) -> list[dict]:
    """The words' times in the trimmed narration: each moved back by what was cut before it."""

    def at(t: float) -> float:
        return round(t - sum(min(b, t) - a for a, b in found if a < t), 2)

    return [{**w, "start": at(w["start"]), "end": at(w["end"])} for w in heard]


def _levels(path: Path) -> list[float]:
    return song_timing.levels(song_timing._samples(path, song_timing.CLEAR), song_timing.CLEAR)


def trim(path: Path, out: Path, longest: float = KEEP, heard=()) -> Path | None:
    """Every pause cut down to `longest` of quiet (`cuts`), nothing with sound or a heard word
    touched; None when there's no pause to cut."""
    return _cut(path, out, cuts(_levels(path), longest, heard))


def _cut(path: Path, out: Path, found: list[tuple[float, float]]) -> Path | None:
    if not found:
        return None
    spans = zip([0.0, *(b for _, b in found)], [*(f":end={a}" for a, _ in found), ""], strict=True)
    n = len(found) + 1  # the pieces kept, cut sample-exact (atrim) and joined
    graph = [f"[0:a]asplit={n}" + "".join(f"[s{k}]" for k in range(n)),
             *(f"[s{k}]atrim=start={a}{end},asetpts=PTS-STARTPTS[k{k}]"
               for k, (a, end) in enumerate(spans)),
             "".join(f"[k{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1[out]"]  # fmt: skip
    command = ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-filter_complex",
               ";".join(graph), "-map", "[out]", str(out)]  # fmt: skip
    done = subprocess.run(command, capture_output=True, timeout=song_timing.TIMEOUT)  # noqa: S603
    if done.returncode:
        raise ValueError("The narration's file can't be read.")
    return out


def plain(text: str) -> str:
    """Letters and digits only, money and numbers one way however they're written: "$5,000"
    and "5000 dollars" both read "5000dollars"; "’" is "'"."""
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text.lower().replace("’", "'"))
    text = re.sub(r"\$\s*(\d+(?:\.\d+)?)", r"\1 dollars", text).replace("%", " percent")
    return re.sub(r"[^a-z0-9]", "", text)


def letters(heard: list[dict]) -> str:
    return plain(" ".join(w["word"] for w in heard))


# Heard but never an extra: the sounds a voice makes ("hmm" for MiniMax's "(laughs)" or
# "emm"), and Whisper's own sign-off after the last word ("Thank you.")
FILLER = {"hmm", "hm", "mm", "mmm", "uh", "um", "umm", "uhm", "ah", "ha", "haha", "oh", "emm",
          "er", "erm", "huh"}  # fmt: skip
SIGN_OFF = {"thankyou", "thanks", "thanksforwatching", "bye"}
LONG_EXTRA = 0.4  # s: one stray word heard this long is said, not misheard


def extras(text: str, heard: list[dict]) -> list[dict]:
    """Words the narration says that the script doesn't have, in phrases [{text, start,
    end}]: a note read aloud, an ad-lib. Only words heard with no script word in their place,
    compared as `plain` letters, so a word heard another way ("5000 dollars" for "$5,000") or
    split ("soft gels") isn't one. A phrase counts before the first script word (where a tag
    read aloud lands), at two words or more, or as one word lasting LONG_EXTRA; never a filler
    sound, the sign-off after the last word, or one word that came with junk glued on."""
    found = []
    for x in song_timing.extras("\n".join(sentences(text)), heard, norm=plain, added_only=True):
        said = [w for w in x["text"].split() if plain(w) not in FILLER]
        if not said or x["end"] >= heard[-1]["end"] and plain(" ".join(said)) in SIGN_OFF:
            continue
        one = x["end"] - x["start"] >= LONG_EXTRA and not song_timing.glued(said[0])
        if x["start"] <= heard[0]["start"] or len(said) >= 2 or one:
            found.append(x)
    return found


def says_more(take) -> str:
    """The first words a timed narration (a SongTake) says that the script doesn't have; ""
    for none, and for a song (its ad-libs are the director's call)."""
    found = (take.timing or {}).get("extras") or [] if take.kind == KIND else []
    return found[0]["text"] if found else ""


COVERED = song_timing.COVERED


def covered(text: str, heard: list[dict]) -> float:
    """The share of the script's words heard, in order, compared as `plain` letters."""
    return song_timing.covered("\n".join(sentences(text)), heard, norm=plain)


def measure(path: Path, text: str, hear=song_timing.words,
            longest: float = KEEP) -> tuple[dict, Path | None]:  # fmt: skip
    """The narration's timing, and the trimmed file (beside `path`; None: there was no pause
    to cut). It's heard once, as made; the trim then cuts only quiet outside every heard word
    (`cuts`), and the words' times move with the cuts. A pause up to `longest` stays (the
    reading's own marks)."""
    before, said = song_timing.length(path), hear(path, text)
    if covered(text, said) < COVERED:  # the script as Whisper's prompt can lose most of a
        again = hear(path, text, prompted=False)  # read (video 281): hear it plainly too
        said = again if covered(text, again) > covered(text, said) else said
    found = cuts(_levels(path), longest, said)
    trimmed = _cut(path, path.with_name("trimmed.mp3"), found)
    use, heard = trimmed or path, moved(said, found)
    seconds, samples = song_timing.length(use), song_timing._samples(use)
    timing = {
        "seconds": seconds, "untrimmed_seconds": before, "trimmed": trimmed is not None,
        "bpm": None, "beats": [], "sections": [], "words": heard,
        "lines": song_timing.lines("\n".join(sentences(text)), heard, seconds,
                                   levels=_levels(use)),
        "extras": extras(text, heard),
        "pace": pace(heard) if covered(text, said) >= COVERED else None,  # none: heard in part
        "peaks": song_timing.peaks(samples),
    }  # fmt: skip
    return timing, trimmed
