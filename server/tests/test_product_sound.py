"""A product's own sound in the cut (app/product_sound.py): loud where the plan says it is
heard, down under a spoken line, off the moment its last shot ends."""

import subprocess

from app import product_sound


def _level(path, at: float, span: float = 0.4) -> float:
    """Mean volume (dB) of a file's sound from `at` for `span` seconds."""
    said = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(at), "-t", str(span), "-i",  # noqa: S603, S607
                           str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                          capture_output=True, text=True).stderr  # fmt: skip
    return float(
        next(ln for ln in said.splitlines() if "mean_volume" in ln).split(":")[1].split()[0]
    )


def test_the_sound_is_loud_in_its_shots_down_under_a_line_and_off_after(tmp_path):
    take, tone = tmp_path / "take.mp4", tmp_path / "tone.wav"
    quiet = ["-f", "lavfi", "-i", "color=s=64x64:d=8:r=24", "-f", "lavfi", "-i",
             "anoisesrc=d=8:amplitude=0.01", "-shortest", "-pix_fmt", "yuv420p"]  # fmt: skip
    subprocess.run(["ffmpeg", "-v", "error", *quiet, str(take)], check=True)  # noqa: S603, S607
    whistle = ["-f", "lavfi", "-i", "sine=frequency=3500:duration=1"]  # 1 s: looped to fill
    subprocess.run(["ffmpeg", "-v", "error", *whistle, str(tone)], check=True)  # noqa: S603, S607
    out = tmp_path / "out.mp4"
    out.write_bytes(product_sound.apply(take.read_bytes(), tone.read_bytes(),
                                        [[2.0, 6.0]], [[4.0, 5.0]]))  # fmt: skip
    before, loud, under, again, after = (_level(out, t) for t in (0.8, 2.6, 4.3, 5.5, 6.6))
    assert loud > before + 25 and again > before + 25  # heard: far above the room
    assert 12 < loud - under < 24  # down under the line (18 LU), not gone
    assert after < before + 3  # off once its last shot ends
    probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0"]
    video = subprocess.run([*probe, str(out)], capture_output=True, text=True).stdout  # noqa: S603
    assert abs(float(video) - 8.0) < 0.2  # the take's own length: the loop never runs on


def test_a_products_sound_is_kept_on_it_told_to_the_plan_and_laid_where_the_plan_hears_it(
        app, owner, db, monkeypatch):  # fmt: skip
    """Reed, 13 Nov: "store the alarm noise somewhere that makes sense, maybe in the brand
    setup". It is the product's own, in the brand's library; the plan is told the product
    makes a sound and marks the shots it is heard in; the cut lays it there."""
    import io
    import wave

    from sqlalchemy.orm.attributes import flag_modified

    from app import clip_prompts, cut, cut_render
    from app.models.clips import FinalVideo
    from app.models.projects import Project
    from app.one_pass_assemble import PLAN
    from app.settings import get_settings
    from tests.conftest import upload
    from tests.helpers import product
    from tests.test_one_pass import BODY, _jobs, _run, _video

    monkeypatch.setattr(get_settings(), "one_pass", True)
    tone = io.BytesIO()
    with wave.open(tone, "wb") as w:
        w.setparams((1, 2, 44100, 0, "NONE", ""))
        w.writeframes(bytes(44100 * 2))
    sound = upload(owner, name="alarm.wav", data=tone.getvalue(), content_type="audio/wav")
    alarm = product(db, 1, "Alarm")
    db.commit()
    kept = owner.patch(f"/library/prop/{alarm}", json={"voice_file_id": sound})
    assert kept.status_code == 200 and kept.json()["voice_file_id"] == sound
    assert owner.post("/freestyles", json={**BODY, "product_ids": [alarm]}).status_code == 201
    _run(app, db)
    video = db.get(Project, _video(db).id)
    assert f"prop:{alarm} | prop | Alarm" in _jobs(db, "one_pass")[0].input["prompt"]
    assert "makes its own sound" in _jobs(db, "one_pass")[0].input["prompt"]
    tl, _ = cut.timeline(db, video)
    first = str(tl["pieces"][0]["take_id"])
    assert cut_render.recipe(db, video, tl)["sources"][first]["product"] is None  # none heard
    row = clip_prompts.newest(db, video)
    shots = row.data[PLAN]["clips"][0]["shots"]
    shots[0]["product_sound"] = True  # heard in clip 1's first shot only
    flag_modified(row, "data")
    db.commit()
    heard = cut_render.recipe(db, video, tl)["sources"][first]["product"]
    assert heard["spans"] == [[0.0, float(shots[0]["seconds"])]] and heard["speech"]
    assert owner.post(f"/projects/{video.id}/cut").status_code in (200, 201, 202)
    _run(app, db, ticks=6, start=False)
    assert db.query(FinalVideo).count() == 2  # the cut is made with it laid in
