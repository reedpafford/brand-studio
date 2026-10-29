"""Cut-ins at stitch time: the real brand picture over insert shots (real ffmpeg, free)."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from app.cut_in import apply
from tests.conftest import png, upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_clip_takes import FakeSeedance, _mp4, _work
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_project_clips import _answer, _prompt


def _frame_at(video: bytes, seconds: float) -> tuple[int, int, int]:
    """The centre pixel of the frame at `seconds`."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "v.mp4").write_bytes(video)
        args = ["-v", "error", "-ss", str(seconds), "-i", "v.mp4", "-frames:v", "1", "f.png"]
        subprocess.run(["ffmpeg", *args], cwd=tmp, check=True)  # noqa: S603, S607
        with Image.open(Path(tmp) / "f.png") as img:
            return img.convert("RGB").getpixel((img.width // 2, img.height // 2))


def _seconds(video: bytes) -> float:
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", "-"]
    done = subprocess.run(command, input=video, capture_output=True, check=True)  # noqa: S603, S607
    return float(json.loads(done.stdout)["format"]["duration"])


def test_picture_covers_its_stretch_only_for_at_least_1_2_s():
    args = (  # 3 s of red with sound
        "-v error -f lavfi -i color=c=red:s=96x160:d=3 -f lavfi -i anullsrc=r=44100:cl=mono "
        "-t 3 -c:v libx264 -pix_fmt yuv420p -c:a aac -movflags frag_keyframe+empty_moov "
        "-f mp4 pipe:1"
    ).split()
    clip = subprocess.run(["ffmpeg", *args], capture_output=True, check=True).stdout  # noqa: S603, S607
    out = apply(clip, [(png(40, 40, "blue"), 1.0, 1.4)], planned=3)  # 0.4 s: held to 1.2 s
    assert _seconds(out) == pytest.approx(3, abs=0.1)
    red, blue = _frame_at(out, 0.5), _frame_at(out, 2.0)
    assert red[0] > 200 > red[2] and blue[2] > 200 > blue[0]
    assert _frame_at(out, 2.6)[0] > 200  # back to the clip after 1.0 + 1.2 s
    streams = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", "-"],  # noqa: S607
        input=out,
        capture_output=True,
        check=True,
    ).stdout
    assert "audio" in {s["codec_type"] for s in json.loads(streams)["streams"]}


@pytest.fixture
def approved(app, db, editor, setup):  # noqa: F811
    """One clip whose second shot is an insert of the Buy screen, with an approved take."""
    mom = editor.post(
        "/library/character", json={"name": "Mom", "image_file_ids": [upload(editor)]}
    ).json()["id"]
    with_sheet(db, mom)
    base = f"/projects/{setup['project']}"
    editor.patch(base, json={"cast_ids": [mom]})
    bd = json.loads(json.dumps(BREAKDOWN))
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mom}"]
    bd["scenes"][0]["shots"][1]["screen_ids"] = [f"screen:{setup['screen']}"]
    editor.post(f"{base}/breakdown")
    _run(app, db, FakeClaude(bd))
    editor.post(f"{base}/clips/prompts")
    _run(app, db, FakeClaude(_answer(mom, setup["screen"], _prompt())))
    clip = editor.get(f"{base}/clips").json()[0]
    editor.post(f"{base}/clips/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    editor.post(f"{base}/clips/{clip['id']}/approve")
    return base, clip


def test_inserts_start_off_and_can_be_switched_on(db, editor, setup, approved):  # noqa: F811
    base, clip = approved
    (insert,) = editor.get(f"{base}/clips").json()[0]["inserts"]
    assert (insert["shot_id"], insert["name"], insert["use_real_image"]) == ("1.2", "Buy", False)
    assert (insert["start"], insert["end"]) == (3.125, 5.0)  # 2.5 + 1.5 s planned over 5 s

    plain = editor.post(f"{base}/video")
    assert plain.status_code == 201, plain.text
    assert _frame_at(editor.get(f"/files/{plain.json()['file_id']}").content, 0.5)[1] < 60  # red

    url = f"{base}/clips/{clip['id']}/inserts/1.2"
    on = editor.put(url, json={"use_real_image": True}).json()
    assert on["inserts"][0]["use_real_image"] is True and on["approved"] is True
    assert editor.get(f"{base}/video").json()["out_of_date"] is True
    video = editor.post(f"{base}/video").json()
    assert video["out_of_date"] is False
    data = editor.get(f"/files/{video['file_id']}").content
    assert _frame_at(data, 0.5)[1] > 100  # the 1 s take is all insert (held 1.2 s): orange
    bad = editor.put(f"{base}/clips/{clip['id']}/inserts/1.1", json={"use_real_image": True})
    assert bad.status_code == 404


def test_a_shot_with_a_character_holding_the_screen_can_use_the_real_image(db, editor, approved):
    # Reed, 2026-10-27: screens are in the character's hand now (Director #546); still off.
    from app.models.breakdowns import BreakdownVersion
    from app.models.clips import ProjectClip

    base, clip = approved
    row = db.get(BreakdownVersion, db.get(ProjectClip, clip["id"]).breakdown_id)
    data = json.loads(json.dumps(row.data))
    held = data["scenes"][0]["shots"][1]
    held["character_ids"] = data["scenes"][0]["shots"][0]["character_ids"]
    held["screen_ids"] = ["product:99", *held["screen_ids"]]  # its first project screen counts
    row.data = data
    db.commit()
    (insert,) = editor.get(f"{base}/clips").json()[0]["inserts"]
    assert (insert["shot_id"], insert["name"], insert["use_real_image"]) == ("1.2", "Buy", False)


def test_a_replaced_shot_loses_its_real_image(app, db, editor, setup, approved):  # noqa: F811
    """Reed, 2026-10-27: "Use the real image" is cleared when its shot is replaced; a new
    breakdown that keeps the shot as it was keeps the switch."""
    base, clip = approved
    mom = editor.get(f"{base}").json()["cast_ids"][0]
    editor.put(f"{base}/clips/{clip['id']}/inserts/1.2", json={"use_real_image": True})
    bd = editor.get(f"{base}/breakdown").json()["breakdown"]

    def again(plan: dict) -> bool:
        editor.post(f"{base}/breakdown")
        _run(app, db, FakeClaude(plan))
        editor.post(f"{base}/clips/prompts")
        _run(app, db, FakeClaude(_answer(mom, setup["screen"], _prompt())))
        return editor.get(f"{base}/clips").json()[0]["inserts"][0]["use_real_image"]

    assert again(bd) is True  # the same shot, the same screen
    bd["scenes"][0]["shots"][1]["action"] = "A new shot of the phone on the counter."
    assert again(bd) is False
