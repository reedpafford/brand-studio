"""Transcribe one video with faster-whisper small (int8, CPU), as JSON lines on stdout.
Run by `app.reel.transcribe` in a subprocess: `python -m app.whisper <video>`, or for a song's
words by `app.song_timing.words`: `python -m app.whisper <song> --words <lyrics>`, or for a
song ad's lines with their words by `app.song_study.hear`: `python -m app.whisper <video>
--study`, or for a take's words with its gasps and breaths by `app.take_words`: `python -m
app.whisper <take> --sounds`. The model is
downloaded once into HF_HOME (a volume on the server, `models`) and read from there with no
check against the hub. Each run says on stderr how long the model took to load and the read
took (`{"whisper": {...}}`), which song_timing and reel log, so a slow read shows where its
time went (the test site, video 240: 6 minutes for 24 s of narration)."""

import json
import os
import sys
import time

# Without VAD, whisper can invent words over music-only or silent stretches. Those come back
# as segments it thinks hold no speech and isn't sure of: whisper's own cut-offs.
NO_SPEECH = 0.6
LOW_LOGPROB = -1.0


def heard(segment) -> bool:
    """A real line, not one made up over music or silence."""
    made_up = segment.no_speech_prob > NO_SPEECH and segment.avg_logprob < LOW_LOGPROB
    return bool(segment.text.strip()) and not made_up


def _words(segment) -> list[dict]:
    return [
        {"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)}
        for w in segment.words or []
    ]


THREADS = "BS_WHISPER_THREADS"  # CPU threads for one read; else the CPUs this process may use


def threads() -> int:
    """BS_WHISPER_THREADS, else the CPUs this process may use (its affinity: a container's own
    limit, not the host's count), at most 4 (CTranslate2's own default ceiling)."""
    if (asked := os.environ.get(THREADS, "").strip()).isdigit() and int(asked) > 0:
        return int(asked)
    try:
        cpus = len(os.sched_getaffinity(0))
    except AttributeError:  # not Linux
        cpus = os.cpu_count() or 1
    return max(1, min(4, cpus))


def said(**facts) -> None:
    """One line of timings on stderr, at once (a read killed for time still shows its load)."""
    print(json.dumps({"whisper": facts}), file=sys.stderr, flush=True)


def timings(stderr: bytes | str | None) -> dict:
    """The run's own timing lines from its stderr, merged: {load_s, cached, threads,
    transcribe_s, audio_s}, as far as it got."""
    text = stderr.decode(errors="replace") if isinstance(stderr, bytes) else (stderr or "")
    out: dict = {}
    for line in text.splitlines():
        if line.startswith('{"whisper"'):
            try:
                out |= json.loads(line)["whisper"]
            except (ValueError, KeyError, TypeError):
                continue
    return out


def load():
    """The same model as ever (small, int8, CPU), from the cache with no network check; only
    when it isn't there yet, downloaded (once, into HF_HOME)."""
    from faster_whisper import WhisperModel

    kwargs = {"device": "cpu", "compute_type": "int8", "cpu_threads": threads(), "num_workers": 1}
    try:
        return WhisperModel("small", local_files_only=True, **kwargs), True
    except Exception:  # noqa: BLE001 - not in the cache yet: fetch it
        return WhisperModel("small", **kwargs), False


def main(path: str, words_prompt: str | None = None, study: bool = False,
         sounds: bool = False) -> None:  # fmt: skip
    start = time.monotonic()
    model, cached = load()
    said(load_s=round(time.monotonic() - start, 2), cached=cached, threads=threads())
    if path == "--warm":  # download and load it, nothing to transcribe
        return
    # No VAD: reels put music under every line, and VAD dropped 6 of the altar reel's 11 lines
    # `sounds`: whisper's non-speech tags ("(gasps)", "[breathing]") are kept, not suppressed.
    start = time.monotonic()
    found, info = model.transcribe(
        path, word_timestamps=True, vad_filter=False, initial_prompt=words_prompt or None,
        **({"suppress_tokens": []} if sounds else {}),
    )  # fmt: skip
    segments = list(found)  # the read itself happens here
    said(transcribe_s=round(time.monotonic() - start, 2),
         audio_s=round(getattr(info, "duration", 0) or 0, 2))  # fmt: skip
    if words_prompt is not None:  # a song: each sung word and when (app/song_timing.py)
        json.dump([w for s in segments if heard(s) for w in _words(s)], sys.stdout)
        return
    lines = [
        {
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "text": s.text.strip(),
            "speaker": None,
            **({"words": _words(s)} if study or sounds else {}),  # a take's: for a splice
        }
        for s in segments
        if heard(s)
    ]
    json.dump(lines, sys.stdout)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[3] if sys.argv[2:3] == ["--words"] else None,
         study=sys.argv[2:3] == ["--study"], sounds=sys.argv[2:3] == ["--sounds"])  # fmt: skip
