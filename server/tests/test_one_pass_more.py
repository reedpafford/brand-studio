"""What else the one-pass director makes (app/one_pass.py): a reel's remake and a video in a
reel's look, a finished video's variations, and the owner's "Change the line", none of which
plans the whole video again. On the stand-ins."""

import pytest

from app import line_change, one_pass
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.models.scripts import ScriptVersion
from app.models.songs import SongTake
from tests.helpers import make_it
from tests.test_one_pass import BODY, SCRIPT
from tests.test_one_pass_narrated import NARRATION, _delivered, _jobs, _run, _video
from tests.test_reel_read import _ready, clip  # noqa: F401  (the module's reel)


@pytest.fixture(autouse=True)
def _one_pass_on(monkeypatch):
    from app.settings import get_settings

    monkeypatch.setattr(get_settings(), "one_pass", True)
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)  # as on the stand-ins


def _takes(db, pid: int) -> dict[str, int]:
    return {r.clip_id: db.query(ClipTake).filter_by(clip_id=r.id).count()
            for r in db.query(ProjectClip).filter_by(project_id=pid)}  # fmt: skip


def test_a_reels_remake_is_planned_in_one_pass_with_the_reel_shot_by_shot(app, owner, db):
    from tests.test_script_library import _make

    made = _make(owner, text=SCRIPT, reference_id="fomo-DehudnaAmce")
    r = owner.post("/freestyles", json={"shape": "9:16", "script_id": made["id"], "slot": 0})
    assert r.status_code == 201, r.text
    _run(app, db, ticks=3, start=False)
    video = _video(db)
    assert video.engine == one_pass.ENGINE and video.reference_breakdown
    said = _jobs(db, "one_pass")[0].input["prompt"]
    assert "<reference>\nStory: " in said and "Shots (time, framing, camera" in said
    assert one_pass.REMAKE in said and "Copy it shot by shot" in said


def test_a_video_in_a_reels_look_is_given_its_facts_and_its_contact_sheet(
    app,
    owner,
    db,
    clip,  # noqa: F811
):
    sid = int(_ready(app, owner, db, clip).rsplit("/", 1)[1])
    made = owner.post("/freestyles/reel", json={
        "script_id": sid, "mode": "look", "type": "dialogue", "look": "house", "shape": "9:16",
        "text": SCRIPT})  # fmt: skip
    assert made.status_code == 201, made.text
    _run(app, db, ticks=3, start=False)
    video = db.get(Project, made.json()["project_id"])
    assert video.engine == one_pass.ENGINE and video.reel_script_id == sid
    plan = _jobs(db, "one_pass")[0].input
    assert "<look_reference>\nThis video is made in the look of the reel" in plan["prompt"]
    assert "Never its words or its story. The last image given is its contact sheet." in plan[
        "prompt"]  # fmt: skip
    assert len(plan["files"]["reference_images"]) == 1 and "<reference>" not in plan["prompt"]


def test_a_variation_is_a_one_pass_video_that_remakes_only_its_named_clip(app, owner, db):
    fs = owner.post("/freestyles", json=BODY)
    _run(app, db)
    pid = _video(db).id
    assert owner.get(f"/freestyles/{fs.json()['id']}").json()["status"] == "delivered"
    assert not owner.get(f"/projects/{pid}/variations").json()["blocked"]
    asked = owner.post(f"/projects/{pid}/variations", json={"count": 2, "part": "hook"})
    assert asked.status_code == 201, asked.text
    _run(app, db, ticks=8, start=False)  # written; each copy plans its change, then its card
    copies = [v["id"] for v in owner.get(f"/projects/{pid}/variations").json()["videos"]]
    assert len(copies) == 2 and pid not in copies
    for vid in copies:
        video = db.get(Project, vid)
        assert video.engine == one_pass.ENGINE  # copied with its engine: never the other path
        (again,) = [j for j in _jobs(db, "one_pass") if j.project_id == vid]
        assert "<notes>" in again.input["prompt"] and "<plan>" in again.input["prompt"]
        assert "is variation " in again.input["prompt"]
    make_it(db)
    _run(app, db)
    for vid in copies:
        out = owner.get(f"/projects/{vid}/director").json()
        assert out["status"] == "delivered", out["ended"]
        assert _takes(db, vid) == {"c1": 1, "c2": 1, "c3": 1}  # c1 made, the others copied
        assert len([j for j in _jobs(db, "clip_take") if j.project_id == vid]) == 1
    assert _takes(db, pid) == {"c1": 1, "c2": 1, "c3": 1}  # the source's own stay


def test_the_owner_changes_a_line_and_no_call_plans_anything_again(app, owner, db):
    pid = _delivered(app, owner, db, **BODY)
    before = _takes(db, pid)
    said = owner.post(f"/projects/{pid}/director/messages",
                      json={"text": "Change “ready for that” to “ready at all”"})  # fmt: skip
    assert said.status_code == 201, said.text
    card = next(a for a in owner.get(f"/projects/{pid}/asks").json() if a["kind"] == "instead")
    change = next(c for c in card["choices"] if c["do"] == line_change.DO)
    assert "Only clip 2 is made again, then the cut" in change["why"]
    pressed = owner.post(f"/asks/{card['id']}/answer",
                         json={"how": "instead", "choice": change["key"]})  # fmt: skip
    assert pressed.status_code == 200, pressed.text
    _run(app, db, start=False)  # no start card: the owner's press was the OK
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert len(_jobs(db, "one_pass")) == 1  # the same plan: the words go in by their number
    assert _takes(db, pid) == {**before, "c2": 2}  # only the line's clip
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c2").one()
    assert '"We were not ready at all."' in row.prompt
    newest = db.query(ScriptVersion).filter_by(project_id=pid).order_by(
        ScriptVersion.version.desc()).first()  # fmt: skip
    assert newest.source == "owner_line" and "LEO: We were not ready at all." in newest.text
    spent = sum(j.credits for j in _jobs(db, "clip_take")[3:]) + _jobs(db, "watch_cut")[-1].credits
    assert spent <= change["price"]["credits"]  # rule 36: never past the price on the card


def test_a_narrated_line_is_read_again_and_the_shots_follow_it_unplanned(app, owner, db):
    pid = _delivered(app, owner, db)
    old = db.query(SongTake).one()
    owner.post(f"/projects/{pid}/director/messages",
               json={"text": "Change “tell a friend” to “tell a neighbour”"})  # fmt: skip
    card = next(a for a in owner.get(f"/projects/{pid}/asks").json() if a["kind"] == "instead")
    change = next(c for c in card["choices"] if c["do"] == line_change.DO)
    assert "and the narration are made again" in change["why"]
    pressed = owner.post(f"/asks/{card['id']}/answer",
                         json={"how": "instead", "choice": change["key"]})  # fmt: skip
    assert pressed.status_code == 200, pressed.text
    _run(app, db, start=False)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    project = db.get(Project, pid)
    take = db.get(SongTake, project.song_take_id)
    assert take.id != old.id and "tell a neighbour" in take.lyrics and take.voice == old.voice
    assert len(_jobs(db, "one_pass")) == 1  # read again, never planned again
    from app.clip_prompts import newest

    row = newest(db, project)
    assert row.data["song"]["take_id"] == take.id and row.data[one_pass.PLAN]
    assert all(c.breakdown_id == row.id and c.picked_take_id
               for c in db.query(ProjectClip).filter_by(project_id=pid))  # fmt: skip
    assert NARRATION  # the script's own version keeps its words


def test_a_ugc_b_roll_clip_can_be_the_brands_own_footage_cut_free(app, owner, db):
    from app import footage, footage_shot
    from app.clip_prompts import newest
    from app.models.jobs import Job
    from tests.test_footage import _described

    clip_id = _described(app, db, owner, 1)
    pid = _delivered(app, owner, db, type="presenter", look="ugc")
    plan = _jobs(db, "one_pass")[0].input
    assert f"- {footage.KEY}{clip_id} | " in plan["system"][-1]
    assert "set the clip's `footage` to the footage's id and `footage_at`" in plan["system"][-1]
    assert plan["files"]["reference_images"]  # a frame of it, to look at
    project = db.get(Project, pid)
    ((real, use),) = footage_shot.uses(newest(db, project).data).items()
    assert use == {"id": f"{footage.KEY}{clip_id}", "start": 0.0, "end": 3.0, "sound": False}
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id=real).one()
    made = db.get(Job, db.get(ClipTake, row.picked_take_id).job_id)
    assert (made.kind, made.provider, made.credits) == (footage_shot.TAKE, "local", 0)
    assert row.prompt.startswith(footage_shot.HEAD)  # never written, never made
    assert len(_jobs(db, "clip_take")) == 1  # only the talker's own clip is made
    note = _jobs(db, "director")[-1].output["note"]
    assert f"Clip {real.removeprefix('c')} is the brand's own footage, cut from it." in note["made"]
