"""Reed's live test: a frame missing a character's sheet couldn't be made. Every character in
a frame's shot now gets their approved sheet, nearest the camera first, within the image
model's limits, and saved frames are repaired for free (no model call)."""

from app import storyboard
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.storyboards import StoryboardFrame
from app.prompts.schemas import Breakdown, Frame
from app.seed import repair_frames
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_storyboard import _with_breakdown


def _people(app, db, editor, setup):  # noqa: F811
    """Mom and Nate, both with approved sheets, in shot 1.1: Mom speaks, the action names
    Nate first. The newest breakdown."""
    ids = []
    for name in ("Nate", "Mom"):
        made = editor.post(
            "/library/character", json={"name": name, "image_file_ids": [upload(editor)]}
        )
        with_sheet(db, made.json()["id"])
        ids.append(made.json()["id"])
    nate, mom = (f"char:{i}" for i in ids)
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": ids})
    _with_breakdown(app, db, editor, setup)
    row = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).order_by(
        BreakdownVersion.id.desc()).first()  # fmt: skip
    data = row.data
    shot = {**data["scenes"][0]["shots"][0], "character_ids": [nate, mom],
            "action": "Nate shrugs at his mom."}  # fmt: skip
    row.data = {
        **data,
        "scenes": [{**data["scenes"][0], "shots": [shot, *data["scenes"][0]["shots"][1:]]}],
    }
    db.commit()
    return row, nate, mom


def test_a_frame_without_its_peoples_sheets_gets_them_in_camera_order(app, db, editor, setup):  # noqa: F811
    row, nate, mom = _people(app, db, editor, setup)
    project = db.get(storyboard.Project, setup["project"])
    screen = f"screen:{setup['screen']}"
    picked = Frame(clip_id="c1", shot_id="1.1", reference_ids=[screen],
                   prompt="Place the app screen from image 1 onto the phone.")  # fmt: skip
    done = storyboard.with_cast(db, project, picked, Breakdown.model_validate(row.data))
    assert done.reference_ids == [mom, nate, screen]  # the speaker, then the action's order
    assert done.prompt == (
        "Place the app screen from image 3 onto the phone."  # it follows its picture
        " Keep Mom from image 1 exactly as on their sheet."
        " Keep Nate from image 2 exactly as on their sheet."
    )
    again = storyboard.with_cast(db, project, done, Breakdown.model_validate(row.data))
    assert again == done  # nothing changes the second time


def test_over_the_image_models_limit_the_nearest_are_kept(app, db, editor, setup, monkeypatch):  # noqa: F811
    row, nate, mom = _people(app, db, editor, setup)
    project = db.get(storyboard.Project, setup["project"])
    one = storyboard.image_model().model_copy(update={"max_character_images": 1})
    monkeypatch.setattr(storyboard, "image_model", lambda: one)
    picked = Frame(clip_id="c1", shot_id="1.1", reference_ids=[nate],
                   prompt="Generate a still of the boy from image 1.")  # fmt: skip
    done = storyboard.with_cast(db, project, picked, Breakdown.model_validate(row.data))
    assert done.reference_ids == [mom]  # Mom speaks: nearest the camera
    assert done.prompt.startswith("Generate a still of the boy from Nate.")
    kept = storyboard.with_cast(  # an editor's own pick is never dropped
        db, project, picked, Breakdown.model_validate(row.data), trim=False
    )
    assert kept == picked


def test_saved_frames_are_repaired_for_free_once(app, db, editor, setup):  # noqa: F811
    row, nate, mom = _people(app, db, editor, setup)
    frame = StoryboardFrame(project_id=setup["project"], breakdown_id=row.id, clip_id="c1",
                            shot_id="1.1", prompt="Mom and Nate argue.", reference_ids=[],
                            problems=["c1: char:1 in the shot without a sheet"])  # fmt: skip
    db.add(frame)
    db.commit()
    jobs = db.query(Job).count()
    assert repair_frames(db) == 1  # the deploy step
    db.refresh(frame)
    assert (frame.reference_ids, frame.problems) == ([mom, nate], [])
    assert repair_frames(db) == 0  # idempotent
    shown = editor.get(f"/projects/{setup['project']}/storyboard").json()
    assert [f["reference_ids"] for f in shown] == [[mom, nate]]
    assert db.query(Job).count() == jobs  # no model call, nothing charged
