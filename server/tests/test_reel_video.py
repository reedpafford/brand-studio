"""Use a reel (v6 S2-07, S-gaps-01 option 2): Copy it shot by shot or Just its structure read
the reel at its own price and make the video at once in the open folder; once its script is
written the director's run waits for the owner's OK, nothing past the read spent. Just its
look makes your words with the reel as the director's look reference. Stand-ins only."""

from app import director
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import Script
from app.routes import reel_video
from tests.test_freestyle_dialogue import SCRIPT
from tests.test_reel_read import _drain, _ready, clip  # noqa: F401  (the module's reel)


def _sid(url: str) -> int:
    return int(url.rsplit("/", 1)[1])


def test_copy_reads_the_reel_then_the_run_waits_for_the_owners_ok(app, owner, db, clip):  # noqa: F811
    sid = _sid(_ready(app, owner, db, clip))
    folder = owner.post(f"/brands/{owner.get('/brands').json()[0]['id']}/folders",
                        json={"name": "Week of 3 Nov"}).json()["id"]  # fmt: skip
    est = owner.get("/freestyles/reel/estimate", params={"script_id": sid}).json()
    assert est["ready"] and est["credits"] == 7 and est["usd"] >= 0.71
    body = {"script_id": sid, "mode": "copy", "type": "dialogue", "look": "house",
            "shape": "9:16", "folder_id": folder}  # fmt: skip
    fs = owner.post("/freestyles/reel", json=body)
    assert fs.status_code == 201, fs.text
    out = fs.json()
    assert out["status"] == "working" and out["reel_script_id"] == sid and out["thread"] == []
    video = db.get(Project, out["project_id"])
    assert video.folder_id == folder and not video.hidden  # in the open folder, at once
    assert not db.get(Script, sid).new_lines  # copy: its own lines
    again = owner.post("/freestyles/reel", json=body)
    assert again.status_code == 409 and again.json()["detail"] == reel_video.READ_ALREADY
    _drain(app, db)
    db.expire_all()
    done = owner.get(f"/freestyles/{out['id']}").json()
    assert done["status"] == "waiting", done["thread"]  # the run waits for the owner's OK
    (turn,) = [j for j in db.query(Job).filter(Job.project_id == video.id)]
    assert turn.status == JobStatus.needs_owner_approval and turn.credits >= 0
    assert done["thread"][0]["text"].endswith("copy it shot by shot.") and done["up_to"] > 0
    assert owner.post(f"/jobs/{turn.id}/approve").status_code == 200  # Make it: it starts


def test_structure_writes_new_lines_and_look_keeps_your_words(app, owner, db, clip):  # noqa: F811
    sid = _sid(_ready(app, owner, db, clip))
    body = {"script_id": sid, "type": "dialogue", "look": "house", "shape": "9:16"}
    owner.post("/freestyles/reel", json={**body, "mode": "structure"})
    assert db.get(Script, sid).new_lines  # new lines on the same beats
    other = _sid(_ready(app, owner, db, clip))
    words = owner.post("/freestyles/reel", json={**body, "script_id": other, "mode": "look"})
    assert words.status_code == 422 and words.json()["detail"] == reel_video.WORDS
    made = owner.post("/freestyles/reel", json={**body, "script_id": other, "mode": "look",
                                                "text": SCRIPT}).json()  # fmt: skip
    video = db.get(Project, made["project_id"])
    assert video.reel_script_id == other and made["status"] == "working"  # your words, now
    ref = reel_video.look_reference(db, video)
    assert (
        ref["shots"] >= 1 and ref["contact_sheet_file_id"] and "Never use its words" in ref["use"]
    )
    prompt = director.turn_input(db, video, {"id": "r", "turn": 0, "redos": {}})["prompt"]
    assert "<look_reference>" in prompt


def test_a_reels_picks_are_checked_at_the_press_before_the_read_is_paid(app, owner, db, clip):  # noqa: F811
    sid = _sid(_ready(app, owner, db, clip))
    body = {"script_id": sid, "mode": "copy", "type": "dialogue", "look": "house", "shape": "9:16"}
    flat = owner.post("/freestyles/reel", json={**body, "broll_look": "skeleton"})
    assert flat.status_code == 409  # no host: no B-roll look of its own
    bad = owner.post("/freestyles/reel", json={**body, "attachments": [999]})
    assert bad.status_code == 404
    assert not db.query(Job).filter(Job.input["reel_step"].as_string().is_not(None)).count()
