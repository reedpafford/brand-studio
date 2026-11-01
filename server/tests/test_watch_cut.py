"""The director watches its cut (watch_cut): a free listen picks the frames on the cut's
boundaries, one look on the director's own limit says what's off, and the findings it can act
on are checked first. On the free stand-ins."""

import pytest
from fastapi import HTTPException

from app import watch_cut
from app.models.accounts import User
from app.models.jobs import Job
from app.models.projects import Project
from app.providers.fake_local import hear_cut
from app.providers.local import LocalProvider
from app.worker import run_once
from tests.conftest import run_writer
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

CUT = [{"clip_id": "c1", "start": 0.0, "end": 4.0, "take_id": 1,
        "other_takes": [{"take_id": 7, "number": 2, "verdict": "clean"}]},
       {"clip_id": "c2", "start": 4.0, "end": 9.0, "take_id": 2, "other_takes": []}]  # fmt: skip
WORDS = [{"word": "Get", "start": 4.5, "end": 4.8, "clip_id": "c2"},
         {"word": "fomo.", "start": 4.8, "end": 5.3, "clip_id": "c2"},
         {"word": "Ugh!", "start": 7.0, "end": 7.4, "clip_id": "c2"}]  # fmt: skip


def test_each_clip_sits_where_the_cut_put_it_and_the_frames_on_its_boundaries():
    spans = watch_cut.spans_of([("c1", 1, 4.0), ("c2", 2, 6.0)], 9.0)  # re-encoded: 9 s, not 10
    assert spans == [{"clip_id": "c1", "take_id": 1, "start": 0.0, "end": 3.6},
                     {"clip_id": "c2", "take_id": 2, "start": 3.6, "end": 9.0}]  # fmt: skip
    assert (watch_cut.count_for(6), watch_cut.count_for(20), watch_cut.count_for(90)) == (
        16,
        20,
        24,
    )
    frames = watch_cut.frames_at(9.0, [3.6], WORDS, spans, 16)
    assert len(frames) == 16 and [f["t"] for f in frames] == sorted(f["t"] for f in frames)
    labels = {f["t"]: (f["clip_id"], f["label"]) for f in frames}
    assert labels[3.75] == ("c2", "a shot starts")  # just after the cut
    assert labels[4.65] == ("c2", 'the word "Get"') and labels[7.15][1] == 'the word "Ugh!"'
    assert labels[0.0] == ("c1", "even spacing")


def test_only_findings_the_director_can_act_on_reach_it():
    found = {"findings": [
        {"clip_id": "c2", "start": 6.9, "end": 7.5, "says": "c2: a groan", "fix": "mute",
         "note": "Ugh!"},
        {"clip_id": "c2", "start": 4.4, "end": 5.4, "says": "c2: the line", "fix": "mute"},
        {"clip_id": "c1", "start": 3.5, "end": 4.5, "says": "across", "fix": "mute"},
        {"clip_id": "c1", "start": 0, "end": 4, "says": "c1: better", "fix": "pick", "take_id": 7},
        {"clip_id": "c1", "start": 0, "end": 4, "says": "c1: no such", "fix": "pick", "take_id": 9},
        {"clip_id": "c2", "start": 4, "end": 9, "says": "c2: face", "fix": "redo",
         "take_id": 7, "note": "Keep her face as on her sheet."},
    ]}  # fmt: skip
    kept = watch_cut.checked(found, CUT, WORDS, "MIA: Get fomo.")
    assert [(f["says"], f["fix"]) for f in kept] == [
        ("c2: a groan", "mute"),
        ("c1: better", "pick"),
        ("c2: face", "redo"),
    ]
    groan, pick, redo = kept
    assert groan["mute"] == [2.9, 3.5]  # in c2's own take seconds, for POST …/mute
    assert (pick["take_id"], pick["mute"]) == (7, None) and redo["take_id"] is None
    nowhere = {"clip_id": "c3", "start": 0, "end": 1, "says": "nowhere", "fix": "redo"}
    assert watch_cut.checked({"findings": [nowhere]}, CUT, WORDS, "") == []
    old = watch_cut.checked({"findings": [{**found["findings"][3], "fix": "other_take"}]},
                            CUT, WORDS, "")  # fmt: skip
    assert old[0]["fix"] == "pick"  # the schema's first name, said as the director reads it


def test_the_director_watches_its_cut_and_reads_what_to_fix(app, db, editor, setup, clip):  # noqa: F811
    project = db.get(Project, setup["project"])
    user = db.query(User).filter_by(email=editor.get("/auth/me").json()["email"]).one()
    with pytest.raises(HTTPException, match="Make the cut first."):
        watch_cut.start(db, user, project, None)
    base = f"/projects/{setup['project']}"
    editor.post(f"{base}/clips/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    editor.post(f"{base}/clips/{clip['id']}/approve")
    assert editor.post(f"{base}/video").status_code == 201
    run = {"id": "r1", "turn": 3, "redos": {}}
    assert watch_cut.start(db, user, project, run) == "Watching the cut."
    db.commit()
    assert watch_cut.state(db, project)["state"] == "watching"
    run_once(db, {"local": LocalProvider(app.state.storage, hear_cut=hear_cut)},
             app.state.storage, only={"local"})  # fmt: skip
    look = db.query(Job).filter(Job.kind == "check-claude").order_by(Job.id.desc()).first()
    assert look.input["step"] == "watch_cut" and look.input["director_run"] == run
    assert len(look.input["files"]["reference_images"]) == 16  # a 1 s cut: the fewest
    assert "[Image1] c1 at 0.0 s" in look.input["prompt"] and "<cut>" in look.input["prompt"]
    assert look.credits > 0  # priced "up to", on the director's own limit
    run_writer(app, db)
    db.expire_all()
    watch = watch_cut.state(db, project)
    assert (watch["state"], watch["current"], watch["lands"]) == ("done", True, True)
    redo, mute = watch["findings"]
    assert (redo["clip_id"], redo["fix"], redo["mute"]) == ("c1", "redo", None)
    start, end = mute["mute"]  # in c1's take seconds, half a second
    assert mute["fix"] == "mute" and 0 < start and round(end - start, 2) == 0.5
    editor.post(f"{base}/clips/{clip['id']}/generate")  # a new take: the cut is out of date
    _work(app, db, FakeSeedance([_mp4("blue")]))
    db.expire_all()
    assert watch_cut.state(db, project)["current"] is False
