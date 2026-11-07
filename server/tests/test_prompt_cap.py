"""Video 245: Seedance 2.0 takes a prompt of at most 4000 characters (Replicate: a 422,
"input.prompt: String length must be less than or equal to 4000"), and 245's prompts, written
for 2.5, ran 4038–4780. A prompt over its model's limit is never sent: it's rewritten to fit,
free, and the writer is told the limit first; a request refused as invalid is never sent again
unchanged and never counted as spent. Mocked Replicate and Claude: no paid calls."""

from decimal import Decimal

from app import clip_prompts, clip_takes
from app.catalogue import get_model
from app.credits import never_billed
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.worker import _plain
from tests.test_clip_takes import clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

TOO_LONG = ('RuntimeError(\'Replicate 422: {"detail":"- input.prompt: String length must be '
            'less than or equal to 4000","status":422}\')')  # fmt: skip


def _on_two(db, clip) -> ProjectClip:  # noqa: F811
    row = db.get(ProjectClip, clip["id"])
    row.model = {"id": "seedance-2.0", "why": "The director moved it.", "by": "director"}
    db.commit()
    return row


def test_every_video_models_prompt_limit_is_known():
    assert get_model("seedance-2.0").prompt_max == 4000
    for other in ("seedance-2.5", "seedance-1-lite", "gemini-omni-1.2"):
        assert get_model(other).prompt_max == 0, other  # their schemas state none


def test_a_prompt_too_long_for_its_model_is_rewritten_to_fit_never_sent(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    base = f"/projects/{setup['project']}"
    row = _on_two(db, clip)
    row.prompt = f"{row.prompt}\n{'Lush detail. ' * 400}"  # ~5,200 characters, as 245's
    db.commit()
    made = editor.post(f"{base}/clips/{row.id}/generate")
    assert made.status_code == 409, made.text
    assert made.json()["detail"].startswith("The prompt is too long for Seedance 2.0 (")
    assert "rewritten to fit, free" in made.json()["detail"]
    jobs = db.query(Job).filter(Job.project_id == setup["project"]).all()
    assert not [j for j in jobs if j.input.get("step") == "clip_take"]  # never sent
    (fix,) = [j for j in jobs if j.input.get(clip_takes.FIT)]
    assert fix.input["clip_ids"] == [row.clip_id] and fix.credits == 0  # free
    told = fix.input["prompt"]  # its own instruction: shorten all else, keep these lines
    assert "under 3400 characters" in told and 'every line that starts "Shot N |"' in told
    assert "the Keep: line" in told and "Change only the lines" not in told
    again = editor.post(f"{base}/clips/{row.id}/generate")  # while it's being rewritten
    assert again.status_code == 409
    assert len([j for j in db.query(Job) if j.input.get(clip_takes.FIT)]) == 1  # one fix
    fix.status = JobStatus.succeeded
    db.commit()
    editor.post(f"{base}/clips/{row.id}/generate")  # still too long: a second rewrite
    fix2 = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)][-1]
    fix2.status = JobStatus.succeeded
    db.commit()
    stuck = editor.post(f"{base}/clips/{row.id}/generate")
    assert stuck.json()["detail"].startswith("The prompt is still too long for Seedance 2.0")
    row.prompt = row.prompt[:3000]  # rewritten to fit
    db.commit()
    assert editor.post(f"{base}/clips/{row.id}/generate").status_code == 201


def test_the_writer_is_told_each_clips_model_limit(db, setup, clip):  # noqa: F811
    video = db.get(Project, setup["project"])
    row = db.get(ProjectClip, clip["id"])
    assert clip_prompts.prompt_limits(db, video, [row.clip_id]) == ""  # 2.5: no limit
    _on_two(db, clip)
    said = clip_prompts.prompt_limits(db, video, [row.clip_id])
    assert said == (f"<limit>{row.clip_id} is made on Seedance 2.0, which takes a prompt of "
                    "at most 4000 characters: write its prompt in under 3400 "
                    "characters.</limit>")  # fmt: skip
    data = clip_prompts.job_input(db, video, clip_prompts.newest(db, video), [row.clip_id])
    assert said in data["prompt"]


def test_a_request_refused_as_invalid_is_never_sent_again_unchanged_nor_counted(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    base = f"/projects/{setup['project']}"
    row = db.get(ProjectClip, clip["id"])
    take = clip_takes.take_input(db, db.get(Project, setup["project"]), row)
    failed = Job(workspace_id=db.get(Project, setup["project"]).workspace_id,
                 created_by_id=row.project_id and db.get(Project, row.project_id).created_by_id,
                 kind="video", provider="replicate", input=take, project_id=setup["project"],
                 credits=Decimal(5), status=JobStatus.failed, error_detail=TOO_LONG)  # fmt: skip
    db.add(failed)
    db.commit()
    assert clip_takes.why_failed(failed) == "invalid"
    assert never_billed(failed)  # Replicate refused it before running: $0 spent
    assert _plain(failed, TOO_LONG) == (
        "The service refused this request as invalid, so nothing was charged: input.prompt: "
        "String length must be less than or equal to 4000.")  # fmt: skip
    clip_takes.retry(db, failed)  # never retried on its own as it is
    assert not db.query(Job).filter(Job.retry_of_id == failed.id).count()
    same = editor.post(f"{base}/clips/{row.id}/generate")  # the director's "try again"
    assert same.status_code == 409 and "would be refused again" in same.json()["detail"]
    row.prompt = f"{row.prompt} Calmer."  # changed: it may go
    db.commit()
    assert editor.post(f"{base}/clips/{row.id}/generate").status_code == 201


def test_the_directors_take_names_the_fix_and_the_rewrite_is_on_its_way(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    from app import director_tools
    from app.models.accounts import User

    row = _on_two(db, clip)
    row.prompt = f"{row.prompt}\n{'Lush detail. ' * 400}"
    db.commit()
    video = db.get(Project, setup["project"])
    said = director_tools.run(db, db.get(User, video.created_by_id), video,
                              {"tool": "make_take", "clip_id": row.clip_id, "note": ""},
                              app.state.storage)  # fmt: skip
    assert said == (f"Refused: The prompt of {row.clip_id} is too long for its model, so "
                    "it's being rewritten to fit (free); make its take once it's "
                    "rewritten.")  # fmt: skip
    assert [j for j in db.query(Job) if j.input.get(clip_takes.FIT)]  # the fix is on its way
    assert not [j for j in db.query(Job) if j.input.get("step") == "clip_take"]


def _land(db, fix, clip_id, prompt, references):
    """The fix's answer saved, as the worker saves it."""
    fix.output = {"clips": [{"clip_id": clip_id, "seconds": 5, "references": references,
                             "prompt": prompt}]}  # fmt: skip
    fix.status = JobStatus.succeeded
    clip_prompts.save_clip_prompts(db, fix)
    db.commit()


def test_a_fit_that_drops_a_shot_keep_or_spoken_line_is_never_saved(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    """QA on #1430: on the stand-ins a 4,780-character prompt came back at 293, its shots and
    lines gone, and was saved and sent. A fit keeps every "Shot N |" line, the Keep: line and
    every quoted line word for word, under the limit; else the old prompt stays, the clip says
    so, and it counts as one of its two tries."""
    base = f"/projects/{setup['project']}"
    row = _on_two(db, clip)
    long = f"{row.prompt}\n{'Lush detail. ' * 400}"
    row.prompt = long
    db.commit()
    editor.post(f"{base}/clips/{row.id}/generate")
    (fix,) = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)]
    shots = [x for x in long.splitlines() if x.startswith("Shot ")]
    keep = [x for x in long.splitlines() if x.startswith("Keep: ")]
    assert shots and keep  # the lines a fit must keep
    refs = row.references
    _land(db, fix, row.clip_id, "A short prompt with nothing in it.", refs)
    db.refresh(row)
    assert row.prompt == long  # never saved
    assert (row.change["note"], row.change["status"]) == (clip_prompts.FIT_NOTE, "failed")
    assert "dropped or changed" in row.change["error"] and "stays as it was" in row.change["error"]
    editor.post(f"{base}/clips/{row.id}/generate")  # one try used: a second fit is asked
    fix2 = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)][-1]
    assert fix2.id != fix.id
    kept = "\n".join([*shots, *keep])  # every line kept, the rest said shorter
    _land(db, fix2, row.clip_id, kept, refs)
    db.refresh(row)
    saved = row.prompt.splitlines()
    assert all(x in saved for x in [*shots, *keep]) and len(row.prompt) < 4000  # it fits
    assert row.prompt != long and (row.change or {}).get("status") != "failed"


def test_a_fit_still_over_the_limit_is_never_saved():
    job = Job(input={clip_takes.FIT: True, "before": "Shot 1 | a\nKeep: b", "fit_max": 10})
    assert clip_prompts.fit_lost(job, "Shot 1 | a\nKeep: b").startswith(
        "The shortened prompt is still"
    )
    assert clip_prompts.fit_lost(job, "Shot 1 | changed\nKeep: b").startswith(
        "The shortened prompt dropped"
    )
    said = Job(
        input={clip_takes.FIT: True, "before": 'Shot 1 | MOM: "Where is it?"', "fit_max": 99}
    )
    assert clip_prompts.fit_lost(said, 'Shot 1 | MOM: "Where is it?"\nKeep: b') == ""
    assert clip_prompts.fit_lost(Job(input={}), "") == ""  # not a fit: nothing to check


def test_two_presses_at_once_queue_one_fit_and_a_full_rewrite_comes_first(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    import pytest
    from fastapi import HTTPException

    video = db.get(Project, setup["project"])
    row = _on_two(db, clip)
    row.prompt = f"{row.prompt}\n{'Lush detail. ' * 400}"
    db.commit()
    model, sent = get_model("seedance-2.0"), row.prompt
    for _ in range(2):  # two presses: the second sees the first's fix under the lock
        with pytest.raises(HTTPException):
            clip_takes.fits_prompt(db, video, row, model, sent)
    assert len([j for j in db.query(Job) if j.input.get(clip_takes.FIT)]) == 1
    db.query(Job).filter(Job.project_id == video.id).delete()
    db.add(Job(workspace_id=video.workspace_id, created_by_id=video.created_by_id,
               kind="write-claude", provider="claude", input={"step": "clip_prompts"},
               project_id=video.id, credits=0, status=JobStatus.queued))  # fmt: skip
    db.commit()
    with pytest.raises(HTTPException) as no:  # every clip is being written: after that
        clip_takes.fits_prompt(db, video, row, model, sent)
    assert "once the clip prompts being written now are done" in no.value.detail
    assert not [j for j in db.query(Job) if j.input.get(clip_takes.FIT)]


def test_an_invalid_take_may_go_again_once_its_pictures_change(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    import pytest
    from fastapi import HTTPException

    video = db.get(Project, setup["project"])
    row = db.get(ProjectClip, clip["id"])
    take = clip_takes.take_input(db, video, row)
    failed = Job(workspace_id=video.workspace_id, created_by_id=video.created_by_id,
                 kind="video", provider="replicate", input=take, project_id=video.id,
                 credits=Decimal(5), status=JobStatus.failed, error_detail=TOO_LONG)  # fmt: skip
    db.add(failed)
    db.commit()
    with pytest.raises(HTTPException):  # the same request, pictures and all: refused
        clip_takes.not_again(db, row, take["model"], take["input"], take["files"])
    other = {**take["files"], "reference_images": [999999]}  # a picture changed
    clip_takes.not_again(db, row, take["model"], take["input"], other)  # it may go
