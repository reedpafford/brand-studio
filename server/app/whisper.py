"""Transcribe one video with faster-whisper small (int8, CPU), as JSON lines on stdout.
Run by `app.reel.transcribe` in a subprocess: `python -m app.whisper <video>`. The model is
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


def main(path: str) -> None:
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8")
    if path == "--warm":  # download and load it, nothing to transcribe
        return
    # No VAD: reels put music under every line, and VAD dropped 6 of the altar reel's 11 lines
    segments, _ = model.transcribe(path, word_timestamps=True, vad_filter=False)
    lines = [
        {
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "text": s.text.strip(),
            "speaker": None,
        }
        for s in segments
        if heard(s)
    ]
    json.dump(lines, sys.stdout)


if __name__ == "__main__":
    main(sys.argv[1])
