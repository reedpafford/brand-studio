"""Free work done on our own server (`paid = False`, so it runs even with generation off).
Today one job: `reel_prepare` (app/reel.py). Files it makes are handed to the worker as
`local://` paths, which `fetch` reads once and deletes."""

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from app import reel
from app.providers import Result

TYPES = {".mp4": "video/mp4", ".jpg": "image/jpeg"}


class LocalProvider:
    name = "local"
    paid = False
    sync = True

    def __init__(
        self,
        storage,
        transcribe: Callable[[Path], list[dict]] = reel.transcribe,
        fetch_link: Callable[[str, Path], Path] = reel.fetch,
    ):
        self.storage, self.transcribe, self.fetch_link = storage, transcribe, fetch_link
        self.root = Path(tempfile.mkdtemp(prefix="bs-local-"))

    def run(self, kind: str, input: dict) -> Result:
        if kind != "reel_prepare":
            raise ValueError(f"Unknown local job {kind!r}.")
        folder = Path(tempfile.mkdtemp(dir=self.root))
        try:
            made = self._prepare(input, folder)
            keep = set(made["files"])
            for f in folder.iterdir():  # frames, the uploaded copy: only the outputs stay
                if f"local://{f}" not in keep:
                    f.unlink()
            return Result("succeeded", **made)
        except reel.Refused as no:  # a plain reason, saved on the script; nothing to retry
            shutil.rmtree(folder, ignore_errors=True)
            return Result("succeeded", output={"problem": no.message, "problem_code": no.code})
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def _prepare(self, input: dict, folder: Path) -> dict:
        if input.get("url"):
            video = self.fetch_link(input["url"], folder)
            files, names = [video], ["video"]
        else:
            video = folder / "reel.mp4"
            video.write_bytes(self.storage.get(input["video_key"]))
            files, names = [], []
        seconds = reel.probe(video)
        cut_times = reel.cuts(video)
        files.append(reel.contact_sheet(video, cut_times, seconds, folder))
        names.append("contact")
        output = {
            "seconds": seconds,
            "cuts": cut_times,
            "stats": reel.stats(cut_times, seconds),
            "transcript": self.transcribe(video),
            "files": names,  # what each of the worker's file_ids is, in order
        }
        return {"output": output, "files": [f"local://{f}" for f in files]}

    def fetch(self, url: str) -> tuple[bytes, str]:
        path = Path(url.removeprefix("local://")).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Bad local file.")
        data = path.read_bytes()
        path.unlink()
        if not any(path.parent.iterdir()):
            path.parent.rmdir()
        return data, TYPES[path.suffix]

    def submit(self, kind: str, input: dict) -> str:  # pragma: no cover - sync only
        raise NotImplementedError

    def poll(self, ref: str) -> Result:  # pragma: no cover - sync only
        raise NotImplementedError
