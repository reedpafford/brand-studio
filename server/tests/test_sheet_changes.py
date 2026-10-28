"""A Cast & places sheet changed after its video's stills and clip prompts were made (QA-Live,
video #17: Goth GF 2's removed purple streak came back, and 8 prompts and 5 stills were fixed
by hand). Opening Storyboard or Clips repairs the words for free; a still drawn from the old
sheet says so and is "Out of date" for a one-click redraw. Nothing paid runs by itself."""

from datetime import datetime

from app import clip_prompts, storyboard
from app.models.clips import ProjectClip
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.storyboards import StoryboardFrame
from tests.conftest import upload
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_frame_sheets import _people

PROMPT = (
    "References: [Image1] is the first frame. [Image2] is Mom. [Image3] is Nate, purple streak "
    "and mesh top.\nShot 1 | 0–5 s. Nate (purple streak) shrugs at his mom.\n"
    "Keep: Mom as in [Image2], the same look as on their sheet; Nate as in [Image3], purple streak."
)


def test_a_changed_sheet_refreshes_the_words_and_flags_the_old_still(app, db, editor, setup):  # noqa: F811
    bd, nate, mom = _people(app, db, editor, setup)
    still, new_sheet = upload(editor), upload(editor)  # before any write here: one writer
    pid, sheet = (
        setup["project"],
        {r: db.get(LibraryItem, int(r[5:])).sheet_file_id for r in (nate, mom)},
    )
    writer = Job(workspace_id=1, kind="write", provider="claude", input={}, project_id=pid,
                 status="succeeded")  # fmt: skip
    db.add(writer)
    db.flush()
    frame = StoryboardFrame(project_id=pid, breakdown_id=bd.id, clip_id="c1", shot_id="1.1",
                            reference_ids=[nate, mom], prompt="Nate (purple streak) shrugs at Mom.",
                            file_id=still, approved=True, job_id=writer.id)  # fmt: skip
    db.add(frame)
    db.flush()
    db.add(Job(workspace_id=1, kind="image", provider="fake", project_id=pid, status="succeeded",
               input={"frame_id": frame.id, "files": {"image_input": [sheet[nate], sheet[mom]]}},
               output={"file_ids": [frame.file_id]}))  # fmt: skip
    refs = [{"kind": "image", "id": i, "role": "x"} for i in ("frame:c1", mom, nate)]
    clip = ProjectClip(project_id=pid, breakdown_id=bd.id, clip_id="c1", seconds=5,
                       prompt=PROMPT, references=refs, job_id=writer.id)  # fmt: skip
    db.add(clip)
    db.commit()
    project = db.get(storyboard.Project, pid)
    storyboard.repair(db, project), clip_prompts.repair(db, project)
    db.commit()
    assert "purple streak" in frame.prompt and not frame.still_stale  # nothing changed yet
    assert not [p for p in clip.problems if "older look" in p]

    nate_item = db.get(LibraryItem, int(nate[5:]))  # Nate's sheet goes back to his first look
    nate_item.sheet_file_id = new_sheet
    db.get(StoredFile, new_sheet).created_at = datetime(2099, 1, 1)  # made after the prompts
    db.commit()
    jobs = db.query(Job).count()
    assert storyboard.repair(db, project) == 1 and clip_prompts.repair(db, project) == 1
    db.commit()
    assert frame.prompt == "Nate shrugs at Mom." and (frame.still_stale, frame.approved) == (
        True,
        False,
    )
    assert (
        "Advice: Drawn from an older look of Nate. Redraw it to show the new look."
        in frame.problems
    )
    assert "[Image2] is Mom. [Image3] is Nate." in clip.prompt and "purple" not in clip.prompt
    assert "Nate as in [Image3], the same look as on their sheet." in clip.prompt
    assert [p for p in clip.problems if "first frame was drawn from an older look of Nate" in p]
    frame.approved = True  # the editor approves it anyway: it stays approved
    db.commit()
    assert storyboard.repair(db, project) == clip_prompts.repair(db, project) == 0  # idempotent
    assert frame.approved and db.query(Job).count() == jobs  # nothing drawn or charged by itself
