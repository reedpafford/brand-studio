"""Sound effects on request (Reed, 3 Nov: "add slight sound effects on the b-roll" after it was
made): MMAudio on the picked takes, asked in the director's chat or on a clip, mixed under the
voice in the cut, which goes out of date and is made again. Stand-ins only."""

import json
import re
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from app import take_sound
from app.catalogue import get_model
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job, JobStatus
from app.providers import fake_local
from app.providers.replicate import _usage
from app.steps import step_failed
from tests.test_freestyle_dialogue import _run
from tests.test_freestyle_song import NARRATION, _sent
from tests.test_host import _jobs, _video

SCHEMA = Path(__file__).parent / "fixtures/replicate/zsxkib_mmaudio.json"


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def _made(app, db, owner):
    fs = _sent(owner, "narrated", NARRATION)
    _run(app, db, ticks=160)
    assert owner.get(f"/freestyles/{fs['id']}").json()["status"] == "delivered"
    return fs, _video(db, fs)


def test_asked_in_the_chat_the_director_adds_slight_sound_to_the_silent_b_roll(app, db, owner):
    fs, video = _made(app, db, owner)
    first = db.query(FinalVideo).filter(FinalVideo.project_id == video.id).all()[-1]
    said = owner.post(f"/freestyles/{fs['id']}/messages",
                      json={"text": "Add slight sound effects on the b-roll."})  # fmt: skip
    assert said.status_code == 201, said.text
    _run(app, db, ticks=120)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]]
    clips = db.query(ProjectClip).filter(ProjectClip.project_id == video.id).all()
    jobs = _jobs(db, video, take_sound.STEP)
    assert len(jobs) == len(clips) >= 1  # every picked take: the stand-in takes are silent
    inputs = json.loads(SCHEMA.read_text())["Input"]["properties"]
    for job in jobs:
        sent = job.input["input"]
        assert (job.kind, job.input["model"], job.input["how"]) == ("sound", "mmaudio", "slight")
        assert set(sent) | {"video"} <= set(inputs) and job.input["files"]["video"]
        assert sent["prompt"].startswith("Add slight sound effects on the b-roll. On screen: ")
        assert "music" in sent["negative_prompt"] and sent["num_steps"] == 25
        assert job.credits == get_model("mmaudio").credits_per_unit()  # its real cost
    for row in clips:
        assert db.get(ClipTake, row.picked_take_id).made_with["sound"]["how"] == "slight"
    final = db.query(FinalVideo).filter(FinalVideo.project_id == video.id).all()[-1]
    assert final.id != first.id and [x for x in final.cut_ins if "/sound:" in x]  # made again


def test_a_clips_sound_is_tried_again_once_then_make_again_and_remove_undoes_it(app, db, owner):
    _, video = _made(app, db, owner)
    row = db.query(ProjectClip).filter(ProjectClip.project_id == video.id).first()
    path = f"/projects/{video.id}/clips/{row.id}/sound"

    def fail(job):
        job.status, job.error = JobStatus.failed, "The service couldn't finish this."
        step_failed(db, job)
        db.commit()

    r = owner.post(path, json={"asked": "a loud splash"})
    assert r.status_code == 201 and r.json()["sound"]["state"] == "making", r.text
    assert r.json()["sound"]["credits"] > 0  # shown before the press
    (job,) = _jobs(db, video, take_sound.STEP)
    fail(job)
    _run(app, db, ticks=10)  # its one retry runs on its own
    shown = owner.get(f"/projects/{video.id}/clips").json()
    sound = next(c for c in shown if c["id"] == row.id)["sound"]
    assert (sound["state"], sound["how"]) == ("ready", "strong")
    assert owner.get(f"/projects/{video.id}/video").json()["out_of_date"]
    owner.post(path, json={"asked": "rain"})
    again = _jobs(db, video, take_sound.STEP)[-1]
    fail(again)
    (retry,) = [j for j in _jobs(db, video, take_sound.STEP) if j.retry_of_id == again.id]
    fail(retry)  # no second retry: Make again, at its price (rule 22)
    assert not [j for j in _jobs(db, video, take_sound.STEP) if j.retry_of_id == retry.id]
    failed = owner.get(f"/projects/{video.id}/clips").json()
    sound = next(c for c in failed if c["id"] == row.id)["sound"]
    assert sound["state"] == "failed" and sound["error"]
    assert owner.post(path, json={"asked": "rain"}).status_code == 201
    db.query(Job).filter(Job.status == JobStatus.queued).delete()
    db.commit()
    gone = owner.delete(path)
    assert gone.status_code == 200 and gone.json()["sound"]["state"] != "ready"
    assert "sound" not in db.get(ClipTake, row.picked_take_id).made_with  # silent again


def test_the_sound_is_mixed_under_a_silent_take_and_slight_sits_lower():
    from app.clip_takes import _probe

    take, sound = fake_local.mp4("9:16", 2), fake_local.mp4("9:16", 2, sound=True)
    out = take_sound.apply(take, sound, take_sound.LEVELS[take_sound.how("slight footsteps")])
    folder = Path(__import__("tempfile").mkdtemp())
    (folder / "out.mp4").write_bytes(out)
    assert _probe(folder, "out.mp4", "a:0", "index")  # the silent take has sound now
    assert take_sound.LEVELS["slight"] < take_sound.LEVELS[take_sound.how("add sound effects")]


def _loud(data: bytes, tmp: Path) -> tuple[float | None, float]:
    """A file's integrated loudness and its true peak (dBFS)."""
    (tmp / "x.mp4").write_bytes(data)
    said = subprocess.run(["ffmpeg", "-nostats", "-i", str(tmp / "x.mp4"), "-af",  # noqa: S603, S607
                           "ebur128=peak=true", "-f", "null", "-"],
                          capture_output=True, text=True).stderr  # fmt: skip
    peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", said)[-1])
    return take_sound.measured(tmp, "x.mp4"), peak


def _quiet(tmp: Path, db: int) -> bytes:
    """A 3 s take with a quiet effect on it (MMAudio's come back -30 to -60 dB: th-20s)."""
    out = tmp / f"quiet{db}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                    "color=c=black:s=64x64:d=3", "-f", "lavfi", "-i",
                    f"anoisesrc=d=3:c=pink:a=1,volume={db}dB", "-shortest", "-c:v", "libx264",
                    "-c:a", "aac", str(out)], check=True)  # fmt: skip
    return out.read_bytes()


def test_each_effect_is_set_to_its_loudness_against_the_voice_and_limited(tmp_path):
    """th-20s: the effects came back far under a -16 LUFS voice and vanished; each one is
    measured and brought to its own level against the voice, peaks limited."""
    silent = fake_local.mp4("9:16", 3)
    out = take_sound.apply(silent, _quiet(tmp_path, -40), take_sound.level("footsteps"))
    loud, _ = _loud(out, tmp_path)
    assert abs(loud - (take_sound.VOICE + take_sound.LEVELS["normal"])) < 1.5  # 12 LU under
    out = take_sound.apply(silent, _quiet(tmp_path, -2), take_sound.level("the alarm, -3 dB"))
    loud, peak = _loud(out, tmp_path)
    assert abs(loud - (take_sound.VOICE - 3)) < 1.5 and peak <= 0.0  # the limiter holds it
    assert take_sound.how("the alarm louder than the voice") == "over the voice"
    assert take_sound.level("the alarm louder than the voice") > 0
    assert take_sound.level("+40 dB") == take_sound.LOUDEST  # never past the cap
    assert take_sound.level("10 dB under the voice") == -10  # unsigned: under (QA on #1316)
    assert take_sound.level("3 dB over the voice") == 3 and take_sound.level("-10 dB") == -10
    out = take_sound.apply(silent, _quiet(tmp_path, -1), take_sound.LOUDEST)  # pushed hard
    assert _loud(out, tmp_path)[1] <= -1.0  # limited at -3 dBFS (AAC overshoots a little)
    assert take_sound.gain(None, -12) == 0.0  # nothing to measure: left as it is


def test_mmaudios_real_cost_is_its_gpu_time():
    model = get_model("mmaudio")
    item = _usage(model, {"metrics": {"predict_time": 8.0}, "input": {}}, 1)
    assert item.cost_usd == Decimal("8.0") * Decimal("0.000975") and not item.estimated
