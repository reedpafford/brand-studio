"""Joining whole takes into a cut (Blocker 2, the real-run audit): a stream copy only when
every take has the same format, its audio track included; else a re-encode in which a take
with no sound gets silence, so the cut keeps every take's sound, in sync. Real ffmpeg on
generated files, free."""

import subprocess
import tempfile
from pathlib import Path

from app import cut_render


def _take(color: str, size: str = "480x854", rate: int | None = 44100, tone: int = 440,
          late: float = 0, clock: int = 12288) -> bytes:  # fmt: skip
    """A 1-second MP4: a coloured picture, and a tone at `rate` Hz (None: no audio track),
    its track starting `late` seconds in; its video timed in 1/`clock` s."""
    tone_in = f"sine=frequency={tone}:sample_rate={rate}"
    offset = ["-itsoffset", str(late)] if late else []
    sound = [] if rate is None else [*offset, "-f", "lavfi", "-i", tone_in]
    args = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s={size}:d=1:r=24",
            *sound, "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            *([] if rate is None else ["-c:a", "aac"]), "-video_track_timescale", str(clock),
            "t.mp4"]  # fmt: skip
    with tempfile.TemporaryDirectory() as tmp:  # a file, not a pipe: its late start is kept
        subprocess.run(args, cwd=tmp, capture_output=True, check=True)  # noqa: S603
        return (Path(tmp) / "t.mp4").read_bytes()


def _facts(data: bytes) -> dict:
    """The cut's streams and lengths, and how loud each second of its sound is."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "c.mp4").write_bytes(data)
        probe = lambda s, e: cut_render._probe(Path(tmp), "c.mp4", s, e)  # noqa: E731
        loud = []
        for start in (0, 1, 0.1, 0.6):  # each second; and inside the first one, early and late
            span = "0.3" if start % 1 else "1"
            loudness = ["ffmpeg", "-v", "info", "-ss", str(start), "-t", span, "-i", "c.mp4",
                        "-vn", "-af", "volumedetect", "-f", "null", "-"]  # fmt: skip
            said = subprocess.run(loudness, cwd=tmp, capture_output=True, text=True).stderr  # noqa: S603
            mean = [ln for ln in said.splitlines() if "mean_volume" in ln]
            loud.append(float(mean[0].split(":")[1].split()[0]) if mean else -999.0)
        return {"size": probe("v:0", "width,height"), "audio": bool(probe("a:0", "index")),
                "video_s": float(probe("v:0", "duration") or 0),
                "audio_s": float(probe("a:0", "duration") or 0), "loud": loud}  # fmt: skip


def _cut(*takes: bytes) -> bytes:
    """The cut of whole takes, as render makes it for a dialogue video."""
    storage = {f"k{n}": t for n, t in enumerate(takes)}
    src = lambda n: {"key": f"k{n}", "inserts": [], "planned": [], "splices": [],  # noqa: E731
                     "from_keys": {}, "mutes": [], "sound": None}  # fmt: skip
    recipe = {"mode": "takes", "length": float(len(takes)),
              "pieces": [{"take_id": n, "from": 0, "whole": True, "length": 1.0}
                         for n in range(len(takes))],
              "sources": {str(n): src(n) for n in range(len(takes))}, "voice": None,
              "music": None, "host": None}  # fmt: skip
    return cut_render.render(recipe, type("S", (), {"get": lambda self, k: storage[k]})())


def test_takes_of_one_format_are_copied_and_differing_ones_never_are():
    same = [_take("red"), _take("blue")]
    assert cut_render.stitch(same) is not None  # the fast path, as made
    assert cut_render.stitch([_take("red", rate=None), _take("blue")]) is None
    assert cut_render.stitch([_take("red"), _take("blue", size="720x1280")]) is None
    assert cut_render.stitch([_take("red"), _take("blue", rate=48000)]) is None
    clocks = [_take("red"), _take("blue", clock=90000)]  # video 406: copied, it ran 7 times slow
    assert cut_render.stitch(clocks) is None and 1.9 < _facts(_cut(*clocks))["video_s"] < 2.2


def test_a_silent_first_take_never_takes_the_next_takes_sound_away():
    """A take with no audio track (Seedance 1 Lite, or nobody speaking) first: the copy took
    the first file's streams and dropped the speaker's sound. Now it's silence, then them."""
    got = _facts(_cut(_take("red", rate=None), _take("blue")))
    assert got["audio"] and got["loud"][0] < -80 < got["loud"][1], got  # silence, then the tone
    assert abs(got["audio_s"] - got["video_s"]) < 0.15, got  # in sync to the end


def test_mixed_sizes_and_sample_rates_join_into_one_format_in_sync():
    mixed = _facts(_cut(_take("red", size="480x854"), _take("blue", size="720x1280", rate=48000)))
    assert mixed["size"] == "480x854" and mixed["audio"], mixed
    assert abs(mixed["video_s"] - 2.0) < 0.25 and abs(mixed["audio_s"] - mixed["video_s"]) < 0.15
    assert mixed["loud"][0] > -80 and mixed["loud"][1] > -80  # both takes' sound kept


def test_whisper_never_runs_on_a_take_with_no_sound(tmp_path, monkeypatch):
    """A silent take (no audio track) has nothing to hear: whisper crashed on it, so narrated
    and song takes showed "Couldn't watch". Now it hears nothing; a take with sound is heard."""
    from app import reel
    from app.providers import local

    heard = []
    monkeypatch.setattr(reel, "transcribe", lambda path, *a, **k: heard.append(path) or ["said"])
    silent, sound = tmp_path / "silent.mp4", tmp_path / "sound.mp4"
    silent.write_bytes(_take("red", rate=None))
    sound.write_bytes(_take("blue"))
    assert local._heard(silent, True) == [] and heard == []
    assert local._heard(sound, words=True) == ["said"] and heard == [sound]


def test_a_take_whose_sound_starts_late_keeps_it_in_place():
    """QA on #1393: a take's audio track starting 0.5 s in was pulled to its start (atrim and
    asetpts to 0), out of sync with its picture; it stays where it was made."""
    got = _facts(_cut(_take("red", rate=None), _take("blue", late=0.5)))
    assert got["loud"][1] > -80 and abs(got["audio_s"] - got["video_s"]) < 0.15, got
    late = _facts(_cut(_take("blue", late=0.5), _take("red", rate=None)))
    assert late["loud"][2] < -80 < late["loud"][3], late  # silent at 0.1 s, the tone at 0.6 s


def _quiet(volumes: list[float]) -> bytes:
    """A take one second per volume (a quiet voice, then quieter music, say), at those gains."""
    tones = ";".join(f"sine=frequency={300 + 200 * n}:d=1,volume={v}[a{n}]"
                     for n, v in enumerate(volumes))  # fmt: skip
    joined = "".join(f"[a{n}]" for n in range(len(volumes)))
    graph = f"{tones};{joined}concat=n={len(volumes)}:v=0:a=1[a]"
    args = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            f"color=c=gray:s=480x854:d={len(volumes)}:r=24", "-filter_complex", graph,
            "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "t.mp4"]  # fmt: skip
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(args, cwd=tmp, capture_output=True, check=True)  # noqa: S603
        return (Path(tmp) / "t.mp4").read_bytes()


def _lufs(data: bytes) -> tuple[float, float]:
    """The integrated loudness (LUFS) and true peak (dBTP) of a cut's sound."""
    import json

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "c.mp4").write_bytes(data)
        said = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", "c.mp4", "-af",  # noqa: S603, S607
                               "loudnorm=print_format=json", "-f", "null", "-"], cwd=tmp,
                              capture_output=True, text=True).stderr  # fmt: skip
        m = json.JSONDecoder().raw_decode(said[said.rindex("{") :])[0]
        return float(m["input_i"]), float(m["input_tp"])


def _level(data: bytes, start: float) -> float:
    """The mean level (dB) of 0.4 s of a cut's sound from `start`."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "c.mp4").write_bytes(data)
        said = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(start), "-t", "0.4", "-i",  # noqa: S603, S607
                               "c.mp4", "-vn", "-af", "volumedetect", "-f", "null", "-"],
                              cwd=tmp, capture_output=True, text=True).stderr  # fmt: skip
        return float(said.split("mean_volume:")[1].split()[0])


def test_a_quiet_cut_is_brought_up_to_social_loudness_keeping_its_balance():
    """E2E 233: the delivered cut measured -25.4 LUFS, about 11 under social video. Every cut
    is brought to about -14 LUFS, its true peak at most -1 dBTP, with one gain: a voice 12 dB
    over the music stays 12 dB over it. The picture is untouched; silence stays silence."""
    quiet = _quiet([0.03, 0.0075])  # about -12 dB apart
    made = _cut(quiet)  # a dialogue video's cut of whole takes, as 233's
    lufs, peak = _lufs(made)
    assert -15.5 <= lufs <= -12.5 and peak <= -0.9, (lufs, peak)
    gap = [_level(d, 0.3) - _level(d, 1.3) for d in (quiet, made)]  # each second's middle
    assert abs(gap[0] - gap[1]) < 1.0, gap  # one gain: the voice stays as far over the music
    assert _facts(made)["size"] == "480x854" and abs(_facts(made)["video_s"] - 2) < 0.1
    silent = _take("red", rate=None)
    assert cut_render.loud(silent) == silent  # no sound: as it was


def test_a_transient_over_a_quiet_voice_stays_under_the_ceiling_after_the_encode(monkeypatch):
    """QA on #1407: a quiet voice (about -25 LUFS) over a bed with one -4.5 dBTP transient came
    out at -0.7 dBTP: loudnorm's dynamic mode, then the AAC encode's overshoot. Measured
    again after the encode, it's brought under -1 dBTP. A cut ffmpeg gives no loudness report
    for is left as it was, never failed."""
    graph = ("sine=frequency=220:d=4,volume=0.02[v];anoisesrc=d=4:c=pink:a=0.01:seed=7[b];"
             "aevalsrc='if(between(t,2,2.004),0.6*sin(2*PI*3000*t),0)':d=4:s=48000[t];"
             "[v][b][t]amix=inputs=3:normalize=0[a]")  # fmt: skip
    args = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=480x854:d=4:r=24",
            "-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "t.mp4"]  # fmt: skip
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(args, cwd=tmp, capture_output=True, check=True)  # noqa: S603
        quiet = (Path(tmp) / "t.mp4").read_bytes()
    before, peak = _lufs(quiet)
    assert before < -23 and peak > -6, (before, peak)  # a quiet voice, a loud transient
    lufs, peak = _lufs(cut_render.loud(quiet))
    assert peak <= cut_render.CEILING and lufs > before + 3, (lufs, peak)  # louder, under it
    monkeypatch.setattr(cut_render, "_loudness", lambda folder, name: None)
    assert cut_render.loud(quiet) == quiet  # no report: the cut as it was
