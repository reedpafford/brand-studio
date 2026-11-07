"""A song take's measured timing, free on our own server: its length, beats and bars, when
each lyric line is sung, and its sections, so the breakdown can cut B-roll to the real track.
Song ads are mostly B-roll with the song over it; lip-sync is a rare extra, so no section is
marked Sung here (the breakdown decides).

A file that can't be read raises ValueError (trying again won't help); anything else, such as
Whisper running slow, may pass on a retry.

Words come from local Whisper, prompted with the lyrics; the lyrics' own words are then lined
up with what was heard, so every line keeps its exact text. Cuts fall only on bars (else
beats), never inside a sung word."""

import json
import math
import re
import subprocess
import sys
from array import array
from difflib import SequenceMatcher
from pathlib import Path

from app.prompts import SECTION, section_name
from app.prompts.check import LIP_SYNC

RATE = 8000  # Hz: enough to hear where the beats land
HOP = 0.01  # s per energy frame
BPM = (70, 180)  # tempos we look for; ads sit near 120
BEATS_PER_BAR = 4
TIMEOUT = 180
# Whisper's read of a take: never under TIMEOUT, more for a longer take (it ran past 180 s on
# a real UGC narration while a deploy built on the same server), and tried once more on its
# own (free, local) before it's said to have failed.
PER_SECOND, MOST = 6, 900
MAX_SECONDS = 900  # far longer than any ad (the stand-ins make one past the cap)
PEAKS = 200  # waveform points for the screens


class TooLong(ValueError):
    """A take longer than any ad (trying again won't help either)."""


def _run(args: list[str], timeout: int = TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout)  # noqa: S603


def length(path: Path) -> float:
    done = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json",
                 str(path)], 30)  # fmt: skip
    seconds = float(json.loads(done.stdout or "{}").get("format", {}).get("duration") or 0)
    if seconds > MAX_SECONDS:
        raise TooLong(f"Song length {seconds} s is over {MAX_SECONDS} s.")
    if not seconds > 0:
        raise ValueError(f"Song length {seconds!r} s can't be measured.")
    return round(seconds, 2)


def _samples(path: Path) -> array:
    done = _run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE),
                 "-f", "s16le", "-"])  # fmt: skip
    if done.returncode != 0:
        raise ValueError("The song file couldn't be decoded.")
    return array("h", done.stdout[: len(done.stdout) // 2 * 2])


def peaks(samples: array, count: int = PEAKS) -> list[float]:
    """The waveform as `count` loudness peaks from 0 to 1, so a phone draws it without
    decoding the song."""
    size = max(1, math.ceil(len(samples) / count))
    tops = [max(map(abs, samples[i : i + size]), default=0) for i in range(0, len(samples), size)]
    loudest = max(tops, default=0) or 1
    return [round(x / loudest, 2) for x in tops]


def _onsets(samples: array) -> list[float]:
    """How sharply the loudness rises in each 10 ms frame (the start of a hit)."""
    hop = int(RATE * HOP)
    energy = [
        math.log1p(sum(x * x for x in samples[i : i + hop]) / hop)
        for i in range(0, len(samples) - hop, hop)
    ]
    return [0.0, *(max(0.0, b - a) for a, b in zip(energy, energy[1:], strict=False))]


def _comb(onsets: list[float], period: float, offset: float) -> float:
    total, t = 0.0, offset
    while t < len(onsets):
        total += onsets[int(t)]
        t += period
    return total


def beats(samples: array, seconds: float) -> tuple[float, list[float]]:
    """(tempo in BPM, beat times). The tempo is the steadiest pulse (leaning towards 120
    BPM, so a half or double tempo doesn't win), then the grid that lands on most hits."""
    onsets = _onsets(samples)
    if not any(onsets):
        return 0.0, []

    def score(period: float) -> float:
        lag = round(period)
        pulse = sum(a * b for a, b in zip(onsets, onsets[lag:], strict=False))
        bpm = 60 / (period * HOP)
        return pulse * math.exp(-0.5 * (math.log2(bpm / 120) / 0.9) ** 2)

    lags = range(round(60 / BPM[1] / HOP), round(60 / BPM[0] / HOP) + 1)
    best = max(lags, key=score)
    # Refine to a fraction of a frame, so the grid doesn't drift over a whole song.
    periods = [best + k / 20 for k in range(-20, 21)]
    grid = {(p, o / 2): _comb(onsets, p, o / 2) for p in periods for o in range(int(p * 2))}
    period, offset = max(grid, key=grid.get)
    step = period * HOP
    times, t = [], offset * HOP
    while t < seconds:
        times.append(round(t, 2))
        t += step
    return round(60 / step, 1), times


def read_timeout(path: Path) -> int:
    """How long Whisper may take on this file: TIMEOUT at least, PER_SECOND of its length
    more, MOST at most (a file that can't be measured gets TIMEOUT)."""
    try:
        seconds = length(path)
    except (ValueError, subprocess.TimeoutExpired):
        return TIMEOUT
    return min(MOST, max(TIMEOUT, round(PER_SECOND * seconds)))


def words(path: Path, lyrics: str) -> list[dict]:
    """Local Whisper, prompted with the lyrics: [{word, start, end}]. Tried once more on its
    own (free, on our server) when it runs out of time or fails, before it's said to fail."""
    args = [sys.executable, "-m", "app.whisper", str(path), "--words", lyrics]
    timeout, why = read_timeout(path), ""
    for _ in range(2):
        try:
            done = _run(args, timeout)
        except subprocess.TimeoutExpired:
            why = "Reading the sung words took too long."
            continue
        if done.returncode == 0:
            return json.loads(done.stdout)
        why = f"Reading the sung words failed ({done.returncode})."
    raise RuntimeError(why)


def _norm(word: str) -> str:
    return re.sub(r"[^\w']", "", word.lower())


def lines(lyrics: str, heard: list[dict], seconds: float, start: float = 0.0) -> list[dict]:
    """Each lyric line, word for word, with when it's sung: [{section, text, start, end,
    heard, times_sung}]. `heard` is the share of its words Whisper caught; lines it missed
    get times between their neighbours, so the order and the words never change.
    `times_sung` is 1 for a line sung as often as it's written (a chorus written twice and
    sung twice), 2 when the song sings it once more than written, and so on."""
    out = _written(lyrics)
    theirs = [_norm(h["word"]) for h in heard]
    times: dict[int, list[tuple[float, float]]] = {}
    ours, matcher = _matcher(out, theirs)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            h = heard[block.b + k]
            times.setdefault(ours[block.a + k][0], []).append((h["start"], h["end"]))
    for i, line in enumerate(out):
        found = times.get(i, [])
        mine = [_norm(w) for w in line["words"]]
        heard_times = sum(
            theirs[k : k + len(mine)] == mine for k in range(len(theirs) - len(mine) + 1)
        )
        written = sum(other["text"] == line["text"] for other in out)
        line["times_sung"] = max(heard_times - written + 1, 0) if heard_times else 0
        line["heard"] = round(len(found) / len(line.pop("words")), 2)
        line["start"] = min((a for a, _ in found), default=None)
        line["end"] = max((b for _, b in found), default=None)
    _fill(out, start, seconds)
    return out


def _written(lyrics: str) -> list[dict]:
    """The sung lines as written: [{section, text, words}] (no tags, no [Lip-sync] marks)."""
    out, section = [], ""
    for raw in lyrics.strip().splitlines():
        text = LIP_SYNC.sub("", raw).strip()
        if SECTION.match(raw):
            section = section_name(raw)
        elif text:
            out.append({"section": section, "text": text, "words": text.split()})
    return out


def _matcher(out: list[dict], theirs: list[str]) -> tuple[list[tuple[int, str]], SequenceMatcher]:
    """The lyric words, (line index, word), lined up with the words heard."""
    ours = [(i, _norm(w)) for i, line in enumerate(out) for w in line["words"]]
    return ours, SequenceMatcher(None, [w for _, w in ours], theirs, autojunk=False)


def extras(lyrics: str, heard: list[dict], pause: float = 1.0) -> list[dict]:
    """What the song sings that isn't in the lyrics (an ad-lib, a repeated hook, an invented
    line): [{text, start, end}], in phrases split at a pause. Heard words with no lyric word
    to line up with count; a word heard in place of a lyric word is that word misheard."""
    theirs = [_norm(h["word"]) for h in heard]
    _, matcher = _matcher(_written(lyrics), theirs)
    loose = [k for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag in ("insert", "replace")
             for k in range(j1 + (i2 - i1), j2)]  # fmt: skip
    phrases: list[dict] = []
    for n, k in enumerate(loose):
        h = heard[k]
        if n and k == loose[n - 1] + 1 and h["start"] - phrases[-1]["end"] <= pause:
            phrases[-1]["text"] += f" {h['word'].strip()}"
            phrases[-1]["end"] = h["end"]
        else:
            phrases.append({"text": h["word"].strip(), "start": h["start"], "end": h["end"]})
    return phrases


def _fill(out: list[dict], start: float, seconds: float) -> None:
    """Lines nobody heard share the time between the lines that were heard either side."""
    i = 0
    while i < len(out):
        if out[i]["start"] is not None:
            i += 1
            continue
        j = i
        while j < len(out) and out[j]["start"] is None:
            j += 1
        a = out[i - 1]["end"] if i else start
        b = out[j]["start"] if j < len(out) else seconds
        step = max(b - a, 0) / (j - i)
        for k in range(i, j):
            out[k]["start"] = round(a + step * (k - i), 2)
            out[k]["end"] = round(a + step * (k - i + 1), 2)
        i = j


def _inside_word(t: float, heard: list[dict]) -> bool:
    return any(w["start"] < t < w["end"] for w in heard)


def _snap(t: float, marks: list[float]) -> float:
    return min(marks, key=lambda m: abs(m - t)) if marks else t


def sections(sung: list[dict], beat_times: list[float], heard: list[dict], seconds: float):
    """The song's parts in order, as the lyrics tag them ([Verse], [Chorus]…), each from a
    bar line to the next, with the bar lines inside it where a B-roll shot can change (none
    inside a sung word). Untagged lyrics are one part; any music before the first line is an
    Intro, after the last an Outro."""
    bars = beat_times[::BEATS_PER_BAR]
    safe = [b for b in bars if not _inside_word(b, heard)] or [
        b for b in beat_times if not _inside_word(b, heard)
    ]
    parts: list[dict] = []
    for line in sung:
        if not parts or line["section"] != parts[-1]["name"]:
            parts.append({"name": line["section"] or "Song", "start": line["start"], "lines": []})
        parts[-1]["lines"].append(line["text"])
    if parts and parts[0]["start"] > 1:
        parts.insert(0, {"name": "Intro", "start": 0.0, "lines": []})
    if sung and seconds - sung[-1]["end"] > 2:
        parts.append({"name": "Outro", "start": sung[-1]["end"], "lines": []})
    for k, part in enumerate(parts[1:], 1):  # from the last bar line before its first word
        if not part["lines"]:  # the Outro: from the first bar line after the last word
            part["start"] = next((s for s in safe if s >= part["start"]), part["start"])
            continue
        before = [s for s in safe if parts[k - 1]["start"] < s <= part["start"] + 0.15]
        part["start"] = before[-1] if before else _snap(part["start"], safe)
    if parts:
        parts[0]["start"] = 0.0
    for part, after in zip(parts, [*parts[1:], None], strict=True):
        part["end"] = after["start"] if after else seconds
        part["cuts"] = [b for b in safe if part["start"] < b < part["end"]]
    return [p for p in parts if p["end"] > p["start"]]


def measure(path: Path, lyrics: str, hear=words) -> dict:
    """Everything the breakdown needs about one take. Free (all on our server)."""
    seconds = length(path)
    samples = _samples(path)
    bpm, beat_times = beats(samples, seconds)
    heard = hear(path, lyrics.strip())
    sung = lines(lyrics, heard, seconds, start=beat_times[0] if beat_times else 0.0)
    return {
        "seconds": seconds,
        "bpm": bpm,
        "beats": beat_times,
        "words": heard,
        "lines": sung,
        "extras": extras(lyrics, heard),
        "sections": sections(sung, beat_times, heard, seconds),
        "peaks": peaks(samples),
    }
