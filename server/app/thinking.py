"""What a Claude step is thinking and writing while it runs (Reed, 11 Nov: "could you have it
display the thinking like higgsfield does?"). The worker hears the call's stream and keeps a
small file up to date; the API reads it for the video's page. Both mount the files folder, so
nothing goes through the database and no job waits on it. Best effort throughout: a file
that can't be written or read is skipped, never an error, and the file goes when the call
ends."""

import json
import logging
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)
STEPS = {"one_pass"}  # the steps shown live: the one long quiet call of a new video
EVERY = 1.0  # seconds between writes
TAIL = 4000  # characters of thinking kept: the page shows its last lines
_STRING = r'"((?:[^"\\]|\\.)*)"'
_FIELD = {name: re.compile(rf'"{name}"\s*:\s*{_STRING}') for name in ("hook", "logline")}
_CLIP = re.compile(rf'"id"\s*:\s*"c\d+"\s*,\s*"name"\s*:\s*{_STRING}')


def _path(job_id: int) -> Path:
    from app.settings import get_settings

    return Path(get_settings().storage_dir) / "thinking" / f"{job_id}.json"


def _said(raw: str) -> str:
    try:
        return str(json.loads(f'"{raw}"')).strip()
    except ValueError:
        return ""


def written(text: str) -> list[str]:
    """The plan so far, from its unfinished JSON: the hook and the story once each is whole,
    then each clip by its name as it is begun. Nothing it can't read is guessed."""
    lines = []
    for label, name in (("Hook", "hook"), ("Story", "logline")):
        if (m := _FIELD[name].search(text)) and (said := _said(m[1])):
            lines.append(f"{label}: {said}")
    for n, m in enumerate(_CLIP.finditer(text), 1):
        if said := _said(m[1]):
            lines.append(f"Clip {n}: {said}")
    return lines


class Writer:
    """Called with each piece of a call's stream ("thinking" or "text", and its words)."""

    def __init__(self, job_id: int):
        self._path, self._thinking, self._text, self._at = _path(job_id), "", "", 0.0

    def __call__(self, kind: str, words: str) -> None:
        if kind == "thinking":
            self._thinking = (self._thinking + words)[-TAIL:]
        else:
            self._text += words
        if time.monotonic() - self._at >= EVERY:
            self._at = time.monotonic()
            self._write()

    def _write(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            part = self._path.with_suffix(".part")
            part.write_text(json.dumps({"thinking": self._thinking,
                                        "written": written(self._text)}))  # fmt: skip
            part.replace(self._path)  # whole or not at all: a reader never sees half a file
        except OSError:
            log.warning("thinking: couldn't write %s", self._path, exc_info=True)

    def close(self) -> None:
        for path in (self._path, self._path.with_suffix(".part")):
            path.unlink(missing_ok=True)


def read(job_id: int) -> dict | None:
    """{"thinking", "written"} for a call that is running and has said something; else None."""
    try:
        data = json.loads(_path(job_id).read_text())
    except (OSError, ValueError):
        return None
    return {"thinking": str(data.get("thinking", "")), "written": list(data.get("written", []))}
