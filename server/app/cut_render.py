"""Making a cut (free: ffmpeg on our own server, the worker's local lane; app/cut.py says
what). `recipe` turns the cut's timeline into files and settings at the press, so `render`
needs no database: each take with what's laid over it (real images cut in, words spliced,
stretches muted, sound effects), then the pieces joined (a story video's back to back with
their own sound; a narrated or song video's on the voice's clock, a short take slowed to fill
its piece, never sped up), the music under the voice by the amount set, rising when no one
speaks or staying down, and the presenter over the B-roll per span. A known problem (music
that stops before the cut ends) comes back as plain words with its one-click fixes."""

import math
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app import cut_in, host, host_layer, screen_figures, take_mute, take_sound, word_splice
from app.models.clips import ClipTake, ProjectClip
from app.models.files import StoredFile
from app.models.projects import Project

FADE = 1.5  # seconds: a song video's end fades out (flows V6)
# A narrated video's mix (flows V6n): the takes' own sound under the narration, the music
# lower still, the whole about -14 LUFS
TAKES, MUSIC, LOUD = 0.75, 0.30, "loudnorm=I=-14:TP=-1.5:LRA=11"
AIM = "loudnorm=I=-14:TP=-1:LRA=20"  # every cut, last (E2E 233); LRA wide, so one gain
RAMP = 0.25  # seconds the music takes to dip under the voice and rise after it
SAME = "aformat=sample_rates=44100:channel_layouts=stereo"
LATE = "aresample=async=1:first_pts=0,"  # a take's sound that starts late keeps its place
SHORT_MUSIC = "the music file stops at {}, and the cut runs to {}"


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
    return {"key": _key(db, take.file_id), "inserts": inserts, "planned": row.seconds,
            "splices": splices,
            "from_keys": {str(s["from_take"]): _key(db, db.get(ClipTake, s["from_take"]).file_id)
                          for s in splices},
            "mutes": take_mute.spans(take),
            "sound": {"key": _key(db, sound["file_id"]), "level": take_sound.loudness(sound)}
            if sound else None}  # fmt: skip


def recipe(db: Session, project: Project, tl: dict) -> dict:
    """What `render` makes, as files and numbers."""
    from app.cut import song

    voice = song(db, project)
    music = tl["music"] if tl["music"] and not tl["music"]["removed"] else None
    out = {"mode": tl["mode"], "length": tl["length"],
           "pieces": [{"take_id": p["take_id"], "from": p["from"], "whole": p["whole"],
                       "length": round(p["end"] - p["start"], 2)} for p in tl["pieces"]],
           "sources": {str(t): _source(db, project, t)
                       for t in dict.fromkeys(p["take_id"] for p in tl["pieces"])},
           "voice": _key(db, voice.file_id) if voice else None,
           "last_word": tl.get("last_word") or 0.0,
           "music": {**{k: music[k] for k in ("quieter_db", "gaps", "loop")},
                     "key": _key(db, music["file_id"]),
                     "lines": tl.get("lines") or []} if music else None,
           "host": None}  # fmt: skip
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
    videos = [made[str(p["take_id"])] for p in pieces]
    if r["mode"] == "takes" and all(p["whole"] and not p["from"] for p in pieces):
        # As made: copied when every take is the same format, else joined with each take's
        # own sound (a silent one, or one with no audio track, gets silence; no drift).
        data = (not laid and stitch(videos)) or joined(videos, [(0.0, None)] * len(videos))
    elif r["mode"] == "takes":
        data = joined(videos, [(p["from"], None if p["whole"] else p["length"]) for p in pieces])
    else:
        music = r["music"]
        bed = storage.get(music["key"]) if music else None
        if music and not music["loop"] and (have := seconds(bed)) < r["length"] - 0.5:
            raise Problem(SHORT_MUSIC.format(_tc(have), _tc(r["length"])),
                          ["loop_music", "remove_music"])  # fmt: skip
        data = song_cut(
            videos,
            [p["length"] for p in pieces],
            storage.get(r["voice"]),
            r["mode"] == "narrated",
            bed,
            [p["from"] for p in pieces],
            {**(music or {}), "last_word": r.get("last_word") or 0},
        )
    progress(85)
    if r["host"]:
        hosts = [storage.get(k) for k in r["host"]["keys"]]
        data = host_layer.lay_over(data, hosts, r["host"]["spans"])
    data = loud(data)  # every kind of cut, as loud as social video plays (E2E 233: -25 LUFS)
    progress(100)
    return data


def loud(data: bytes) -> bytes:
    """The cut at about -14 LUFS with its true peak at most -1 dBTP: loudnorm measured, then
    applied as one gain (`linear`), so the voice, the music and the sound keep their balance;
    the picture is copied. A cut with no sound, or only silence, is as it was."""
    import json  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "in.mp4").write_bytes(data)
        if not _probe(folder, "in.mp4", "a:0", "index"):
            return data
        measure = ["ffmpeg", "-hide_banner", "-nostats", "-i", "in.mp4", "-vn", "-af",
                   f"{AIM}:print_format=json", "-f", "null", "-"]  # fmt: skip
        said = subprocess.run(measure, cwd=folder, capture_output=True, text=True,  # noqa: S603
                              timeout=600).stderr  # fmt: skip
        m = json.JSONDecoder().raw_decode(said[said.rindex("{") :])[0]  # its report, last
        if m["input_i"] in ("-inf", "inf") or float(m["input_i"]) < -70:
            return data  # silence: nothing to bring up
        keep = ":".join(f"measured_{k}={m[f'input_{k.lower()}']}" for k in ("I", "TP", "LRA"))
        aim = f"{AIM}:{keep}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}"
        return _run(folder, ["-i", "in.mp4", "-map", "0:v?", "-map", "0:a:0", "-c:v", "copy",
                             "-af", f"{aim}:linear=true", "-ar", "48000", "-c:a", "aac", "-b:a",
                             "192k", "-movflags", "+faststart"])  # fmt: skip


def _tc(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def seconds(data: bytes) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "f").write_bytes(data)
        return _length(Path(tmp), "f")


VIDEO = "codec_name,width,height,r_frame_rate,pix_fmt"
AUDIO = "codec_name,sample_rate,channels"


def stitch(videos: list[bytes]) -> bytes | None:
    """Join MP4 clips in order by copying their streams (no credits), only when every clip has
    the same video and audio format, its audio track included (ffmpeg's concat copy takes the
    streams from the first file and still succeeds, so a silent first take or mixed sizes and
    sample rates lose or drift the sound). None when they differ, or the copy fails: then they
    are joined by re-encoding (`joined`)."""
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
                              timeout=600)  # fmt: skip
        return (folder / "out.mp4").read_bytes() if done.returncode == 0 else None


def joined(videos: list[bytes], cuts: list[tuple[float, float | None]]) -> bytes:
    """A story video's takes back to back, each from its in-point for its length (None: to
    its end), with their own sound (silence for a silent one); a short take holds its last
    frame."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for n, data in enumerate(videos):
            (folder / f"{n}.mp4").write_bytes(data)
        size = (_probe(folder, "0.mp4", "v:0", "width,height") or "720x1280").replace("x", ":")
        lengths = [d if d is not None else max(0.1, _length(folder, f"{n}.mp4") - f)
                   for n, (f, d) in enumerate(cuts)]  # fmt: skip
        parts = []
        for n, ((f, _), d) in enumerate(zip(cuts, lengths, strict=True)):
            parts.append(f"[{n}:v]trim=start={f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:"
                         f"stop_duration={d},trim=duration={d},scale={size},setsar=1,fps=30,"
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
                          cwd=folder, capture_output=True, timeout=600)  # fmt: skip
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
    """The end's fade: FADE seconds, but never starting before the last word has ended."""
    st = max(total - FADE, last_word, 0)
    return f"st={st:.2f}:d={max(total - st, 0.05):.2f}"


def song_cut(
    videos: list[bytes], lengths: list[float], song: bytes, narrated: bool = False,
    music: bytes | None = None, froms: list[float] | None = None, mix: dict | None = None,
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
        size = _probe(folder, "0.mp4", "v:0", "width,height") or "720x1280"
        slow = [max(1.0, d / have) if (have := _length(folder, f"{n}.mp4") - froms[n]) > 0
                else 1.0 for n, d in enumerate(lengths)]  # fmt: skip
        parts = [f"[{n}:v]trim=start={froms[n]},setpts={slow[n]:.4f}*(PTS-STARTPTS),"
                 f"trim=duration={d},tpad=stop_mode=clone:stop_duration={d},trim=duration={d},"
                 f"scale={size.replace('x', ':')},setsar=1,fps=30,format=yuv420p[v{n}]"
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
            loop = ["-stream_loop", "-1"] if (mix or {}).get("loop", True) else []
            inputs += [*loop, "-i", "music"]
        return _run(folder, [*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                             "-c:v", "libx264", "-c:a", "aac", "-t", str(total),
                             "-movflags", "+faststart"])  # fmt: skip


def _narrated_mix(folder: Path, lengths: list[float], froms: list[float], music: bool,
                  fade: str, mix: dict | None) -> list[str]:  # fmt: skip
    """Each take's own sound from its in-point (silence if it has none), the narration on top,
    the music under it at its level (`level`), made loud enough and faded."""
    n, total = len(lengths), sum(lengths)
    takes = [f"[{i}:a]{SAME},atrim=start={froms[i]},asetpts=PTS-STARTPTS,atrim=duration={d},"
             f"apad=whole_dur={d},volume={TAKES}[a{i}]"
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
