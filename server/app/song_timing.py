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
import logging
import math
import re
import subprocess
import sys
import time
from array import array
from difflib import SequenceMatcher
from pathlib import Path

from app.prompts import SECTION, section_name
from app.prompts.check import LIP_SYNC

log = logging.getLogger(__name__)

RATE = 8000  # Hz: enough to hear where the beats land
CLEAR = 24000  # Hz: enough to hear an "s" or an "f" at a word's edge as sound
HOP = 0.01  # s per energy frame
BPM = (70, 180)  # tempos we look for; ads sit near 120
BEATS_PER_BAR = 4
TIMEOUT = 180
# Whisper's read of a take: never under FLOOR, more for a longer take (it ran past 180 s on
# a real UGC narration while a deploy built on the same server, and a 23 s read took 175 s on
# the test site). One try a job: the local lane is one worker every cut and listen shares; a
# failed read is read again as its own job (song_takes.time_again). A read that uses over
# NEAR of its time logs a warning, so the trend shows before one runs out.
FLOOR, PER_SECOND, MOST, NEAR = 300, 6, 1800, 0.75  # MOST: a 5-minute cut (long scripts)
MAX_SECONDS = 900  # far longer than any ad (the stand-ins make one past the cap)
PEAKS = 200  # waveform points for the screens
# Quiet: this far under a voice's own loud level (its 95th-percentile 10 ms frame). In video
# 261's narration the breaths and room tone in its pauses sat 31-43 dB under it and the words'
# fading ends 13-22 dB under it.
QUIET_DB = 28


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


def _samples(path: Path, rate: int = RATE) -> array:
    done = _run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(rate),
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


def levels(samples: array, rate: int = RATE) -> list[float]:
    """The loudness of each HOP frame, in dB under full scale."""
    hop = int(rate * HOP)
    return [10 * math.log10(sum(x * x for x in samples[i : i + hop]) / hop / 32768**2 + 1e-12)
            for i in range(0, len(samples) - hop + 1, hop)]  # fmt: skip


def quiet(loudness: list[float]) -> float:
    """The level under which a frame is quiet: QUIET_DB under the loud frames."""
    ranked = sorted(loudness)
    return ranked[int(0.95 * (len(ranked) - 1))] - QUIET_DB if ranked else 0.0


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
    """How long Whisper may take on this file: FLOOR at least, PER_SECOND of its length
    more, MOST at most (a file that can't be measured gets FLOOR)."""
    try:
        seconds = length(path)
    except (ValueError, subprocess.TimeoutExpired):
        return FLOOR
    return min(MOST, max(FLOOR, round(PER_SECOND * seconds)))


def words(path: Path, lyrics: str, prompted: bool = True) -> list[dict]:
    """Local Whisper, prompted with the lyrics (unless `prompted` is False): [{word, start,
    end}], in the time the take's length gives it (`read_timeout`)."""
    from app.whisper import timings

    args = [sys.executable, "-m", "app.whisper", str(path), "--words", lyrics if prompted else ""]
    allowed, began = read_timeout(path), time.monotonic()
    try:
        done = _run(args, allowed)
    except subprocess.TimeoutExpired as late:  # where the time went: the load, or the read
        log.warning("whisper timing read ran out of %s s: %s", allowed, timings(late.stderr))
        raise RuntimeError("Reading the sung words took too long.") from None
    took = time.monotonic() - began
    near = log.warning if took > NEAR * allowed else log.info  # close to running out
    near("whisper timing read: %s (took %.0f of %s s)", timings(done.stderr), took, allowed)
    if done.returncode != 0:
        raise RuntimeError(f"Reading the sung words failed ({done.returncode}).")
    return json.loads(done.stdout)


def _norm(word: str) -> str:
    """A word as it's compared: letters, digits and apostrophes only. Whisper glues stray
    characters onto a sentence's first word ("?ÿÿÿÿDay", ".שובDay"), which `\\w` kept."""
    return re.sub(r"[^a-z0-9']", "", word.lower().replace("’", "'"))


def glued(word: str) -> bool:
    """Whisper glued junk onto this heard word: a stray character ("?ÿÿÿÿDay", ".שובDay",
    ".ManiaResilia"), beyond the punctuation around a word, in a number or an abbreviation
    ("U.S.", "e.g."); a name with a capital inside ("iPhone", "McDonald's") is a word."""
    core = re.sub(r"(?<=\d)[.,](?=\d)|(?<=\b[A-Za-z])\.(?=[A-Za-z]\b)", "", word.strip())
    core = core.strip("\"“”‘’'()[]¡¿$%").rstrip(".,!?;:…-")
    return bool(re.search(r"[^A-Za-z0-9'’-]", core))


def _capital(word: str, known: set[str], norm=_norm) -> bool:
    """Junk glued on in letters: a heard word the lyrics don't have whose part from its last
    inner capital on is one they do ("iPhDanny" for "Danny", video 281). A name ("iPhone",
    "TikTok") is only one when the lyrics have its tail but not it."""
    tail = re.search(r"[a-z]([A-Z][a-z']*)\W*$", word.strip())
    return bool(tail) and norm(word) not in known and norm(tail[1]) in known


def _ending(word: str, known: set[str]) -> str:
    """A heard word with junk glued on that the lyrics don't have, ending with one they do
    (".ManiaResilia" in video 261), is that word; it stays as it is otherwise."""
    if word in known:
        return word
    return max((w for w in known if len(w) >= 3 and word.endswith(w)), key=len, default=word)


REACH = 0.15  # s: how much earlier than Whisper's start a word's own sound may begin


def sounds_from(start: float, end: float, loudness: list[float]) -> float | None:
    """Where a word heard with junk glued on really starts: where the sound rises inside it,
    past any tail of the word before (it starts too early, in the pause before it); None
    when nothing inside it is loud."""
    floor, k, last = quiet(loudness), round(start / HOP), min(round(end / HOP), len(loudness))
    while 0 < k < last and loudness[k - 1] >= floor and loudness[k] >= floor:
        k += 1  # the word before still sounding
    k = next((n for n in range(k, last) if loudness[n] >= floor), None)
    return round(max(start, k * HOP), 2) if k is not None else None


def _start(found: list[tuple], loudness: list[float] | None) -> float | None:
    """When a line starts: its first heard word's start. With the take's loudness, a word
    with junk glued on starts where its sound rises inside it (`sounds_from`); any other where
    its sound began, up to REACH before Whisper's start, never before the word heard before
    it ends (Whisper often starts a word a little late, inside its first sound)."""
    if not found:
        return None
    a, b, junk, after = min(found)
    if not loudness:
        return a
    if junk:
        return sounds_from(a, b, loudness) or a
    floor = quiet(loudness)

    def loud(k: int) -> bool:
        return 0 <= k < len(loudness) and loudness[k] >= floor

    first, last = round(max(after, a - REACH) / HOP), round(a / HOP)
    k = next((n for n in range(first, last + 1) if loud(n) and not loud(n - 1)), None)
    return round(k * HOP, 2) if k is not None else a


def lines(lyrics: str, heard: list[dict], seconds: float, start: float = 0.0,
          levels: list[float] | None = None) -> list[dict]:  # fmt: skip
    """Each lyric line, word for word, with when it's sung: [{section, text, start, end,
    heard, times_sung}]. `heard` is the share of its words Whisper caught; lines it missed
    get times between their neighbours, so the order and the words never change.
    `times_sung` is 1 for a line sung as often as it's written (a chorus written twice and
    sung twice), 2 when the song sings it once more than written, and so on. With the take's
    `levels`, a line starts where its first word's sound does (`_start`)."""
    out = _written(lyrics)
    times: dict[int, list[tuple]] = {}
    ours, theirs, junk, matcher = _matcher(out, heard)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            j = block.b + k
            after = heard[j - 1]["end"] if j else 0.0  # the word heard before it ends
            found = (heard[j]["start"], heard[j]["end"], junk[j], after)
            times.setdefault(ours[block.a + k][0], []).append(found)
    for i, line in enumerate(out):
        found = times.get(i, [])
        mine = [_norm(w) for w in line["words"]]
        heard_times = sum(
            theirs[k : k + len(mine)] == mine for k in range(len(theirs) - len(mine) + 1)
        )
        written = sum(other["text"] == line["text"] for other in out)
        line["times_sung"] = max(heard_times - written + 1, 0) if heard_times else 0
        line["heard"] = round(len(found) / len(line.pop("words")), 2)
        line["start"] = _start(found, levels)
        line["end"] = max((x[1] for x in found), default=None)
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


def _matcher(out: list[dict], heard: list[dict], norm=_norm):
    """The lyric words, (line index, word), the heard words (`_ending`), which of them came
    with junk glued on, and the two lined up."""
    ours = [(i, norm(w)) for i, line in enumerate(out) for w in line["words"]]
    known = {w for _, w in ours}
    junk = [glued(h["word"]) or _capital(h["word"], known, norm) for h in heard]
    theirs = [_ending(norm(h["word"]), known) if j else norm(h["word"])
              for h, j in zip(heard, junk, strict=True)]  # fmt: skip
    matcher = SequenceMatcher(None, [w for _, w in ours], theirs, autojunk=False)
    return ours, theirs, junk, matcher


def extras(lyrics: str, heard: list[dict], pause: float = 1.0, norm=_norm,
           added_only: bool = False) -> list[dict]:  # fmt: skip
    """What the song sings that isn't in the lyrics (an ad-lib, a repeated hook, an invented
    line): [{text, start, end}], in phrases split at a pause. Heard words with no lyric word
    to line up with count; a word heard in place of a lyric word is that word misheard.
    `added_only`: of several words heard in place of fewer, none count (a narration's)."""
    _, theirs, _, matcher = _matcher(_written(lyrics), heard, norm)
    loose = [k for tag, i1, i2, j1, j2 in matcher.get_opcodes()
             if tag == "insert" or tag == "replace" and not added_only
             for k in range(j1 + (i2 - i1), j2) if theirs[k]]  # fmt: skip
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


# The share of the words a read must have, in order, to count as all heard: Whisper writes a
# few another way ("10" for "ten", "Everything's giving" for "Every Thanksgiving", video 281)
COVERED = 0.9


def covered(lyrics: str, heard: list[dict], norm=_norm) -> float:
    """The share of the lyrics' words heard, in order (junk glued on taken off)."""
    ours, _, _, matcher = _matcher(_written(lyrics), heard, norm)
    said = sum(1 for _, w in ours if w)
    found = sum(1 for b in matcher.get_matching_blocks() for k in range(b.size) if ours[b.a + k][1])
    return round(min(found / said, 1.0), 3) if said else 1.0


def measure(path: Path, lyrics: str, hear=words) -> dict:
    """Everything the breakdown needs about one take. Free (all on our server)."""
    seconds = length(path)
    samples = _samples(path)
    bpm, beat_times = beats(samples, seconds)
    heard = hear(path, lyrics.strip())
    if (
        covered(lyrics, heard) < COVERED
    ):  # an empty read too (lyrics with no words: 1.0)  # the lyrics as Whisper's prompt can lose
        again = hear(path, lyrics.strip(), prompted=False)  # most of a read: hear it plainly
        heard = again if covered(lyrics, again) > covered(lyrics, heard) else heard
    sung = lines(
        lyrics, heard, seconds, start=beat_times[0] if beat_times else 0.0, levels=levels(samples)
    )
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
