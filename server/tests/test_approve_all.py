"""Approve all (Reed, 2026-10-26, #503): every frame with a still and nothing to fix, every
clip with a picked take; the rest listed with why; Undo takes back exactly that set."""

from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.storyboards import StoryboardFrame
from tests.conftest import upload
from tests.test_clip_takes import clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_storyboard import _with_breakdown


def _newest(db, pid):
    query = db.query(BreakdownVersion).filter_by(project_id=pid)
    return query.order_by(BreakdownVersion.id.desc()).first()


def test_approve_all_frames_and_undo(app, db, editor, setup):  # noqa: F811
    _with_breakdown(app, db, editor, setup)
    pid, bd = setup["project"], _newest(db, setup["project"])

    def frame(**extra):
        row = StoryboardFrame(project_id=pid, breakdown_id=bd.id, clip_id="c1", shot_id="1.1",
                              prompt="Mom at the table.", reference_ids=[], **extra)  # fmt: skip
        db.add(row)
        db.commit()
        return row.id

    ready = frame(file_id=upload(editor))
    advised = frame(file_id=upload(editor), problems=["Advice: a softer light reads better"])
    no_still = frame()
    problem = frame(file_id=upload(editor), problems=["More references than the model keeps"])
    earlier = frame(file_id=upload(editor), approved=True)
    recast = frame(file_id=upload(editor), still_stale=True)  # shows the old cast
    url = f"/projects/{pid}/storyboard"
    done = editor.post(f"{url}/approve-all").json()
    assert done == {
        "approved": [ready, advised],
        "skipped": [{"id": no_still, "reason": "no still yet"},
                    {"id": problem, "reason": "has a problem to fix"},
                    {"id": recast, "reason": "still is out of date, Redo it first"}],
    }  # fmt: skip
    shown = {f["id"]: f["approved"] for f in editor.get(url).json()}
    assert shown[ready] and shown[advised] and not shown[no_still] and shown[earlier]
    undone = editor.post(f"{url}/approve-all/undo", json={"ids": done["approved"]}).json()
    after = {f["id"]: f["approved"] for f in undone}
    assert not after[ready] and not after[advised] and after[earlier]  # exactly that set


def test_approve_all_clips_and_undo(app, db, editor, setup, clip):  # noqa: F811
    pid = setup["project"]
    row = db.get(ProjectClip, clip["id"])
    take = ClipTake(clip_id=row.id, number=1, job_id=row.job_id, file_id=upload(editor))
    db.add(take)
    db.flush()
    row.picked_take_id, row.file_id = take.id, take.file_id
    data = _newest(db, pid).data
    rows = [BreakdownVersion(project_id=pid, script_version=1, source="edit", data=data,
                             problems=[]) for _ in range(2)]  # fmt: skip
    db.add_all(rows)
    db.flush()
    older, newest = rows
    row.breakdown_id = newest.id  # the ready clip is for the newest breakdown
    stale = ProjectClip(project_id=pid, breakdown_id=older.id, clip_id="c3", seconds=5,
                        prompt="x", references=[], picked_take_id=take.id)  # fmt: skip
    no_take = ProjectClip(project_id=pid, breakdown_id=newest.id, clip_id="c2",
                          seconds=5, prompt="x", references=[])  # fmt: skip
    db.add_all([stale, no_take])
    db.commit()
    url = f"/projects/{pid}/clips"
    done = editor.post(f"{url}/approve-all").json()
    assert done == {"approved": [row.id], "skipped": [
        {"id": stale.id, "reason": "made for an older breakdown"},
        {"id": no_take.id, "reason": "no take picked yet"},
    ]}  # fmt: skip
    assert editor.get(url).json()[0]["approved"] is True
    undone = editor.post(f"{url}/approve-all/undo", json={"ids": done["approved"]}).json()
    assert not any(c["approved"] for c in undone)
