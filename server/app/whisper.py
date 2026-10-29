"""Transcribe one video with faster-whisper small (int8, CPU), as JSON lines on stdout.
Run by `app.reel.transcribe` in a subprocess: `python -m app.whisper <video>`, or for a song's
words by `app.song_timing.words`: `python -m app.whisper <song> --words <lyrics>`, or for a
song ad's lines with their words by `app.song_study.hear`: `python -m app.whisper <video>
--study`. The model is
downloaded once into HF_HOME (a volume on the server)."""

import json
import sys

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


def main(path: str, words_prompt: str | None = None, study: bool = False) -> None:
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8")
    if path == "--warm":  # download and load it, nothing to transcribe
        return
    # No VAD: reels put music under every line, and VAD dropped 6 of the altar reel's 11 lines
    segments, _ = model.transcribe(
        path, word_timestamps=True, vad_filter=False, initial_prompt=words_prompt
    )
    if words_prompt is not None:  # a song: each sung word and when (app/song_timing.py)
        json.dump([w for s in segments if heard(s) for w in _words(s)], sys.stdout)
        return
    lines = [
        {
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "text": s.text.strip(),
            "speaker": None,
            **({"words": _words(s)} if study else {}),
        }
        for s in segments
        if heard(s)
    ]
    json.dump(lines, sys.stdout)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[3] if sys.argv[2:3] == ["--words"] else None,
         study=sys.argv[2:3] == ["--study"])  # fmt: skip
