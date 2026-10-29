"""OR3, Preferred and going back (flows.md # 5): the Preferred still, the Preferred look, and
Versions on storyboards, clip prompts and breakdowns, each free with Undo."""

from app import clip_prompts
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.storyboard import save_still
from tests.conftest import upload
from tests.test_change_notes import _frame
from tests.test_enhance import setup  # noqa: F401 - fixture


def _take_from(db, editor, frame: StoryboardFrame) -> ProjectClip:
    """Clip c1 with a picked take made from its frame's still as it is now."""
    project, video = db.get(Project, frame.project_id), upload(editor)
    job = Job(workspace_id=project.workspace_id, created_by_id=None, kind="video-480p",
              provider="fake", project_id=project.id, status="succeeded",
              input={"files": {"reference_images": [frame.file_id]}})  # fmt: skip
    db.add(job)
    db.flush()
    ref = {"kind": "image", "id": f"frame:{frame.clip_id}", "role": ""}
    row = ProjectClip(project_id=project.id, breakdown_id=frame.breakdown_id,
                      clip_id=frame.clip_id, seconds=5, prompt="Mom looks up.",
                      references=[ref])  # fmt: skip
    db.add(row)
    db.flush()
    take = ClipTake(clip_id=row.id, number=1, job_id=job.id, file_id=video)
    db.add(take)
    db.flush()
    row.picked_take_id, row.file_id = take.id, take.file_id
    db.commit()
    return row


def _older(db, row: ProjectClip) -> bool:
    db.expire_all()
    project = db.get(Project, row.project_id)
    return clip_prompts.older_still(db, clip_prompts.assets(db, project), row)


def test_a_preferred_still_says_when_and_who_and_its_takes_follow(app, db, editor, setup):  # noqa: F811
    url, frame = _frame(app, db, editor, setup)
    first = frame.file_id
    row = _take_from(db, editor, frame)
    assert not _older(db, row)  # made from the still in use

    still = upload(editor)
    draw = Job(workspace_id=db.get(Project, frame.project_id).workspace_id, kind="image",
               provider="fake", project_id=frame.project_id, status="succeeded",
               created_by_id=db.get(Project, frame.project_id).created_by_id,
               input={"step": "frame", "frame_id": frame.id, "project_id": frame.project_id},
               output={"file_ids": [still]})  # fmt: skip
    db.add(draw)
    db.flush()
    save_still(db, draw)  # a new still: the first one goes to the earlier stills
    db.commit()
    shown = next(f for f in editor.get(url).json() if f["id"] == frame.id)
    (earlier,) = shown["earlier"]
    assert earlier["file_id"] == first and earlier["made_at"]  # when it was made
    assert _older(db, row)  # the take shows a still that's no longer the Preferred one

    back = editor.post(f"{url}/frames/{frame.id}/pick", json={"file_id": first}).json()
    assert back["file_id"] == first and back["was_file_id"] == draw.output["file_ids"][0]
    assert back["earlier"][0]["made_by"]["name"]  # who drew the one it replaced
    assert not _older(db, row)  # Preferred again: the take is current
    undo = editor.post(f"{url}/frames/{frame.id}/pick", json={"file_id": back["was_file_id"]})
    assert undo.json()["file_id"] == draw.output["file_ids"][0]  # Undo: free, one press
    assert _older(db, row)
