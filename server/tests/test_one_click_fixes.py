"""No dead ends (Reed, 2026-10-26, DECISIONS #520; spec one-click-fixes.md): every blocking
problem has a free one-click fix, or the server repairs it, or it's advice."""

import copy

from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import LibraryItem
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture


def _saved(editor, setup, bd):  # noqa: F811
    url = f"/projects/{setup['project']}/breakdown"
    editor.post(url)
    return url


def test_breakdown_problems_have_a_free_fix(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/breakdown"
    editor.post(url)
    _run(app, db, FakeClaude(BREAKDOWN))
    bad = copy.deepcopy(BREAKDOWN)
    shots = bad["scenes"][0]["shots"]
    shots[0]["line"] = "Nate where is your cash?"  # changed
    shots[1]["script_lines"] = []  # line 4 is in no shot
    bad["clips"][0]["shot_ids"] = ["1.1"]  # the clips miss shot 1.2
    got = editor.put(url, json=bad).json()
    kinds = {f["problem"]: f["kind"] for f in got["fixes"]}
    assert kinds == {
        "line 4 is in no shot": "add_line",
        "shot 1.2: line differs from the script": "restore_line",
        "shot 1.1: line differs from the script": "restore_line",
        "clips don't cover the shots once each, in order": "recover_clips",
    }
    jobs = db.query(Job).count()
    one = editor.post(f"{url}/fix", json={"problems": ["line 4 is in no shot"]}).json()
    assert one["fixed"] == ["Put line 4 in shot 1.2."]  # the shot that says it
    assert "line 4 is in no shot" not in one["problems"]
    assert "shot 1.2: line differs from the script" not in one["problems"]  # the same fix
    assert "shot 1.1: line differs from the script" in one["problems"]
    every = editor.post(f"{url}/fix").json()  # all the rest
    assert every["fixed"] == ["Put the script's words back in shot 1.1.",
                              "Fitted the clips to the shots."]  # fmt: skip
    assert every["fixes"] == []
    fixed = every["breakdown"]
    assert fixed["scenes"][0]["shots"][0]["line"] == "Nate, where is all your money?"
    assert fixed["clips"][0]["shot_ids"] == ["1.1", "1.2"]
    assert db.query(Job).count() == jobs  # free: no model call
    again = editor.post(f"{url}/fix")
    assert again.status_code == 409 and "Edit the shot" in again.json()["detail"]
    undo = editor.put(url, json=bad)  # Undo is PUT of the breakdown it had
    assert undo.json()["breakdown"]["clips"][0]["shot_ids"] == ["1.1"]


def test_a_name_the_video_doesnt_have_is_taken_out(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}"
    mia = editor.post("/library/character", json={"name": "Mia"}).json()["id"]  # not cast
    made = copy.deepcopy(BREAKDOWN)
    made["scenes"][0]["shots"][1]["character_ids"] = [f"char:{mia}"]
    editor.post(f"{url}/breakdown")
    _run(app, db, FakeClaude(made))
    got = editor.get(f"{url}/breakdown").json()
    assert got["breakdown"]["scenes"][0]["shots"][1]["character_ids"] == []
    assert ("Advice: Removed Mia from shot 1.2. Nobody by that name is in this video."
            in got["problems"])  # fmt: skip
    editor.patch(url, json={"cast_ids": [mia]})  # cast now: the editor puts Mia back
    with_mia = copy.deepcopy(BREAKDOWN)
    with_mia["scenes"][0]["shots"][1]["character_ids"] = [f"char:{mia}"]
    editor.put(f"{url}/breakdown", json=with_mia)
    out = editor.post(f"{url}/shots/1.2/remove-ref", json={"kind": "character", "name": "Mia"})
    assert out.status_code == 200, out.text
    assert out.json()["fixed"] == ["Removed Mia from shot 1.2."]
    assert out.json()["breakdown"]["scenes"][0]["shots"][1]["character_ids"] == []
    gone = editor.post(f"{url}/shots/1.2/remove-ref", json={"kind": "character", "name": "Mia"})
    assert gone.status_code == 409 and "char:" not in gone.json()["detail"]
    assert editor.post(f"{url}/shots/9.9/remove-ref",
                       json={"kind": "place", "name": "x"}).status_code == 404  # fmt: skip
    rows = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).count()
    assert rows == 3  # Claude's, the edit, the removal: Undo is PUT of the one before


def test_a_role_whose_character_was_deleted_says_so(owner, editor, db):
    from tests.test_video_looks import _row, _video

    _, pid, nate = _video(owner, editor, db)
    kid = editor.post("/library/character", json={"name": "Kid"}).json()["id"]
    editor.put(f"/projects/{pid}/assets/slots/{nate}", json={"library_item_id": kid})
    assert _row(editor, pid, nate)["library_deleted"] is False
    db.get(LibraryItem, kid).archived = True
    db.commit()
    assert _row(editor, pid, nate)["library_deleted"] is True  # Make a look, or Pick another


def test_too_many_pictures_never_blocks_once_repaired(app, db, editor, setup, monkeypatch):  # noqa: F811
    from app import storyboard
    from app.models.storyboards import StoryboardFrame
    from tests.test_frame_sheets import _people

    row, nate, mom = _people(app, db, editor, setup)
    screen = f"screen:{setup['screen']}"
    frame = StoryboardFrame(project_id=setup["project"], breakdown_id=row.id, clip_id="c1",
                            shot_id="1.1", prompt="Mom in image 1, Nate in image 2, the app "
                            "in image 3.", reference_ids=[mom, nate, screen])  # fmt: skip
    db.add(frame)
    db.commit()
    two = storyboard.image_model().model_copy(update={"max_reference_images": 2})
    monkeypatch.setattr(storyboard, "image_model", lambda: two)
    shown = editor.get(f"/projects/{setup['project']}/storyboard").json()[0]
    assert shown["reference_ids"] == [mom, screen]  # the nearest person, and the screen
    assert "Nate in Nate" in shown["prompt"] and "image 2." in shown["prompt"]
    assert not [p for p in shown["problems"] if "references" in p]
    left = "Advice: Left out Nate: the model takes 2 pictures, nearest the camera first."
    assert left in shown["problems"]
    again = editor.get(f"/projects/{setup['project']}/storyboard").json()[0]
    assert left in again["problems"]  # still said the next time it's opened


def test_opening_clips_attaches_sheets_approved_since(app, db, editor, setup):  # noqa: F811
    from app.models.clips import ProjectClip
    from tests.test_clip_sheets import _clip
    from tests.test_frame_sheets import _people

    row, nate, mom = _people(app, db, editor, setup)
    old = _clip(f"screen:{setup['screen']}")
    db.add(ProjectClip(project_id=setup["project"], breakdown_id=row.id, clip_id="c1",
                       seconds=5, prompt=old.prompt, problems=["Nate has no approved look yet."],
                       references=[r.model_dump() for r in old.references]))  # fmt: skip
    db.commit()
    (shown,) = editor.get(f"/projects/{setup['project']}/clips").json()
    assert [r["id"] for r in shown["references"]][1:3] == [mom, nate]
    assert "Nate has no approved look yet." not in shown["problems"]


def test_a_versions_plan_has_the_same_free_fixes(owner):
    from tests.test_script_library import SCRIPT, _make

    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/drafts/0/breakdown"
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["script_lines"] = [2]
    bd["scenes"][0]["shots"][1]["script_lines"] = []  # line 3 ("I bought the dip.") in none
    got = owner.put(url, json=bd).json()
    assert {"problem": "line 3 is in no shot", "kind": "add_line",
            "label": "Add it to a shot"} in got["fixes"]  # fmt: skip
    fixed = owner.post(f"{url}/fix").json()
    assert fixed["fixed"] == ["Put line 3 in shot 1.2."]
    assert fixed["breakdown"]["scenes"][0]["shots"][1]["script_lines"] == [3]
    assert "line 3 is in no shot" not in fixed["problems"]


def test_edit_shot_can_name_what_the_video_doesnt_have(app, db, editor, outsider, setup):  # noqa: F811
    """Designer, §2: "Remove Mia from this shot", never another workspace's name."""
    from tests.conftest import upload

    url = f"/projects/{setup['project']}/breakdown"
    editor.post(url)
    _run(app, db, FakeClaude(BREAKDOWN))
    mia = editor.post("/library/character", json={"name": "Mia"}).json()["id"]  # not cast
    rival = outsider.post(
        "/library/character", json={"name": "Secret Rival", "image_file_ids": [upload(outsider)]}
    ).json()["id"]
    row = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).one()
    data = copy.deepcopy(row.data)
    data["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mia}", f"char:{rival}"]
    row.data = data
    db.commit()
    assert editor.get(url).json()["unknown_names"] == {
        f"char:{mia}": "Mia",
        f"char:{rival}": "an unnamed character",  # another workspace's: said for what it is
    }
