"""Free work done on our own server (`paid = False`, so it runs even with generation off):
`reel_prepare` (app/reel.py), `song_timing` (app/song_timing.py), `song_study`
(app/song_study.py), `take_listen` (app/take_words.py), `cut_listen` (app/watch_cut.py) and
`cut_make` (app/cut_render.py). Files it makes are handed to the worker as `local://` paths,
which `fetch` reads once and deletes."""

import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from app import narration, reel, room, song_study, song_timing
from app.providers import Result

TYPES = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".mp3": "audio/mpeg"}


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
        hear_voice: Callable[[Path, str], list[dict]] = song_timing.words,
        hear_study: Callable[[Path, song_study.Watch], list[dict]] = song_study.hear,
        fetch_study: Callable[[str, Path], Path] = reel.fetch,
        hear_take: Callable[[Path, dict], list[dict]] = lambda path, _: reel.transcribe(path, True),
        hear_cut: Callable[[Path, dict], list[dict]] = lambda path, _: reel.transcribe(
            path, words=True
        ),
    ):
        self.storage, self.transcribe, self.fetch_link = storage, transcribe, fetch_link
        self.hear_song, self.hear_voice, self.hear_study = hear_song, hear_voice, hear_study
        self.fetch_study = fetch_study  # a song-ad study's link (the stand-ins give a clip)
        self.hear_take = hear_take  # a take's words, for its words check (app/take_words.py)
        self.hear_cut = hear_cut  # a cut's words and when, for its watch (app/watch_cut.py)
        self.root = Path(tempfile.mkdtemp(prefix="bs-local-"))

    def run(self, kind: str, input: dict) -> Result:
        if kind == "song_timing":
            return self._time_song(input)
        if kind == "narration_timing":
            return self._time_narration(input)
        if kind == "song_study":
            return self._study(input)
        if kind == "take_listen":
            return self._hear_take(input)
        if kind == "cut_listen":
            return self._hear_cut(input)
        if kind == "cut_make":
            return self._make_cut(input)
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

    def _time_narration(self, input: dict) -> Result:
        """Pauses trimmed (kept if the trim would clip a word), then each sentence timed; a
        UGC talker's (`room`) then sounds recorded in a room (app/room.py), its times kept."""
        folder = Path(tempfile.mkdtemp(dir=self.root))
        voice = folder / "narration.mp3"
        voice.write_bytes(self.storage.get(input["song_key"]))
        try:
            timing, trimmed = narration.measure(
                voice,
                input["lyrics"],
                hear=self.hear_voice,
                longest=input.get("pause", narration.PAUSE),
            )
            if input.get("room"):
                trimmed = room.finish(trimmed or voice, folder / "room.mp3")
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        voice.unlink()
        if trimmed is None:
            shutil.rmtree(folder, ignore_errors=True)
            return Result("succeeded", output={"timing": timing})
        return Result("succeeded", output={"timing": timing}, files=[f"local://{trimmed}"])

    def _hear_take(self, input: dict) -> Result:
        with tempfile.TemporaryDirectory(dir=self.root) as folder:
            take = Path(folder) / "take.mp4"
            take.write_bytes(self.storage.get(input["video_key"]))
            return Result("succeeded", output={"heard": self.hear_take(take, input)})

    def _hear_cut(self, input: dict) -> Result:
        """A cut's watch, free: its words, where each clip sits, and the frames to look at
        (app/watch_cut.py), handed over as files."""
        from app import take_frames, watch_cut

        folder = Path(tempfile.mkdtemp(dir=self.root))
        cut = folder / "cut.mp4"
        cut.write_bytes(self.storage.get(input["video_key"]))
        length = take_frames.length(cut)
        lengths = []
        for c in input["clips"]:
            seconds = c.get("seconds")
            if seconds is None:
                take = folder / f"take-{c['take_id']}.mp4"
                take.write_bytes(self.storage.get(c["key"]))
                seconds = take_frames.length(take)
                take.unlink()
            lengths.append((c["clip_id"], c["take_id"], float(seconds)))
        spans = watch_cut.spans_of(lengths, length)
        words = [{**w, "clip_id": watch_cut.clip_at(spans, w["start"])}
                 for line in self.hear_cut(cut, input) for w in line.get("words", [])]  # fmt: skip
        frames = watch_cut.frames_at(length, take_frames.cuts(cut), words, spans,
                                     watch_cut.count_for(length))  # fmt: skip
        files = []
        for n, f in enumerate(frames):
            dst = folder / f"frame-{n}.jpg"
            take_frames.grab(cut, f["t"], dst)
            files.append(f"local://{dst}")
        cut.unlink()
        return Result("succeeded", output={"spans": spans, "words": words, "frames": frames},
                      files=files)  # fmt: skip

    def _make_cut(self, input: dict) -> Result:
        """A cut (app/cut_render.py), its progress kept where the cut editor reads it. A
        known problem comes back as plain words with its fixes; anything else as a retry."""
        import logging

        from app import cut_render

        key = input["progress_key"]
        folder = Path(tempfile.mkdtemp(dir=self.root))
        try:
            data = cut_render.render(input["recipe"], self.storage,
                                     lambda n: self.storage.put(key, str(n).encode()))  # fmt: skip
        except cut_render.Problem as no:
            shutil.rmtree(folder, ignore_errors=True)
            return Result("succeeded", output={"problem": no.said, "fixes": no.fixes})
        except Exception:  # an odd file: plain words, Try again
            logging.getLogger(__name__).exception("the cut couldn't be made")
            shutil.rmtree(folder, ignore_errors=True)
            return Result("succeeded", output={"problem": "a clip's file couldn't be read. "
                                               "Redo the odd one out, or try again",
                                               "fixes": ["again"]})  # fmt: skip
        finally:
            if self.storage.exists(key):
                self.storage.delete(key)
        out = folder / "cut.mp4"
        out.write_bytes(data)
        return Result("succeeded", output={}, files=[f"local://{out}"])

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
                video = self.fetch_study(input["url"], folder)
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
