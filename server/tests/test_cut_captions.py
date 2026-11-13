"""Captions in a story video's cut (app/cut_captions.py): the script's words on the times
they are heard, a few at a time, burned in with the spoken word in yellow."""

import io
import subprocess

from PIL import Image

from app import cut_captions

LINES = [{"text": "Did you scream?", "start": 0, "end": 2},
         {"text": "She is sixteen, and nobody said a word.", "start": 2, "end": 7}]  # fmt: skip


def _heard(*words: tuple[str, float]) -> list[dict]:
    return [{"word": w, "start": at, "end": at + 0.3} for w, at in words]


def test_scripted_words_sit_where_they_are_heard_and_an_unheard_one_stays_in_its_shot():
    heard = _heard(("Did", 0.5), ("you", 0.9), ("scream?", 1.1), ("She", 2.4), ("is", 2.7),
                   ("16", 3.0), ("and", 3.5), ("nobody", 3.8), ("said", 4.2),
                   ("word", 4.9))  # fmt: skip
    words = cut_captions.timed(LINES, heard)
    assert [w["word"] for w in words] == " ".join(x["text"] for x in LINES).split()  # as written
    at = {w["word"]: w["start"] for w in words}
    assert (at["Did"], at["scream?"], at["nobody"]) == (0.5, 1.1, 3.8)
    assert at["sixteen,"] == 3.0  # heard as "16": the script's spelling, on the heard time
    assert 4.5 <= at["a"] <= 4.9  # never heard: between its neighbours
    late = cut_captions.timed(LINES[:1], _heard(("Did", 0.5), ("you", 0.9), ("scream?", 9.0)))
    assert late[2]["start"] <= 2.6  # heard far outside its shot: placed inside it


def test_a_caption_holds_a_few_words_and_breaks_at_the_lines_punctuation():
    heard = _heard(*((w, 0.4 * n) for n, w in enumerate(
        "Did you scream? She is sixteen, and nobody said a word.".split())))  # fmt: skip
    caps = cut_captions.chunks(cut_captions.timed(
        [{**LINES[0], "end": 1.2}, {**LINES[1], "start": 1.2}], heard))  # fmt: skip
    assert [" ".join(c["words"]) for c in caps] == [
        "Did you scream?", "She is sixteen,", "and nobody said a word."]  # fmt: skip
    assert all(len(c["words"]) == len(c["at"]) and c["end"] > c["start"] for c in caps)
    assert caps[1]["end"] == caps[2]["start"]  # it stays up until the next takes over


def test_the_word_being_said_is_yellow_in_the_picture_and_the_sound_is_untouched(tmp_path):
    made = ["-f", "lavfi", "-i", "color=c=black:s=480x854:d=2:r=24", "-f", "lavfi", "-i",
            "sine=d=2", "-shortest", "-pix_fmt", "yuv420p"]  # fmt: skip
    subprocess.run(["ffmpeg", "-v", "error", *made, str(tmp_path / "cut.mp4")], check=True)  # noqa: S603, S607
    caps = [{"start": 0.5, "end": 1.5, "words": ["Did", "you"], "at": [0.5, 1.0]}]
    out = tmp_path / "out.mp4"
    out.write_bytes(cut_captions.burn((tmp_path / "cut.mp4").read_bytes(), caps))

    def colours(at: float) -> set[str]:
        png = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(out),  # noqa: S603, S607
                              "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"],
                             capture_output=True, check=True).stdout  # fmt: skip
        band = Image.open(io.BytesIO(png)).convert("RGB").crop((0, 590, 480, 650))
        seen = {px for _, px in band.getcolors(1 << 20)}
        yellow = any(p[0] > 200 and p[1] > 170 and p[2] < 90 for p in seen)
        return {name for name, there in (("yellow", yellow), ("white", any(min(p) > 215
                                                                             for p in seen)))
                if there}  # fmt: skip

    assert colours(0.2) == set() and colours(1.8) == set()  # no caption: the picture as it was
    assert colours(0.7) == {"yellow", "white"} == colours(1.2)  # one word lit, the other white
    probe = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of",
             "csv=p=0", str(out)]  # fmt: skip
    kinds = subprocess.run(probe, capture_output=True, text=True, check=True).stdout.split()  # noqa: S603
    assert [k.split(",")[0] for k in kinds] == ["video", "audio"]
    assert all(abs(float(k.split(",")[1]) - 2.0) < 0.1 for k in kinds)
    assert cut_captions.burn(b"as it is", []) == b"as it is"  # nothing to say: nothing done
