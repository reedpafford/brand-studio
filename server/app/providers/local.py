"""Free work done on our own server (`paid = False`, so it runs even with generation off):
`reel_prepare` (app/reel.py), `song_timing` (app/song_timing.py) and `song_study`
(app/song_study.py). Files it makes are handed to the worker as `local://` paths, which
`fetch` reads once and deletes."""

import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from app import reel, song_study, song_timing
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
        hear_song: Callable[[Path, str], list[dict]] = song_timing.words,
        hear_study: Callable[[Path, song_study.Watch], list[dict]] = song_study.hear,
    ):
        self.storage, self.transcribe, self.fetch_link = storage, transcribe, fetch_link
        self.hear_song, self.hear_study = hear_song, hear_study
        self.root = Path(tempfile.mkdtemp(prefix="bs-local-"))

    def run(self, kind: str, input: dict) -> Result:
        if kind == "song_timing":
            return self._time_song(input)
        if kind == "song_study":
            return self._study(input)
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
            if input.get("video_key"):  # an upload we can't read: don't keep it
                self.storage.delete(input["video_key"])
            return Result("succeeded", output={"problem": no.message, "problem_code": no.code})
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def _time_song(self, input: dict) -> Result:
        with tempfile.TemporaryDirectory(dir=self.root) as folder:
            song = Path(folder) / "song.mp3"
            song.write_bytes(self.storage.get(input["song_key"]))
            hear = (lambda path, lyrics: []) if input.get("spread") else self.hear_song
            timing = song_timing.measure(song, input["lyrics"], hear=hear)
        return Result("succeeded", output={"timing": timing})

    def _study(self, input: dict) -> Result:
        """A song ad's study and its frames; a plain reason when it can't be read. An
        uploaded video is deleted either way: only the study and its frames are kept."""
        folder = Path(tempfile.mkdtemp(dir=self.root))
        marker = song_study.stop_key(input.get("job_id", 0))
        until = time.monotonic() + song_study.LIMIT
        watch = song_study.Watch(lambda: self.storage.exists(marker), until)
        try:
            video = folder / "reel.mp4"
            if input.get("url"):
                video = self.fetch_link(input["url"], folder)
            else:
                video.write_bytes(self.storage.get(input["video_key"]))
            found, frames = song_study.study(video, folder, hear=self.hear_study, watch=watch)
        except reel.Refused as no:
            shutil.rmtree(folder, ignore_errors=True)
            return Result("succeeded", output={"problem": no.message, "problem_code": no.code})
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        finally:
            self.storage.delete(marker)
            if input.get("video_key"):
                self.storage.delete(input["video_key"])
        for f in folder.iterdir():  # the video and anything else: only the frames stay
            if f not in {p for p, _ in frames}:
                f.unlink()
        output = {**found, "frame_times": [t for _, t in frames]}
        return Result("succeeded", output=output, files=[f"local://{p}" for p, _ in frames])

    def _prepare(self, input: dict, folder: Path) -> dict:
        if input.get("url"):
            video = self.fetch_link(input["url"], folder)
            files, names = [video], ["video"]
            said = reel.caption(folder)
        else:
            video = folder / "reel.mp4"
            video.write_bytes(self.storage.get(input["video_key"]))
            files, names, said = [], [], ""
        seconds = reel.probe(video)
        cut_times = reel.cuts(video)
        files.append(reel.contact_sheet(video, cut_times, seconds, folder))
        files.append(reel.watch_copy(video, folder))  # what Gemini gets: small enough for it
        grids = reel.frame_grids(video, cut_times, seconds, folder)  # if video won't go through
        files += grids
        names += ["contact", "watch", *(["grid"] * len(grids))]
        output = {
            "seconds": seconds,
            "cuts": cut_times,
            "stats": reel.stats(cut_times, seconds),
            "transcript": self.transcribe(video),
            "caption": said,
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
