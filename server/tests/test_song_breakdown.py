"""Song ads: the breakdown timed to the video's song, kept beside the plan, carried by edits
and moved for free when the video's take changes (stand-ins only, no paid calls)."""

import copy

from sqlalchemy import select

from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.songs import SongTake
from tests.test_song_takes import _video, _work, song  # noqa: F401 - fixture


def _rows(db, video):
    pid = int(video.rsplit("/", 1)[1])
    return db.scalars(select(BreakdownVersion).where(BreakdownVersion.project_id == pid)
                      .order_by(BreakdownVersion.id)).all()  # fmt: skip


def test_a_song_videos_plan_is_timed_to_its_song(app, db, owner, editor, song):  # noqa: F811
    video = _video(app, db, owner, editor, song)  # its breakdown runs on making the video
    job = db.scalar(select(Job).where(Job.input["step"].as_string() == "song_breakdown"))
    assert job is not None and "<song seconds=" in job.input["prompt"]
    row = _rows(db, video)[-1]
    timed = row.data["song"]
    take = editor.get(f"{video}/songs").json()["song_take_id"]
    assert timed["take_id"] == take
    shots = [s["id"] for scene in row.data["scenes"] for s in scene["shots"]]
    edges = [timed["shots"][s] for s in shots]
    assert edges[0]["start"] == 0 and all(not e["sung"] for e in edges)
    assert all(a["end"] == b["start"] for a, b in zip(edges, edges[1:], strict=False))
    plan = editor.get(f"{video}/breakdown").json()  # every other step reads the plain plan
    assert "song_start" not in str(plan["breakdown"])
    assert plan["song"]["take_id"] == take and set(plan["song"]["shots"]) == set(shots)


def test_an_edit_keeps_the_song_part(app, db, owner, editor, song):  # noqa: F811
    video = _video(app, db, owner, editor, song)
    plan = editor.get(f"{video}/breakdown").json()["breakdown"]
    plan["hook"] = "A new hook."
    assert editor.put(f"{video}/breakdown", json=plan).status_code == 200
    first, edited = _rows(db, video)[-2:]
    assert edited.data["hook"] == "A new hook." and edited.data["song"] == first.data["song"]


def test_a_new_take_moves_the_shots_free_and_undo_moves_them_back(
    app,
    db,
    owner,
    editor,
    song,  # noqa: F811
):
    video = _video(app, db, owner, editor, song)
    project = db.get(Project, int(video.rsplit("/", 1)[1]))
    draft = db.get(ScriptDraft, project.script_draft_id)
    draft.style_line = "pop fake:long=40"  # only to make a longer take on the stand-in
    db.commit()
    editor.post(f"{video}/songs", json={})
    _work(app, db)
    draft.style_line = "pop"  # back as it was, so the first take sings the current words
    longest = db.query(SongTake).order_by(SongTake.id.desc()).first()
    longest.style_line = "pop"  # (the long take stands in for another take of them)
    db.commit()
    songs = editor.get(f"{video}/songs").json()
    first, longer = songs["song_take_id"], songs["takes"][-1]["id"]
    paid = db.query(Job).count()
    assert editor.put(f"{video}/song", json={"take_id": longer}).status_code == 200
    moved = _rows(db, video)[-1].data["song"]
    assert moved["take_id"] == longer and db.query(Job).count() == paid  # no model call
    ends = sorted(s["end"] for s in moved["shots"].values())
    assert ends[-1] > 39  # the shots now run to the longer take's end
    r = editor.put(f"{video}/song", json={"take_id": first})  # Undo
    assert r.status_code == 200, r.text
    assert _rows(db, video)[-1].data["song"]["take_id"] == first


def test_clips_made_for_the_old_take_go_out_of_date_and_undo_brings_them_back(
    app,
    db,
    owner,
    editor,
    song,  # noqa: F811
):
    from app.models.clips import ProjectClip

    video = _video(app, db, owner, editor, song)
    project = db.get(Project, int(video.rsplit("/", 1)[1]))
    made = _rows(db, video)[-1]
    clip = made.data["clips"][0]
    db.add(ProjectClip(project_id=project.id, breakdown_id=made.id, clip_id=clip["id"],
                       seconds=clip["seconds"], prompt="A test clip."))  # fmt: skip
    draft = db.get(ScriptDraft, project.script_draft_id)
    draft.style_line = "pop fake:long=40"
    db.commit()
    editor.post(f"{video}/songs", json={})
    _work(app, db)
    draft.style_line = "pop"
    longest = db.query(SongTake).order_by(SongTake.id.desc()).first()
    longest.style_line = "pop"
    db.commit()
    first = editor.get(f"{video}/songs").json()["song_take_id"]
    editor.put(f"{video}/song", json={"take_id": longest.id})
    row = db.scalar(select(ProjectClip))
    db.refresh(row)
    assert row.breakdown_id == made.id != _rows(db, video)[-1].id  # out of date
    editor.put(f"{video}/song", json={"take_id": first})  # Undo: the clip is current again
    db.refresh(row)
    assert row.breakdown_id == _rows(db, video)[-1].id


def test_a_shot_whose_line_wasnt_heard_says_its_timing_is_guessed(
    app,
    db,
    owner,
    editor,
    song,  # noqa: F811
):
    video = _video(app, db, owner, editor, song)
    project = db.get(Project, int(video.rsplit("/", 1)[1]))
    draft = db.get(ScriptDraft, project.script_draft_id)
    draft.style_line = "pop fake:drop-line"  # a take that doesn't sing the last line
    db.commit()
    editor.post(f"{video}/songs", json={})
    _work(app, db)
    draft.style_line = "pop"
    dropped = db.query(SongTake).order_by(SongTake.id.desc()).first()
    dropped.style_line = "pop"  # (stands in for another take of the current words)
    db.commit()
    assert editor.put(f"{video}/song", json={"take_id": dropped.id}).status_code == 200
    plan = editor.get(f"{video}/breakdown").json()
    flags = {sid: s["guessed"] for sid, s in plan["song"]["shots"].items()}
    assert any(flags.values()) and not all(flags.values())


def test_the_reflow_keeps_shots_on_their_lines():
    from app.song_breakdown import reflow

    old = {"seconds": 20, "lines": [{"start": 2, "end": 6}, {"start": 8, "end": 12}]}
    new = {"seconds": 30, "lines": [{"start": 3, "end": 10}, {"start": 14, "end": 20}]}
    part = {"take_id": 1, "shots": {"1.1": {"start": 0, "end": 8, "sung": False},
                                    "1.2": {"start": 8, "end": 10, "sung": True},
                                    "1.3": {"start": 10, "end": 20, "sung": False}}}  # fmt: skip
    moved = reflow(part, old, new, 2)["shots"]
    assert [(moved[s]["start"], moved[s]["end"]) for s in ("1.1", "1.2", "1.3")] == [
        (0, 14),
        (14, 17),
        (17, 30),  # line 2 starts at 14 in the new take; 10 is its middle
    ]
    assert moved["1.2"]["sung"] is True


def test_deleting_or_adding_a_shot_repacks_the_song_free_and_undo_is_exact(
    app,
    db,
    owner,
    editor,
    song,  # noqa: F811
):
    video = _video(app, db, owner, editor, song)
    original = editor.get(f"{video}/breakdown").json()
    plan, times = original["breakdown"], original["song"]["shots"]
    shots = plan["scenes"][0]["shots"]
    assert len(shots) >= 3
    gone = shots[1]["id"]
    deleted = copy.deepcopy(plan)
    deleted["scenes"][0]["shots"].pop(1)
    for clip in deleted["clips"]:
        clip["shot_ids"] = [s for s in clip["shot_ids"] if s != gone]
    out = editor.put(f"{video}/breakdown", json=deleted).json()
    after = out["song"]["shots"]
    nxt = shots[2]["id"]
    assert after[nxt]["start"] == times[gone]["start"]  # the next shot takes its time
    assert not [p for p in out["problems"] if "back to back" in str(p)]

    added = copy.deepcopy(plan)
    extra = {**copy.deepcopy(shots[0]), "id": "1.99"}
    added["scenes"][0]["shots"].insert(1, extra)
    added["clips"][0]["shot_ids"].insert(1, "1.99")
    out = editor.put(f"{video}/breakdown", json=added).json()
    timed = out["song"]["shots"]
    assert timed["1.99"]["end"] > timed["1.99"]["start"] == timed[shots[0]["id"]]["end"]
    assert not [p for p in out["problems"] if "back to back" in str(p)]

    back = editor.put(f"{video}/breakdown", json=plan).json()  # Undo: the plan as it was
    assert {k: (v["start"], v["end"]) for k, v in back["song"]["shots"].items()} == {
        k: (v["start"], v["end"]) for k, v in times.items()
    }


def test_a_sung_clip_goes_out_of_date_on_any_take_change(app, db, owner, editor, song):  # noqa: F811
    from app.models.clips import ProjectClip

    video = _video(app, db, owner, editor, song)
    project = db.get(Project, int(video.rsplit("/", 1)[1]))
    made = _rows(db, video)[-1]
    data = copy.deepcopy(made.data)
    clip = data["clips"][0]
    for sid in clip["shot_ids"]:
        data["song"]["shots"][sid]["sung"] = True
    made.data = data
    db.add(ProjectClip(project_id=project.id, breakdown_id=made.id, clip_id=clip["id"],
                       seconds=clip["seconds"], prompt="A sung clip."))  # fmt: skip
    db.commit()
    takes = editor.get(f"{video}/songs").json()["takes"]
    first, other = takes[0]["id"], takes[1]["id"]  # the same stand-in song: nothing moves
    editor.put(f"{video}/song", json={"take_id": other})
    row = db.scalar(select(ProjectClip))
    db.refresh(row)
    assert row.breakdown_id == made.id  # out of date: it sings the other take
    editor.put(f"{video}/song", json={"take_id": first})  # Undo
    db.refresh(row)
    assert row.breakdown_id == _rows(db, video)[-1].id
