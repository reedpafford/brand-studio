"""Making a cut (free: ffmpeg on our own server, the worker's local lane; app/cut.py says
what). `recipe` turns the cut's timeline into files and settings at the press, so `render`
needs no database: each take with what's laid over it (real images cut in, words spliced,
stretches muted, sound effects), then the pieces joined (a story video's back to back with
their own sound; a narrated or song video's on the voice's clock, a short take slowed to fill
its piece, never sped up), the music under the voice by the amount set, rising when no one
speaks or staying down, and the presenter over the B-roll per span. A known problem (music
that stops before the cut ends) comes back as plain words with its one-click fixes."""

import contextvars
import logging
import math
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app import (
    cut_captions,
    cut_in,
    host,
    host_layer,
    narration,
    screen_figures,
    take_mute,
    take_sound,
    talker,
    talker_sound,
    word_splice,
)
from app.models.clips import ClipTake, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.projects import Project

log = logging.getLogger(__name__)
FADE = 1.5  # seconds: a song video's end fades out (flows V6)
HELD_FADE = 0.5  # seconds: a held end fades only at its very end
# A narrated video's mix (flows V6n): the takes' own sound under the narration, the music
# lower still, the whole about -14 LUFS
TAKES, MUSIC, LOUD = 0.75, 0.30, "loudnorm=I=-14:TP=-1.5:LRA=11"
# Under a talker's own voice (UGC: one close phone voice in one room), B-roll's own sound sits
# 20 dB lower again: 293's dinner chatter played 7-12 dB under the voice, a narrator over a
# party; the references' other sound is about 39 dB under. Sound effects a person added keep TAKES.
UNDER_TALKER = 0.075
AIM = "loudnorm=I=-14:TP=-1.5:LRA=20"  # every cut, last (E2E 233); TP as LOUD: AAC overshoots
CEILING = -1.0  # dBTP a delivered cut's sound never passes, measured after the encode
RAMP = 0.25  # seconds the music takes to dip under the voice and rise after it
SAME = "aformat=sample_rates=44100:channel_layouts=stereo"
LATE = "aresample=async=1:first_pts=0,"  # a take's sound that starts late keeps its place
SHORT_MUSIC = "the music file stops at {}, and the cut runs to {}"
# Seconds an ffmpeg pass over the whole cut may take: a 1,000-word script's cut runs 5 minutes,
# 3-5x a short ad's, so its re-encodes get 3x the old 600 s on the shared server (long scripts).
# A cut that ran out of time is made once more with `slower` set to LONGER (providers/local.py,
# FABLE B7): 1.5x, so a retry never holds the one local worker for an hour a stage.
WHOLE, LONGER = 1800, 1.5
slower = contextvars.ContextVar("slower", default=1)


def _limit() -> float:
    return WHOLE * slower.get()


class Problem(Exception):
    """A cut that can't be made, in plain words, and the fixes that make it (cut.FIXES)."""

    def __init__(self, said: str, fixes: list[str]):
        super().__init__(said)
        self.said, self.fixes = said, fixes


def _key(db: Session, file_id: int) -> str:
    return db.get(StoredFile, file_id).key


def _source(db: Session, project: Project, take_id: int) -> dict:
    """One take and what's laid over it in this video's cut."""
    take = db.get(ClipTake, take_id)
    row = db.get(ProjectClip, take.clip_id)
    ours = row.project_id == project.id
    inserts = [{"key": _key(db, i.file_id), "figure": i.figure, "start": i.start, "end": i.end}
               for i in (cut_in.inserts(db, project, row) if ours else []) if i.on]  # fmt: skip
    splices = word_splice.spliced(take)
    sound = take_sound.added(take)
    voice = (take.made_with or {}).get(talker_sound.KEY)  # an Omni talker's, from its room
    return {"key": _key(db, take.file_id), "inserts": inserts, "planned": row.seconds,
            "voice": _key(db, voice) if voice else None,
            "splices": splices,
            "from_keys": {str(s["from_take"]): _key(db, db.get(ClipTake, s["from_take"]).file_id)
                          for s in splices},
            "mutes": take_mute.spans(take),
            "sound": {"key": _key(db, sound["file_id"]), "level": take_sound.loudness(sound)}
            if sound else None}  # fmt: skip


def _reshaped(db: Session, project: Project, tl: dict) -> str | None:
    """The video's shape, when a take in the cut was made in another one (Omni 1.2 makes only
    9:16 and 16:9: a 1:1 video's takes are made 9:16, `model_map.nearest`), so the cut crops
    each piece to it; None when every take was asked for in the video's own shape."""
    for take_id in {p["take_id"] for p in tl["pieces"] if p.get("take_id")}:
        take = db.get(ClipTake, take_id)
        job = db.get(Job, take.job_id) if take and take.job_id else None
        asked = ((job.input or {}).get("input") or {}).get("aspect_ratio") if job else None
        if asked and asked != project.aspect_ratio:
            return project.aspect_ratio
    return None


def recipe(db: Session, project: Project, tl: dict) -> dict:
    """What `render` makes, as files and numbers."""
    from app.cut import laid_over, song

    voice = song(db, project)
    music = tl["music"] if tl["music"] and not tl["music"]["removed"] else None
    out = {"mode": tl["mode"], "length": tl["length"],
           "pieces": [{"take_id": p["take_id"], "from": p["from"], "whole": p["whole"],
                       "length": round(p["end"] - p["start"], 2), "card": p.get("card")}
                      for p in tl["pieces"]],
           "sources": {str(t): _source(db, project, t) for t in dict.fromkeys(
               p["take_id"] for p in tl["pieces"] if not p.get("card"))},
           "titles": [{"start": p["start"], "words": t["words"]} for t in tl.get("titles") or []
                      for p in tl["pieces"] if p["id"] == t["piece"]],
           "voice": _key(db, voice.file_id) if voice else None,
           "last_word": tl.get("last_word") or 0.0, "aspect": _reshaped(db, project, tl),
           "music": {**{k: music[k] for k in ("quieter_db", "gaps", "loop")},
                     "key": _key(db, music["file_id"]),
                     "lines": tl.get("lines") or []} if music else None,
           "host": None, "captions": cut_captions.for_cut(db, tl) if tl.get("captions") else [],
           "over": [{"key": _key(db, db.get(ClipTake, o["take_id"]).file_id), "start": o["start"],
                     "length": o["length"]} for o in laid_over(tl)]}  # fmt: skip
    if tl.get("speed"):  # an Omni talker's: each take's voice evened, one room, faster
        out["steady"] = True
        for take_id, src in out["sources"].items():
            src["even"] = True
            if not src["voice"]:  # never separated (failed, or given up on): its own sound
                log.info("cut of video %s: take %s plays its own sound", project.id, take_id)
    if talker.on(db, project):  # the talker's room carries the video
        out["takes"] = [TAKES if out["sources"][str(p["take_id"])]["sound"] else UNDER_TALKER
                        for p in tl["pieces"]]  # fmt: skip
    if tl["presenter"] and any(not s["hidden"] for s in tl["presenter"]["spans"]):
        from app.cut import SIZES

        out["host"] = {"keys": [_key(db, r.file_id) for r in host.rows(db, project)[1:]],
                       "spans": [{**{k: s[k] for k in ("start", "end", "side", "hidden")},
                                  "height": SIZES[s["size"]]}
                                 for s in tl["presenter"]["spans"]]}  # fmt: skip
    return out


def _prepare(src: dict, storage) -> tuple[bytes, bool]:
    """The take with what's laid over it; and whether anything was."""
    video = storage.get(src["key"])
    if src.get("even"):  # an Omni talker's take: its voice alone, at the one speech loudness
        video = talker_sound.even(video, storage.get(src["voice"]) if src["voice"] else None)
    cuts = [(screen_figures.draw(storage.get(i["key"]), i["figure"]), i["start"], i["end"])
            for i in src["inserts"]]  # fmt: skip
    video = cut_in.apply(video, cuts, src["planned"]) if cuts else video
    video = word_splice.apply(
        video, src["splices"], lambda take_id: storage.get(src["from_keys"][str(take_id)])
    )
    video = take_mute.apply(video, src["mutes"])
    if src["sound"]:
        video = take_sound.apply(video, storage.get(src["sound"]["key"]), src["sound"]["level"])
    return video, bool(cuts or src["splices"] or src["mutes"] or src["sound"])


def render(r: dict, storage, progress=lambda percent: None) -> bytes:
    """The cut as an MP4. `progress(percent)` hears how far it got."""
    made, laid = {}, False
    for n, (take_id, src) in enumerate(r["sources"].items(), 1):
        made[take_id], over = _prepare(src, storage)
        laid = laid or over
        progress(round(60 * n / len(r["sources"])))
    pieces = r["pieces"]
    cards = any(p.get("card") for p in pieces)  # each on black, the size of the cut's takes
    videos = [cut_captions.card_clip(p["card"], next(iter(made.values())), p["length"])
              if p.get("card") else made[str(p["take_id"])] for p in pieces]  # fmt: skip
    laid = laid or cards
    shape = r.get("aspect")  # the video's own shape: a take made in another is cropped to it
    if r["mode"] == "takes" and all(p["whole"] and not p["from"] for p in pieces):
        # As made: copied when every take is the same format, else joined with each take's
        # own sound (a silent one, or one with no audio track, gets silence; no drift).
        copy = not laid and _shaped(videos[0], shape) and stitch(videos)
        data = copy or joined(videos, [(0.0, None)] * len(videos), shape)
    elif r["mode"] == "takes":
        data = joined(videos, [(p["from"], None if p["whole"] else p["length"]) for p in pieces],
                      shape)  # fmt: skip
    if r.get("over"):  # an Omni talker's B-roll, over their picture while they talk
        data = cut_away([(storage.get(o["key"]), o["start"], o["length"]) for o in r["over"]],
                        data)  # fmt: skip
    music = r["music"]
    bed = storage.get(music["key"]) if music else None
    if music and not music["loop"] and (have := seconds(bed)) < r["length"] - 0.5:
        raise Problem(SHORT_MUSIC.format(_tc(have), _tc(r["length"])),
                      ["loop_music", "remove_music"])  # fmt: skip
    if r["mode"] == "takes":
        if bed is not None:  # a dialogue cut's bed, under its takes' own sound
            data = bedded(data, bed, {**music, "last_word": r.get("last_word") or 0})
    else:
        data = song_cut(
            videos,
            [p["length"] for p in pieces],
            storage.get(r["voice"]),
            r["mode"] == "narrated",
            bed,
            [p["from"] for p in pieces],
            {**(music or {}), "last_word": r.get("last_word") or 0, "takes": r.get("takes")},
            shape,
        )
    progress(85)
    if r["host"]:
        hosts = [storage.get(k) for k in r["host"]["keys"]]
        data = host_layer.lay_over(data, hosts, r["host"]["spans"])
    data = cut_captions.burn(data, r.get("captions") or [], tuple(r.get("titles") or ()))
    # every kind of cut, as loud as social video plays (E2E 233: -25 LUFS); an Omni talker's
    # by one fixed gain, never loudnorm's dynamic mode, with its room and its speed
    data = talker_sound.finish(data) if r.get("steady") else loud(data)
    progress(100)
    return data


XFADE = 0.04  # seconds each repeat of a looped bed crossfades into the next (no click)


def looped(folder: Path, name: str, total: float) -> str:
    """The music file `name` in `folder` repeated to at least `total` seconds, each repeat
    crossfading into the next over XFADE (QA on #1415: a plain `-stream_loop` jumped about 9x
    the normal sample step at the seam, an audible click), as a new WAV in `folder`; `name`
    itself when it's already long enough or can't be read."""
    have = _length(folder, name)
    if have <= 2 * XFADE or have >= total:
        return name
    n = max(2, math.ceil((total - XFADE) / (have - XFADE)) + 1)
    parts = [f"[0:a]{SAME},asplit={n}" + "".join(f"[s{i}]" for i in range(n))]
    last = "s0"
    for i in range(1, n):
        parts.append(f"[{last}][s{i}]acrossfade=d={XFADE}:c1=tri:c2=tri[x{i}]")
        last = f"x{i}"
    done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", name, "-filter_complex",  # noqa: S603, S607
                           ";".join(parts), "-map", f"[{last}]", "-t", f"{total + 0.1:.3f}",
                           "-c:a", "pcm_s16le", "looped.wav"],
                          cwd=folder, capture_output=True, timeout=_limit())  # fmt: skip
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
    return "looped.wav"


def bedded(data: bytes, bed: bytes, mix: dict) -> bytes:
    """A dialogue cut with a music bed under it (the House refs: a bed under every second):
    the takes' own sound as it is, the bed at its level (`level`: `quieter_db` under the
    lines, rising between them when it rises), looped when it's shorter, faded at the end;
    the picture copied, as long as the cut. `loud` then brings the whole cut to its level."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "cut.mp4").write_bytes(data)
        (folder / "music").write_bytes(bed)
        total = _length(folder, "cut.mp4")  # the cut as joined: the bed runs exactly as long
        bed_file = looped(folder, "music", total) if mix.get("loop", True) else "music"
        fade = fade_out(total, mix.get("last_word") or 0)
        graph = (f"[0:a]{SAME},apad=whole_dur={total}[takes];"
                 f"[1:a]{SAME},atrim=duration={total},apad=whole_dur={total},{level(mix)},"
                 f"afade=t=out:{fade}[under];"
                 "[takes][under]amix=inputs=2:normalize=0:duration=first[a]")  # fmt: skip
        return _run(folder, ["-i", "cut.mp4", "-i", bed_file, "-filter_complex", graph,
                             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                             "-t", str(total), "-movflags", "+faststart"])  # fmt: skip


def loud(data: bytes) -> bytes:
    """The cut at about -14 LUFS with its true peak at most -1 dBTP: loudnorm measured, then
    applied; as one gain (`linear`) when the cut allows, so the voice, the music and the sound
    keep their balance, else loudnorm's own gentle dynamic mode (a quiet voice needing about
    12 dB, say). The AAC encode can overshoot a transient past the ceiling: measured again,
    such a cut is brought down under it. The picture is copied. A cut with no sound, or only
    silence, or one ffmpeg can't measure (logged), is as it was."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(data)
        if not _probe(folder, "in.mp4", "a:0", "index"):
            return data
        m = _loudness(folder, "in.mp4")
        if m is None or m["input_i"] in ("-inf", "inf") or float(m["input_i"]) < -70:
            return data  # silence, or no report: nothing to bring up
        keep = ":".join(f"measured_{k}={m[f'input_{k.lower()}']}" for k in ("I", "TP", "LRA"))
        aim = f"{AIM}:{keep}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}"
        (folder / "loud.mp4").write_bytes(_aac(folder, "in.mp4", f"{aim}:linear=true"))
        after = _loudness(folder, "loud.mp4")
        over = float(after["input_tp"]) - CEILING if after else 0.0
        if over <= 0:
            return (folder / "loud.mp4").read_bytes()
        return _aac(folder, "loud.mp4", f"volume={-(over + 0.5):.2f}dB")  # under it, a margin


def _loudness(folder: Path, name: str) -> dict | None:
    """loudnorm's measure of a file's sound (input_i, input_tp, …), or None, logged."""
    import json  # noqa: PLC0415

    measure = ["ffmpeg", "-hide_banner", "-nostats", "-i", name, "-vn", "-af",
               f"{AIM}:print_format=json", "-f", "null", "-"]  # fmt: skip
    said = subprocess.run(measure, cwd=folder, capture_output=True, text=True,  # noqa: S603
                          timeout=_limit()).stderr  # fmt: skip
    try:
        return json.JSONDecoder().raw_decode(said[said.rindex("{") :])[0]  # its report, last
    except ValueError:
        log.warning("cut loudness: no loudnorm report for %s: %s", name, said[-500:])
        return None


def _aac(folder: Path, name: str, audio: str) -> bytes:
    """`name` with its sound through `audio`, as AAC; the picture copied."""
    return _run(folder, ["-i", name, "-map", "0:v?", "-map", "0:a:0", "-c:v", "copy", "-af",
                         audio, "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
                         "-movflags", "+faststart"])  # fmt: skip


def _tc(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def seconds(data: bytes) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "f").write_bytes(data)
        return _length(Path(tmp), "f")


# time_base: a copy reads every clip on the first one's clock (video 406: KIE's takes came at
# 1/12288 and 1/90000, so the second played seven times slow)
VIDEO = "codec_name,width,height,r_frame_rate,pix_fmt,time_base"
AUDIO = "codec_name,sample_rate,channels"


def stitch(videos: list[bytes]) -> bytes | None:
    """Join MP4 clips in order by copying their streams (no credits), only when every clip has
    the same video and audio format, its audio track included (ffmpeg's concat copy takes the
    streams from the first file and still succeeds, so a silent first take or mixed sizes and
    sample rates lose or drift the sound). None when they differ, the copy fails, or it comes
    out longer or shorter than its takes: then they are joined by re-encoding (`joined`)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        names = []
        for n, data in enumerate(videos):
            (folder / f"{n}.mp4").write_bytes(data)
            names.append(f"{n}.mp4")
        kinds = {(_probe(folder, f, "v:0", VIDEO), _probe(folder, f, "a:0", AUDIO)) for f in names}
        if len(kinds) != 1 or not next(iter(kinds))[0]:
            return None
        (folder / "list.txt").write_text("\n".join(f"file '{f}'" for f in names))
        copy = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-i", "list.txt", "-c", "copy"]
        done = subprocess.run([*copy, "out.mp4"], cwd=folder, capture_output=True,  # noqa: S603
                              timeout=_limit())  # fmt: skip
        takes = sum(_length(folder, f) for f in names)
        if done.returncode or abs(_length(folder, "out.mp4") - takes) > max(0.5, takes / 50):
            return None  # a copy that isn't as long as its takes is never the cut (video 406)
        return (folder / "out.mp4").read_bytes()


def cut_away(over: list[tuple[bytes, float, float]], data: bytes) -> bytes:
    """`data` with each B-roll take laid over its picture from `start` for `length` seconds,
    filling the frame; picture only, so the sound under it (the talker's voice) runs on."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "0.mp4").write_bytes(data)
        w, h = (_probe(folder, "0.mp4", "v:0", "width,height") or "720x1280").split("x")[:2]
        graph, under = [], "0:v"
        for n, (video, start, length) in enumerate(over, 1):
            (folder / f"{n}.mp4").write_bytes(video)
            graph += [f"[{n}:v]trim=duration={length},setpts=PTS-STARTPTS+{start}/TB,"
                      f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                      f"setsar=1[b{n}]",
                      f"[{under}][b{n}]overlay=eof_action=pass:"
                      f"enable='between(t,{start},{start + length})'[o{n}]"]  # fmt: skip
            under = f"o{n}"
        inputs = [arg for n in range(len(over) + 1) for arg in ("-i", f"{n}.mp4")]
        return _run(folder, [*inputs, "-filter_complex", ";".join(graph), "-map", f"[{under}]",
                             "-map", "0:a?", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a",
                             "copy", "-movflags", "+faststart"])  # fmt: skip


def _ratio(shape: str) -> float:
    w, _, h = shape.partition(":")
    return float(w) / float(h)


def _frame(folder: Path, shape: str | None) -> str:
    """Each piece's picture filter: scaled to the first take's size, as before; with the
    video's `shape`, first cut to that shape around its centre and scaled to the first take's
    size cut the same way (a take on Omni 1.2, which makes only 9:16 and 16:9: a 1:1
    video's takes are made 9:16 and cropped here, QA on #1440)."""
    size = _probe(folder, "0.mp4", "v:0", "width,height") or "720x1280"
    w, h = (int(x) for x in size.split("x")[:2])
    if not shape or ":" not in shape:
        return f"scale={w}:{h}"
    r = _ratio(shape)
    big_w, big_h = (round(h * r) // 2 * 2, h) if w / h > r else (w, round(w / r) // 2 * 2)
    return f"crop='min(iw,ih*{r:.6f})':'min(ih,iw/{r:.6f})',scale={big_w}:{big_h}"


def _shaped(data: bytes, shape: str | None) -> bool:
    """The take is already the video's shape (or none is asked), so it can be copied."""
    if not shape or ":" not in shape:
        return True
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "0.mp4").write_bytes(data)
        size = _probe(Path(tmp), "0.mp4", "v:0", "width,height")
    w, _, h = size.partition("x")
    return bool(size) and abs(int(w) / int(h) - _ratio(shape)) < 0.02


def joined(videos: list[bytes], cuts: list[tuple[float, float | None]],
           shape: str | None = None) -> bytes:  # fmt: skip
    """A story video's takes back to back, each from its in-point for its length (None: to
    its end), with their own sound (silence for a silent one); a short take holds its last
    frame."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for n, data in enumerate(videos):
            (folder / f"{n}.mp4").write_bytes(data)
        frame = _frame(folder, shape)
        lengths = [d if d is not None else max(0.1, _length(folder, f"{n}.mp4") - f)
                   for n, (f, d) in enumerate(cuts)]  # fmt: skip
        parts = []
        for n, ((f, _), d) in enumerate(zip(cuts, lengths, strict=True)):
            parts.append(f"[{n}:v]trim=start={f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:"
                         f"stop_duration={d},trim=duration={d},{frame},setsar=1,fps=30,"
                         f"format=yuv420p[v{n}]")  # fmt: skip
            parts.append(f"[{n}:a]{LATE}{SAME},atrim=start={f},asetpts=PTS-STARTPTS,apad=whole_dur={d},"
                         f"atrim=duration={d}[a{n}]" if _probe(folder, f"{n}.mp4", "a:0", "index")
                         else f"anullsrc=r=44100:cl=stereo,atrim=duration={d}[a{n}]")  # fmt: skip
        both = "".join(f"[v{n}][a{n}]" for n in range(len(videos)))
        graph = ";".join([*parts, f"{both}concat=n={len(videos)}:v=1:a=1[v][a]"])
        inputs = [arg for n in range(len(videos)) for arg in ("-i", f"{n}.mp4")]
        out = ["-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac"]
        return _run(folder, [*inputs, "-filter_complex", graph, *out, "-movflags", "+faststart"])


def _run(folder: Path, args: list[str]) -> bytes:
    done = subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "out.mp4"],  # noqa: S603, S607
                          cwd=folder, capture_output=True, timeout=_limit())  # fmt: skip
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
    return (folder / "out.mp4").read_bytes()


def _probe(folder: Path, name: str, stream: str, entries: str) -> str:
    probe = ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
             f"stream={entries}", "-of", "csv=p=0:s=x", name]  # fmt: skip
    return subprocess.run(  # noqa: S603 - fixed arguments; file names are ours
        probe, cwd=folder, capture_output=True, text=True, timeout=60,
    ).stdout.strip()  # fmt: skip


def _length(folder: Path, name: str) -> float:
    probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             name]  # fmt: skip
    done = subprocess.run(probe, cwd=folder, capture_output=True, text=True,  # noqa: S603
                          timeout=60).stdout.strip()  # fmt: skip
    try:
        return float(done)
    except ValueError:
        return 0.0


def level(music: dict | None) -> str:
    """The music's volume over time: `quieter_db` under the voice's lines, and back up between
    them when it rises (ramped), else down the whole way."""
    music = music or {}
    under = 10 ** (-float(music.get("quieter_db", 18)) / 20)
    lines = sorted(music.get("lines") or [])
    if music.get("gaps", "rise") != "rise" or not lines:
        return f"volume={MUSIC * under:.4f}"
    spans: list[list[float]] = []
    for a, b in lines:  # lines closer than the ramps hold the music down between them
        if spans and a - spans[-1][1] < 2 * RAMP:
            spans[-1][1] = max(spans[-1][1], b)
        else:
            spans.append([a, b])
    speaking = ""
    for a, b in spans:
        one = f"clip(min((t-{a - RAMP:.2f})/{RAMP},({b + RAMP:.2f}-t)/{RAMP}),0,1)"
        speaking = f"max({speaking},{one})" if speaking else one
    return f"volume=eval=frame:volume='{MUSIC}*(1-{1 - under:.4f}*{speaking})'"


def fade_out(total: float, last_word: float) -> str:
    """The end's fade: FADE seconds, but never starting before the last word has ended; a
    held end (the last shot's hold past the last word) fades only its last HELD_FADE, so the
    payoff plays (QA on #1450)."""
    held = last_word and total - last_word <= narration.FINAL_HOLD + 0.05
    st = max(total - (HELD_FADE if held else FADE), last_word, 0)
    return f"st={st:.2f}:d={max(total - st, 0.05):.2f}"


def song_cut(
    videos: list[bytes], lengths: list[float], song: bytes, narrated: bool = False,
    music: bytes | None = None, froms: list[float] | None = None, mix: dict | None = None,
    shape: str | None = None,
) -> bytes:  # fmt: skip
    """A song video (flows V6, free): each piece from its in-point (`froms`) for its length
    of the song (a short one slowed to fill it, never sped up: Song-Producer), joined in
    order with its own sound dropped, the song laid under the whole picture, and the end
    faded. A narrated video (V6n) keeps each take's own sound under the narration, with its
    music (`mix`: quieter_db, gaps, loop, lines) if any."""
    videos, froms = videos[: len(lengths)], (froms or [0.0] * len(lengths))
    total = sum(lengths)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for n, data in enumerate(videos):
            (folder / f"{n}.mp4").write_bytes(data)
        (folder / "song").write_bytes(song)
        frame = _frame(folder, shape)
        slow = [max(1.0, d / have) if (have := _length(folder, f"{n}.mp4") - froms[n]) > 0
                else 1.0 for n, d in enumerate(lengths)]  # fmt: skip
        parts = [f"[{n}:v]trim=start={froms[n]},setpts={slow[n]:.4f}*(PTS-STARTPTS),"
                 f"trim=duration={d},tpad=stop_mode=clone:stop_duration={d},trim=duration={d},"
                 f"{frame},setsar=1,fps=30,format=yuv420p[v{n}]"
                 for n, d in enumerate(lengths)]  # fmt: skip
        joined_v = "".join(f"[v{n}]" for n in range(len(videos)))
        fade = fade_out(total, (mix or {}).get("last_word") or 0)
        sound = (_narrated_mix(folder, lengths, froms, music is not None, fade, mix)
                 if narrated else [f"[{len(videos)}:a]atrim=duration={total},asetpts=PTS-STARTPTS,"
                                   f"apad=whole_dur={total},afade=t=out:{fade}[a]"])  # fmt: skip
        graph = ";".join(
            [*parts, f"{joined_v}concat=n={len(videos)}:v=1:a=0,fade=t=out:{fade}[v]", *sound]
        )
        inputs = [arg for n in range(len(videos)) for arg in ("-i", f"{n}.mp4")]
        inputs += ["-i", "song"]
        if narrated and music is not None:
            (folder / "music").write_bytes(music)
            looping = (mix or {}).get("loop", True)
            inputs += ["-i", looped(folder, "music", total) if looping else "music"]
        return _run(folder, [*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                             "-c:v", "libx264", "-c:a", "aac", "-t", str(total),
                             "-movflags", "+faststart"])  # fmt: skip


def _narrated_mix(folder: Path, lengths: list[float], froms: list[float], music: bool,
                  fade: str, mix: dict | None) -> list[str]:  # fmt: skip
    """Each take's own sound from its in-point (silence if it has none), the narration on top,
    the music under it at its level (`level`), made loud enough and faded. Each take's sound
    at its level in `mix["takes"]`, else TAKES."""
    n, total = len(lengths), sum(lengths)
    each = (mix or {}).get("takes") or [TAKES] * n
    takes = [f"[{i}:a]{SAME},atrim=start={froms[i]},asetpts=PTS-STARTPTS,atrim=duration={d},"
             f"apad=whole_dur={d},volume={each[i]}[a{i}]"
             if _probe(folder, f"{i}.mp4", "a:0", "index")
             else f"anullsrc=r=44100:cl=stereo,atrim=duration={d}[a{i}]"
             for i, d in enumerate(lengths)]  # fmt: skip
    joined_a = "".join(f"[a{i}]" for i in range(n))
    voice = f"[{n}:a]{SAME},atrim=duration={total},apad=whole_dur={total}[voice]"
    graph = [*takes, f"{joined_a}concat=n={n}:v=0:a=1[takes]", voice]
    if music:
        graph.append(f"[{n + 1}:a]{SAME},atrim=duration={total},apad=whole_dur={total},"
                     f"{level(mix)}[under]")  # fmt: skip
    parts = "[takes][voice][under]" if music else "[takes][voice]"
    graph.append(f"{parts}amix=inputs={3 if music else 2}:normalize=0:duration=first,{LOUD},"
                 f"aresample=44100,afade=t=out:{fade}[a]")  # fmt: skip
    return graph


def about(length: float) -> int:
    """Seconds a cut takes to make, before one was timed here: a guess of 0.7 s a second of
    cut, 10 s at least (`cut.about` uses the video's own last cut once there is one)."""
    return max(10, math.ceil(length * 0.7))
