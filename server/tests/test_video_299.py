"""Video 299 (Pixar Dialogue, fomo): clip 3 was never made. Its one-line prompt ("only the
spoken line and …") was read as a broken audio line, so its take was refused "Fix this clip's
problems first" while clip_prompts said "No clip needs new prompts"; the server's first-takes
step was refused four times; and the take watch remade clips 1 and 2 again and again for a
generated fomo screen, so the director never got a turn. On the stand-ins."""

from app import director_tools, take_watch
from app.clip_prompts import to_rewrite
from app.models.accounts import User
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.prompts import check
from tests.test_clip_takes import clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

LINE = ("Audio: only the spoken line and a quiet night apartment with a faint fridge hum. No "
        "music. No subtitles.")  # fmt: skip


def test_a_one_line_clips_audio_line_is_its_audio_line():
    prompt = f"{LINE}\nSummary: x\nShot 1 | 0-4 s. Maya dares us.\nKeep: Maya.\n{LINE}"
    assert "doesn't open and close with the same audio line" not in check._shape(prompt, 4)[0]


def test_a_stuck_clip_is_fixed_free_first(app, db, editor, setup, clip):  # noqa: F811
    project = db.get(Project, setup["project"])
    row = db.get(ProjectClip, clip["id"])
    lines = row.prompt.splitlines()
    row.prompt = "\n".join(lines[:-1])  # its closing audio line lost: the free fix puts it back
    row.problems = ["doesn't open and close with the same audio line"]
    db.commit()
    assert to_rewrite(db, project) == []  # nothing stale: the director's clip_prompts still
    ed = db.query(User).filter_by(email="ed@example.com").one()  # rewrites it, never "none"
    said = director_tools.run(db, ed, project, {"tool": "clip_prompts"}, app.state.storage)
    assert said == f"Rewriting the prompt of {row.clip_id}.", said
    db.query(Job).filter(Job.input["step"].as_string() == "clip_prompts",
                         Job.status == "queued").delete(synchronize_session=False)  # fmt: skip
    db.commit()
    said = director_tools.run(db, ed, project, {"tool": "make_take", "clip_id": None},
                              app.state.storage)  # fmt: skip
    db.refresh(row)
    assert said == "Making 1 take.", said
    assert row.prompt.splitlines()[-1] == lines[-1] and not row.problems
    assert db.query(Job).filter(Job.kind == "video").count() == 1


def test_screen_faults_are_the_directors(app, db, editor, setup, clip, monkeypatch):  # noqa: F811
    """The take watch never remakes a take on its own for a generated screen or label (the
    director's call, rule 16), and after one remake of a clip it hands back to the director."""
    from app.director import RUN
    from app.director import STEP as TURN
    from tests.test_take_watch import _land

    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins
    shown = _land(app, db, editor, setup, clip, action="Maya checks the phone. fake:screen")
    w = shown["takes"][0]["watch"]
    assert (w["action"], w["did"].startswith("Left for the director:")) == ("flagged", True)
    assert db.query(Job).filter(Job.kind == "video").count() == 1  # no remake bought
    project = db.get(Project, setup["project"])
    db.add(Job(workspace_id=project.workspace_id, kind="write-claude", provider="fake",
               project_id=project.id, status="succeeded", credits=0,
               input={"step": TURN, RUN: {"id": "r1", "redos": {}}}))  # fmt: skip
    db.commit()
    shown = _land(app, db, editor, setup, clip, action="Maya waves. fake:redo")
    assert shown["takes"][1]["watch"]["action"] == "redo"  # one remake on its own
    again = _land(app, db, editor, setup, clip, press=False)
    assert again["takes"][2]["watch"]["did"] == take_watch.HANDED_BACK  # then the director's
    assert db.query(Job).filter(Job.kind == "video").count() == 3


def test_a_generated_screen_is_judged_by_its_brand_name_and_logo():
    from app import prompts

    said = prompts.system("take_watch")
    assert "a generated brand screen passes when its brand name and logo read" in said
    assert "a wrong brand or logo is still a fault" in said
