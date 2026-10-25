"""Transcribe one video with faster-whisper small (int8, CPU), as JSON lines on stdout.
Run by `app.reel.transcribe` in a subprocess: `python -m app.whisper <video>`. The model is
downloaded once into HF_HOME (a volume on the server)."""

import json
import sys


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
        if s.text.strip()
    ]
    json.dump(lines, sys.stdout)


if __name__ == "__main__":
    main(sys.argv[1])
