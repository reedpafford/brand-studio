"""The video's Clips tab (v6 S6, S-gaps-08): Use this take (free, and it's the person's OK),
Keep it on a take the director's watch flagged, what each clip cost, the model each take was
made with, and Change the still… on a clip with a take making its new take too. Free: the
stand-in providers only."""

from decimal import Decimal

import pytest

from app import change, storyboard
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


def _two_takes(app, db, editor, base, clip):  # noqa: F811
    url = f"{base}/clips/{clip['id']}"
    editor.post(f"{url}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    editor.post(f"{url}/generate")
    _work(app, db, FakeSeedance([_mp4("blue")]))
    return url, editor.get(f"{base}/clips").json()[0]


def test_use_this_take_picks_and_approves_it_free(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url, shown = _two_takes(app, db, editor, base, clip)
    first, second = shown["takes"]
    before = db.query(Job).count()
    used = editor.post(f"{url}/takes/{first['id']}/use").json()
    assert used["picked_take_id"] == first["id"] and used["approved"] is True
    assert db.query(Job).count() == before  # free: nothing queued
    assert editor.post(f"{url}/takes/99999/use").status_code == 404
    assert [t["model"] for t in used["takes"]] == [second["model"]] * 2 and first["model"]
    assert used["spent"] > 0  # its takes' real cost: "Cost $0.64 (2 takes)"
    assert all("from_still" in t for t in used["takes"])  # the still each was made from


def test_keep_it_clears_a_flag_and_says_who_kept_it(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url, shown = _two_takes(app, db, editor, base, clip)
    take = db.get(ClipTake, shown["takes"][1]["id"])
    refused = editor.post(f"{url}/takes/{take.id}/keep")
    assert refused.status_code == 409  # nothing flagged on it
    take.watch = {"state": "done", "action": "flagged", "found": "Dana's voice drifts."}
    db.commit()
    kept = editor.post(f"{url}/takes/{take.id}/keep").json()
    watch = next(t["watch"] for t in kept["takes"] if t["id"] == take.id)
    assert watch["action"] == "keep" and watch["kept_by"]
    assert watch["did"] == f"Kept by {watch['kept_by']}."
    assert kept["picked_take_id"] == take.id and kept["approved"] is True


def test_change_the_still_with_a_take_makes_its_new_take_too(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    _two_takes(app, db, editor, base, clip)
    row = db.get(ProjectClip, clip["id"])
    frame = StoryboardFrame(project_id=row.project_id, clip_id=row.clip_id, shot_id="1.1",
                            prompt="Mom at the window.", reference_ids=[],
                            breakdown_id=row.breakdown_id, file_id=None)  # fmt: skip
    db.add(frame)
    db.commit()
    project = db.get(Project, row.project_id)
    still_only = change.credits(db, project, frame) - change._then(db, project, row)
    assert change.take_after(db, frame) is not None  # its clip has takes
    assert change.credits(db, project, frame) > still_only  # "a new still and a new take"
    job = Job(workspace_id=project.workspace_id, project_id=project.id, kind="image",
              provider="replicate",
              input={"frame_id": frame.id, "then_take": True},
              output={"file_ids": [shown_file(db, row)]}, created_by_id=project.created_by_id,
              credits=Decimal(0))  # fmt: skip
    db.add(job)
    db.flush()
    takes_before = db.query(Job).filter(Job.kind == "video").count()
    storyboard.save_still(db, job)
    db.commit()
    assert db.get(StoryboardFrame, frame.id).approved  # the still asked for is in use
    assert db.query(Job).filter(Job.kind == "video").count() == takes_before + 1


def shown_file(db, row) -> int:
    return db.get(ClipTake, row.picked_take_id).file_id


@pytest.mark.parametrize("flag", ["unsure", "held"])
def test_keep_also_takes_an_unsure_take(app, db, editor, setup, clip, flag):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url, shown = _two_takes(app, db, editor, base, clip)
    take = db.get(ClipTake, shown["takes"][0]["id"])
    take.watch = {"state": "done", "action": flag, "found": "Her lips may slip (not confirmed)."}
    db.commit()
    assert editor.post(f"{url}/takes/{take.id}/keep").status_code == 200


def test_a_new_still_never_pays_a_take_from_a_bad_prompt(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    _two_takes(app, db, editor, base, clip)
    row = db.get(ProjectClip, clip["id"])
    row.problems = ["The prompt says 12 s but the clip is 4 s."]
    frame = StoryboardFrame(project_id=row.project_id, clip_id=row.clip_id, shot_id="1.1",
                            prompt="Mom at the window.", reference_ids=[],
                            breakdown_id=row.breakdown_id, file_id=None)  # fmt: skip
    db.add(frame)
    db.commit()
    project = db.get(Project, row.project_id)
    job = Job(workspace_id=project.workspace_id, project_id=project.id, kind="image",
              provider="replicate", input={"frame_id": frame.id, "then_take": True},
              output={"file_ids": [shown_file(db, row)]}, created_by_id=project.created_by_id,
              credits=Decimal(0))  # fmt: skip
    db.add(job)
    db.flush()
    takes_before = db.query(Job).filter(Job.kind == "video").count()
    storyboard.save_still(db, job)
    db.commit()
    assert db.query(Job).filter(Job.kind == "video").count() == takes_before  # nothing paid
    said = editor.get(f"{base}/clips").json()[0]["change"]
    assert said["status"] == "failed" and "Fix this clip's prompt" in said["error"]


def test_history_lists_each_prompt_and_going_back_never_makes_a_take(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url = f"{base}/clips/{clip['id']}"
    first = clip["prompt"]
    editor.put(url, json={"prompt": first + " Slower.", "references": clip["references"]})
    shown = editor.get(f"{base}/clips").json()[0]
    assert [v["prompt"] for v in shown["versions"]][:2] == [shown["prompt"], first]
    before = db.query(Job).filter(Job.kind == "video").count()
    back = editor.post(f"{url}/versions/1/use").json()
    assert back["prompt"] == first
    assert db.query(Job).filter(Job.kind == "video").count() == before  # nothing made


def test_going_back_keeps_the_take_in_the_cut_approved(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    url = f"{base}/clips/{clip['id']}"
    editor.put(url, json={"prompt": clip["prompt"] + " Slower.", "references": clip["references"]})
    editor.post(f"{url}/generate")  # made from the edited prompt
    _work(app, db, FakeSeedance([_mp4("red")]))
    take = editor.get(f"{base}/clips").json()[0]["takes"][-1]
    editor.post(f"{url}/takes/{take['id']}/use")
    back = editor.post(f"{url}/versions/1/use").json()  # the first prompt again
    assert back["approved"] is True and back["picked_take_id"] == take["id"]
    listed = editor.get(f"{base}/clips").json()[0]
    assert listed["approved"] is True and listed["take_stale"] is True  # "Out of date", kept
    assert editor.post(f"{base}/video").status_code == 201  # the cut can still be made


def test_keeping_a_held_take_withdraws_its_waiting_remake(app, db, editor, setup, clip):  # noqa: F811
    from app.models.jobs import JobStatus

    base = f"/projects/{setup['project']}"
    url, shown = _two_takes(app, db, editor, base, clip)
    take = db.get(ClipTake, shown["takes"][1]["id"])
    project = db.get(Project, take_project(db, take))
    remake = Job(workspace_id=project.workspace_id, project_id=project.id, kind="video",
                 provider="replicate", input={"project_clip_id": clip["id"]},
                 status=JobStatus.needs_owner_approval, created_by_id=project.created_by_id,
                 credits=Decimal(3))  # fmt: skip
    db.add(remake)
    db.flush()
    take.watch = {"state": "done", "action": "held", "found": "A stray hand.",
                  "remake_job_id": remake.id}  # fmt: skip
    db.commit()
    assert editor.post(f"{url}/takes/{take.id}/keep").status_code == 200
    db.expire_all()
    assert db.get(Job, remake.id).status == JobStatus.cancelled  # the owner can't approve it now


def take_project(db, take) -> int:
    return db.get(ProjectClip, take.clip_id).project_id


def test_editing_a_prompt_never_buys_a_take(app, db, editor, setup, clip):  # noqa: F811
    """Reed, rule 21 (#1347): a prompt edited after its take exists, or while it's being made,
    marks the take out of date and queues nothing; the takes stay."""
    base = f"/projects/{setup['project']}"
    url = f"{base}/clips/{clip['id']}"
    editor.post(f"{url}/generate")  # a take being made
    videos = lambda: db.query(Job).filter(Job.kind == "video").count()  # noqa: E731
    before = videos()
    editor.put(url, json={"prompt": clip["prompt"] + " Slower.", "references": clip["references"]})
    assert videos() == before  # nothing more queued while it's made
    _work(app, db, FakeSeedance([_mp4("red")]))
    shown = editor.get(f"{base}/clips").json()[0]
    (take,) = shown["takes"]  # it lands, kept, but not as the take of the new prompt
    assert shown["picked_take_id"] is None or shown["take_stale"] is True
    editor.post(f"{url}/takes/{take['id']}/use")  # a person puts it in the cut
    editor.put(url, json={"prompt": clip["prompt"] + " Faster.", "references": clip["references"]})
    after = editor.get(f"{base}/clips").json()[0]
    assert videos() == before and [t["id"] for t in after["takes"]] == [take["id"]]
    assert after["picked_take_id"] == take["id"] and after["approved"] is True
    assert after["take_stale"] is True and after["take_credits"] > 0  # "Another take · up to"
