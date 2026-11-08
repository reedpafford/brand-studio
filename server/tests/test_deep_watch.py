"""The deep watch as server code (app/deep_watch): free measurements and filmstrips, real ffmpeg."""

import subprocess

from PIL import Image

from app import deep_watch


def _video(path, flash: int | None = 30) -> None:
    """2 s, upright: grey, a white box for one frame (a glitch), silent for 1 s then a tone
    loud enough to clip."""
    box = f",drawbox=x=8:y=30:w=40:h=40:c=white:t=fill:enable='eq(n,{flash})'" if flash else ""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                    "color=c=gray:s=72x128:d=2:r=25", "-f", "lavfi", "-i",
                    "aevalsrc='if(lt(t,1),0,1.5*sin(2*PI*440*t))':s=44100:d=2",
                    "-vf", f"format=yuv420p{box}", "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    str(path)], check=True)  # fmt: skip


def test_it_measures_motion_glitches_and_sound(tmp_path):
    src = tmp_path / "take.mp4"
    _video(src)
    facts = deep_watch.probe(src)
    assert (facts["length"], facts["width"], facts["height"], facts["audio"]) == (
        2.0,
        72,
        128,
        True,
    )
    moved = deep_watch.motion(src, [])
    assert moved["jumps"] == [1.2]  # the box pops in and out: one jump
    assert deep_watch.motion(src, [1.2])["jumps"] == []  # on a cut, it's the cut
    heard = deep_watch.sound(src, [{"word": "hi", "start": 1.2, "end": 1.6}])
    assert heard["silences"] == [[0.0, 1.0]] and heard["clipped_samples"] > 0
    assert heard["loudness_per_half_second"][0] == -70.0 and heard["lufs"] > -10
    assert heard["between_words_lufs"] is not None  # loud while nobody speaks: noise or music
    told = deep_watch.told({**facts, "cuts": [], "motion": moved, "sound": heard})
    assert "Jumps away from any cut (a glitch, a pop or a morph?): [1.2]" in told
    assert "clipped samples" in told and "Silences: [[0.0, 1.0]]" in told


def test_strips_sample_the_take_and_its_moments(tmp_path):
    src = tmp_path / "take.mp4"
    _video(src, flash=None)
    words = [{"word": "Get", "start": 0.4, "end": 0.6}]
    facts, made = deep_watch.look(src, tmp_path, words, 10, 2)
    assert [m["what"] for m in made] == [
        "sampled frames over the whole (5 a second)", "sampled frames over the whole (5 a second)",
        "sampled frames round a key moment (10 a second)",
        "the sound as a spectrogram (time across, pitch up)"]  # fmt: skip
    first = Image.open(made[0]["path"])
    assert first.size == (4 * deep_watch.TILE, 2 * 456)  # 8 upright frames, four across
    assert Image.open(made[2]["path"]).size == first.size  # 0.8 s at 10 a second
    assert (made[2]["start"], made[2]["end"]) == (0.0, 0.7)  # around the first word
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "spectrogram.png", "strip-all-0.jpg", "strip-all-1.jpg", "strip-near-0.jpg",
        "take.mp4"]  # only the pictures stay  # fmt: skip
    assert deep_watch.named(made)[2] == "0.0–0.7 s: sampled frames round a key moment (10 a second)"
    assert deep_watch.said_at(words, 0.5) == "Get" and deep_watch.said_at(words, 0.7) == ""


def test_a_cuts_end_window_is_one_more_never_one_of_the_others(tmp_path):
    """QA on #1448: a cut's end window took one of the 4, so with 3 glitches its clip joins
    got none. The end comes first, and the glitches, joins and first word keep their own."""
    src = tmp_path / "cut.mp4"
    _video(src, flash=5)  # a glitch early on, far from the end
    _, made = deep_watch.look(src, tmp_path, [], 10, 1, ending=True)
    near = [(m["start"], m["end"]) for m in made if "key moment" in m["what"]]
    assert len(near) == 2 and near[0][0] < 0.5 and near[1][0] == 1.2  # the glitch and the end


def test_dense_windows_never_overlap_and_stay_inside():
    assert deep_watch.windows(6.0, [5.9, 1.0, 1.2, 3.0, 4.0], 3) == [0.6, 2.6, 5.2]
    assert deep_watch.windows(0.5, [0.2], 3) == [0.0]
    assert deep_watch.per_strip(1080, 1920) == 8 and deep_watch.per_strip(1920, 1080) == 16
