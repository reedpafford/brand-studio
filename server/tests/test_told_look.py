"""The director's make_looks for someone it names (video 294: four tries for Maya and three for
Bruno drew nothing, as neither was a role, then the owner had to upload a frame of the cut). No
paid calls: the stand-ins only."""

import copy
import json

from app import director, director_tools
from app.models.accounts import User
from app.models.asks import Ask
from app.models.breakdowns import BreakdownVersion
from app.models.clips import FinalVideo, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot
from tests.conftest import upload
from tests.helpers import approve_cast
from tests.test_breakdown import BREAKDOWN
from tests.test_cast_gate import _drawn, _nate, _two_clips
from tests.test_clip_takes import _mp4
from tests.test_director import _made, _run, started
from tests.test_script_library import _make
from tests.test_video_looks import _video as _nate_video

SCRIPT = "SCENE 1 — INT. KITCHEN — DAY\nBruno sniffs his bowl."  # Maya is no role


def _video(owner, editor, action: str) -> int:
    """A video whose shot 1.1 does `action`, and whose script has no role at all."""
    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["action"] = action
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return editor.post(f"{base}/drafts/0/produce").json()["project_id"]


def _make_looks(db, pid, look, storage=None) -> str:
    user = db.query(User).filter_by(email="ed@example.com").one()
    move = {"tool": "make_looks", "look": look}
    said = director_tools.run(db, user, db.get(Project, pid), move, storage)
    db.commit()
    return said


def _looked(db, pid, name) -> tuple[LibraryItem, Job, list[str]]:
    """`name`'s look, its sheet job, and the shots that show them."""
    db.expire_all()
    look = db.query(LibraryItem).filter_by(owner_project_id=pid, name=name).one()
    sheet = next(j for j in db.query(Job).all() if j.input.get("library_item_id") == look.id)
    bd = db.query(BreakdownVersion).filter_by(project_id=pid).order_by(BreakdownVersion.id.desc())
    shots = bd.first().data["scenes"][0]["shots"]
    return look, sheet, [s["id"] for s in shots if f"char:{look.id}" in s["character_ids"]]


def test_someone_who_isnt_a_role_is_made_one_and_drawn_in_the_same_move(owner, editor, db):
    pid = _video(owner, editor, "Maya, 30s, opens the bag.")
    said = _make_looks(db, pid, {"name": "Maya", "description": "a messy bun, grey sleep tee"})
    assert said == "Making the missing looks."
    look, sheet, shots = _looked(db, pid, "Maya")
    prompt = sheet.input["input"]["prompt"]
    assert "opens the bag" in prompt and "a messy bun, grey sleep tee" in prompt  # both words
    assert shots == ["1.1"]
    # nobody's words name him: he's put in the shots the director gives
    rex = {"name": "Rex", "description": "a scruffy grey terrier", "shot_ids": ["1.2"]}
    assert _make_looks(db, pid, rex) == "Making the missing looks."
    assert _looked(db, pid, "Rex")[2] == ["1.2"]


def test_a_look_pointed_at_a_moment_of_the_cut_is_drawn_from_that_frame(app, owner, editor, db):
    pid = _video(owner, editor, "Maya opens the bag.")
    cut = upload(editor, "cut.mp4", _mp4("red"), "video/mp4")
    db.add(FinalVideo(project_id=pid, file_id=cut, take_ids=[]))
    db.commit()
    maya = {"name": "Maya", "description": "the woman who opens the bag at 0.5 s in the cut"}
    assert _make_looks(db, pid, maya, app.state.storage) == "Making the missing looks."
    look, sheet, _ = _looked(db, pid, "Maya")
    photo = db.get(StoredFile, look.source_photo_file_id)
    assert photo.content_type == "image/png" and photo.id != cut  # a frame of it, free
    assert sheet.input["files"]["image_input"] == [photo.id]  # her sheet is drawn from it


def test_one_person_is_never_made_a_second_role(owner, editor, db):
    """Rule 9 (QA on #1483): "Maya Chen", "Bruno's owner" or "the woman" in Maya's shot is
    Maya, never a new role; with two people there, it says who they are instead of guessing."""
    pid = _video(owner, editor, "Maya, 30s, opens the bag.")
    _make_looks(db, pid, {"name": "Maya", "description": "a messy bun"})
    _make_looks(db, pid, {"name": "Bruno", "description": "a tan pup", "shot_ids": ["1.1"]})
    roles, sheets = db.query(ScriptCastSlot).count(), db.query(Job).count()
    has = "who has a look in this video already (it's used); change_look Maya to redraw."
    for name in ("Maya Chen", "Bruno's owner"):
        said = _make_looks(db, pid, {"name": name, "description": "grey tee", "shot_ids": ["1.1"]})
        assert said == f"Refused: {name} is Maya, {has}"
    woman = _make_looks(db, pid, {"name": "the woman", "shot_ids": ["1.1"]})
    assert woman == (
        "Refused: shot 1.1 already shows Maya and Bruno: make_looks one of them by name, or "
        "give `shot_ids` that show none of them for someone new."
    )
    assert (db.query(ScriptCastSlot).count(), db.query(Job).count()) == (roles, sheets)


def test_a_person_is_tried_twice_then_waits_for_the_owner_whatever_the_words(
    app, db, owner, editor, monkeypatch
):
    """Video 294's tries were each worded differently: the cap is per person. Twice (the same
    move again counts), then the owner's card, and the run waits for it; one try after the
    answer, then it stops."""
    words = iter(["a tall man", "a tall man", "a short man", "a man in a red coat", "a man"])

    def zed(state):
        return {"tool": "make_looks", "why": "Z",
                "look": {"name": "Zed", "description": next(words, "a man")}}  # fmt: skip

    monkeypatch.setattr(director, "choose", started(zed))
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=12)
    out = editor.get(f"/projects/{pid}/director").json()
    tries = [t["result"] for t in out["turns"] if t["why"] == "Z"]
    why = ("Refused: Zed is named in neither the script nor the plan's shots; give `shot_ids`, "
           "the plan's shots that show them.")  # fmt: skip
    asked = "Asked: Who plays Zed? Pick or upload a picture of them."
    waits = "Waiting on the owner's answer to who plays Zed."
    assert tries == [why, f"{why} {asked}", waits]  # no third try while the card is open
    card = db.query(Ask).filter_by(project_id=pid, kind="cast").one()
    assert (card.subject, card.state, out["status"]) == ("Zed", "open", "running")
    owner.post(f"/asks/{card.id}/answer", json={"how": "reply", "text": "A tall man."})
    _run(app, db, ticks=12)
    out = editor.get(f"/projects/{pid}/director").json()
    tries = [t["result"] for t in out["turns"] if t["why"] == "Z"]
    assert tries[3] == why and len(tries) == 5  # one try after the answer, then it stops
    assert out["status"] == "ended" and out["ended"].startswith("It stopped: Zed's look was")


def test_a_take_carries_a_look_drawn_after_its_prompt_only_where_its_shots_show_them(
    owner, editor, db
):
    _, pid, slot = _nate_video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _two_clips(db, pid)  # clip 1 shows no one, clip 2 shows Nate
    bd = db.query(BreakdownVersion).filter_by(project_id=pid).order_by(BreakdownVersion.id.desc())
    rows = [ProjectClip(project_id=pid, breakdown_id=bd.first().id, clip_id=c, seconds=4,
                        prompt="Shot 1 | 0–4 s. Wide.", references=[])
            for c in ("c1", "c2")]  # fmt: skip
    db.add_all(rows)
    db.commit()  # their prompts were written before Nate had a sheet
    _drawn(db, editor, look)
    approve_cast(editor, pid)
    sheet = db.get(LibraryItem, look).sheet_file_id
    sent = {}
    for row in rows:
        made = editor.post(f"/projects/{pid}/clips/{row.id}/generate")
        assert made.status_code == 201, made.text
        sent[row.clip_id] = json.dumps(db.get(Job, made.json()["id"]).input["files"])
    assert str(sheet) in sent["c2"] and str(sheet) not in sent["c1"]
