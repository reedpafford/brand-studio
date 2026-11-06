"""The director watches and listens to each piece of a Presenter's host as it lands (rule 11,
app/host_watch): corner pieces and a UGC talker's HeyGen take alike. Stand-ins only."""

import pytest

from app import director, host, host_watch, take_watch, talker, watch_report
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
from app.providers.fake_local import FakeWriter
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import _run
from tests.test_freestyle_song import NARRATION, _sent
from tests.test_host import _jobs, _video
from tests.test_talker import LINES


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins


def test_every_piece_of_the_host_is_watched_against_its_words_and_still(app, db, owner):
    fs = _sent(owner, "presenter", NARRATION)
    _run(app, db, ticks=160)
    video = _video(db, fs)
    pieces = host.rows(db, video)[1:]
    assert pieces and all(p.watch["state"] == "done" for p in pieces)
    assert {c.target for c in db.query(ItemCheck).filter_by(project_id=video.id)} >= {"piece"}
    looks = [j for j in _jobs(db, video, take_watch.STEP) if j.input.get("piece_id")]
    assert len(looks) == len(pieces)
    said = looks[0].input["prompt"]
    assert "s piece 1, 0.0–" in said and "made on HeyGen Avatar IV" in said and "<over>" in said
    assert looks[0].input["files"]["reference_images"][-1] == host.rows(db, video)[0].file_id
    shown = owner.get(f"/projects/{video.id}/host").json()["pieces"]
    assert shown[0]["watch"] is None and shown[1]["watch"]["action"] == "keep"
    assert owner.get(f"/projects/{video.id}/checks/watch").json()["takes"]["watched"] >= len(
        pieces)  # fmt: skip


def test_a_weak_piece_is_made_again_with_the_fix_in_its_prompt(app, db, owner, monkeypatch):
    fs = _sent(owner, "presenter", NARRATION)
    _run(app, db, ticks=160)
    video = _video(db, fs)
    piece = host.rows(db, video)[1]
    check = db.query(ItemCheck).filter_by(target="piece", target_id=piece.id).one()
    look = db.get(Job, check.job_id)
    look.output = {"seen": "The lips may slip behind the words at 0:01.", "verdict": "redo",
                   "faults": [{"kind": "lipsync", "at": 1.0, "says": "The lips may be late",
                               "evidence": "picture"}],
                   "note": "lips on every word", "prompt": ""}  # fmt: skip
    take_watch.save(db, look)  # lip-sync from sampled frames: never confirmed, never paid for
    db.commit()
    w = db.get(type(piece), piece.id).watch
    assert (w["action"], w["remake_job_id"]) == ("unsure", None)
    assert w["did"] == "Not remade: The lips may be late (not confirmed). Listen before you use it."
    assert w["faults"][0]["verified"] is False
    look.output = {"seen": "His hand melts into the desk at 0:01.", "verdict": "redo",
                   "faults": [{"kind": "motion", "at": 1.0, "says": "A hand melts",
                               "evidence": "picture"}],
                   "note": "hands stay whole and still", "prompt": ""}  # fmt: skip
    take_watch.save(db, look)
    db.commit()
    w = db.get(type(piece), piece.id).watch
    how = "on HeyGen Avatar IV with “hands stay whole and still” in the prompt"
    assert w["action"] in ("redo", "held")  # past the run's approved price: the owner's OK
    assert w["did"] in (
        f"Made it again {how}.",
        f"Asked the owner: making it again {how} goes past the video's budget.",
    )
    again = db.get(Job, w["remake_job_id"])
    assert again.input[host_watch.REDO] == piece.id
    assert again.status == (JobStatus.queued if w["action"] == "redo"
                            else JobStatus.needs_owner_approval)  # fmt: skip
    assert "hands stay whole and still." in again.input["input"]["motion_prompt"]
    lines = [m["text"] for m in director.thread(db, video) if m["id"].startswith("w-host-")]
    assert lines == [f"The host's piece {piece.number}: His hand melts into the desk at 0:01. "
                     f"{w['did']}"]  # fmt: skip
    assert host_watch.remakes(db, piece) == 1
    seen = owner.get(f"/projects/{video.id}/checks/watch").json()
    assert any(r["clip_id"] == "host" and r["at"] == round(piece.start + 1.0, 1)
               for r in seen["redid"])  # fmt: skip


def test_a_ugc_talkers_heygen_take_is_watched_and_its_clips_carry_it(app, db, owner, monkeypatch):
    usual = FakeWriter._take_watch

    def lips(self, prompt):
        if "of the narration, made on" not in prompt:
            return usual(self, prompt)
        return {"seen": "A hand melts into the phone at 0:00.5; kept.", "verdict": "keep",
                "faults": [{"kind": "motion", "at": 0.5, "says": "A hand melts",
                            "evidence": "picture"}]}  # fmt: skip

    monkeypatch.setattr(FakeWriter, "_take_watch", lips)
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": LINES,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    _run(app, db, ticks=200)
    video = _video(db, fs)
    (row,) = host.rows(db, video)[1:]
    assert row.watch["state"] == "done" and row.watch["faults"][0]["says"] == "A hand melts"
    look = next(j for j in _jobs(db, video, take_watch.STEP) if j.input.get("piece_id"))
    assert "made on HeyGen Avatar IV" in look.input["prompt"]
    assert talker.MOTION in look.input["prompt"]
    for clip_id in talker.clips(db, video):
        clip = db.query(ProjectClip).filter_by(project_id=video.id, clip_id=clip_id).one()
        take = db.get(ClipTake, clip.picked_take_id)
        shown = watch_report.shown(db, take)  # its share of the talker's watch, read live
        assert take.watch is None and shown["found"] == row.watch["found"]
    done = {"state": "done", "did": "x"}
    assert watch_report.part({**done, "faults": [{"at": 3.0}, {"at": None}]}, 2.0, 4.0)[
        "faults"
    ] == [{"at": 1.0}, {"at": None}]  # its own seconds; the whole take's too
    assert watch_report.part({**done, "faults": [{"at": 5.0}]}, 2.0, 4.0)["action"] == "keep"
    assert watch_report.part({"state": "watching"}, 2.0, 4.0) == {"state": "watching"}
