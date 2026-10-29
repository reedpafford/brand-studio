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
from tests.test_clip_takes import clip  # noqa: F401 - fixture
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


def test_a_preferred_look_is_an_earlier_approved_sheet_with_undo(db, owner, editor):
    from app.models.accounts import User
    from app.models.library import LibraryItem
    from app.routes.library import _save_version
    from tests.helpers import with_sheet

    made = {"name": "Mia", "notes": "a girl", "image_file_ids": [upload(owner)]}
    mia = owner.post("/library/character", json=made).json()["id"]
    with_sheet(db, mia)
    first, second = db.get(LibraryItem, mia).sheet_file_id, upload(owner)
    item, me = db.get(LibraryItem, mia), db.query(User).filter_by(role="owner").one()
    _save_version(db, me, item)  # a new sheet, approved (as the Approve press does)
    item.sheet_file_id, item.sheet_approved = second, True
    db.commit()
    url = f"/library/character/{mia}/sheet"
    sheets = owner.get(f"{url}/versions").json()
    assert {(s["file_id"], s["preferred"]) for s in sheets} == {(second, True), (first, False)}
    assert all(s["made_at"] and s["look_id"] == "house" for s in sheets)

    assert editor.post(f"{url}/preferred", json={"file_id": first}).status_code == 403  # rule 12
    assert owner.post(f"{url}/preferred", json={"file_id": 999}).status_code == 404
    back = owner.post(f"{url}/preferred", json={"file_id": first}).json()
    assert (back["sheet_file_id"], back["was_file_id"], back["name"]) == (first, second, "Mia")
    assert back["sheet_status"] == "approved"
    undo = owner.post(f"{url}/preferred", json={"file_id": back["was_file_id"]}).json()
    assert undo["sheet_file_id"] == second  # Undo: one press, free


def test_go_back_to_an_earlier_storyboard_with_undo(app, db, editor, setup):  # noqa: F811
    from tests.test_enhance import FakeClaude, _run
    from tests.test_storyboard import _frames

    url, frame = _frame(app, db, editor, setup)
    first_still, refs = frame.file_id, frame.reference_ids
    row = _take_from(db, editor, frame)  # a take made from storyboard 1's still
    assert editor.post(url, json={}).status_code == 201  # Make the storyboard again
    _run(app, db, FakeClaude(_frames(*refs)))
    db.expire_all()
    new = db.get(StoryboardFrame, editor.get(url).json()[0]["id"])
    second_still = upload(editor)
    new.file_id = second_still  # storyboard 2's still
    db.commit()
    assert _older(db, row)  # its take shows storyboard 1's still

    shown = editor.get(f"{url}/versions").json()
    assert [v["index"] for v in shown] == [None, 0] and shown[0]["current"]
    assert shown[1]["still_file_ids"] == [first_still] and shown[1]["made_at"]
    assert editor.post(f"{url}/versions/5/use").status_code == 404

    back = editor.post(f"{url}/versions/0/use").json()  # Go back to this: free
    assert [(f["clip_id"], f["file_id"]) for f in back] == [(frame.clip_id, first_still)]
    assert not _older(db, row)  # the take made from the restored frame is current again
    assert [v["index"] for v in editor.get(f"{url}/versions").json()] == [None, 0]
    undo = editor.post(f"{url}/versions/0/use").json()  # Undo: storyboard 2 again
    assert undo[0]["file_id"] == second_still and _older(db, row)


def test_go_back_to_an_earlier_clip_prompt_with_undo(app, db, editor, setup, clip):  # noqa: F811
    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    assert [v["current"] for v in clip["versions"]] == [True]  # Claude's, version 1
    edited = clip["prompt"].replace("Setting: cold morning light.", "Setting: warm dusk light.")
    shown = editor.put(url, json={"prompt": edited, "references": clip["references"]}).json()
    assert [v["index"] for v in shown["versions"]] == [0, 1] and shown["versions"][0]["made_by"]
    from app import video_settings
    from app.breakdown import video_model

    row = db.get(ProjectClip, clip["id"])
    project, video = db.get(Project, row.project_id), upload(editor)
    take = ClipTake(
        clip_id=row.id,
        number=1,
        job_id=row.job_id,
        file_id=video,
        prompt=edited,
        made_with={
            **video_settings.made_with(db, project, [], video_model(project).id),
            "prompt_version": 2,
        },
    )  # made from the edit
    db.add(take)
    db.flush()
    row.picked_take_id, row.file_id = take.id, take.file_id
    db.commit()
    listed = lambda: next(c for c in editor.get(url.rsplit("/", 1)[0]).json()  # noqa: E731
                          if c["id"] == clip["id"])  # fmt: skip
    assert listed()["take_stale"] is False

    assert editor.post(f"{url}/versions/0/use").status_code == 409  # in use already
    assert editor.post(f"{url}/versions/9/use").status_code == 404
    back = editor.post(f"{url}/versions/1/use").json()  # Go back to this: free
    assert back["prompt"] == clip["prompt"] and back["prompt_ok"] is False
    assert listed()["take_stale"] is True  # its take was made from the other version
    undo = editor.post(f"{url}/versions/1/use").json()  # Undo
    assert undo["prompt"] == edited and listed()["take_stale"] is False


def test_go_back_to_an_earlier_breakdown_with_undo(app, db, editor, setup):  # noqa: F811
    url, frame = _frame(app, db, editor, setup)
    base = f"/projects/{setup['project']}/breakdown"
    first = editor.get(base).json()
    edited = {**first["breakdown"], "hook": "A new hook."}
    second = editor.put(base, json=edited).json()
    stale = lambda: next(f for f in editor.get(url).json() if f["clip_id"] == frame.clip_id)[  # noqa: E731
        "stale"
    ]
    assert stale()  # its frame was made for the first breakdown

    shown = editor.get(f"{base}/versions").json()
    assert [(v["id"], v["current"]) for v in shown] == [(second["id"], True), (first["id"], False)]
    assert shown[0]["made_by"]["name"] and shown[0]["source"] == "edit"
    assert editor.post(f"{base}/versions/{second['id']}/use").status_code == 409  # in use
    assert editor.post(f"{base}/versions/999/use").status_code == 404

    back = editor.post(f"{base}/versions/{first['id']}/use").json()  # Go back to this: free
    assert back["breakdown"]["hook"] == first["breakdown"]["hook"]
    assert back["was_id"] == second["id"] and back["id"] > second["id"]  # history only grows
    assert not stale()  # made for the one gone back to: current again, nothing to redo
    undo = editor.post(f"{base}/versions/{back['was_id']}/use").json()
    assert undo["breakdown"]["hook"] == "A new hook." and stale()


def test_only_the_maker_or_the_owner_goes_back(app, db, owner, editor, setup):  # noqa: F811
    """QA-4 on #957: a second editor can open the video but not change what it uses (as Video
    settings); the owner and whoever made it can."""
    from tests.test_script_produce import _second_editor

    url, frame = _frame(app, db, editor, setup)
    row = _take_from(db, editor, frame)
    base = f"/projects/{setup['project']}"
    first = editor.get(f"{base}/breakdown").json()["id"]
    two, _ = _second_editor(app, owner, db)
    presses = [
        (f"{url}/frames/{frame.id}/pick", {"file_id": frame.file_id}),
        (f"{url}/versions/0/use", None),
        (f"{base}/clips/{row.id}/versions/1/use", None),
        (f"{base}/breakdown/versions/{first}/use", None),
    ]
    for path, body in presses:
        refused = two.post(path, json=body)
        assert refused.status_code == 403, path
        assert refused.json()["detail"].startswith("Only whoever made this video, or the owner")
    assert two.get(f"{url}/versions").status_code == 200  # reading stays open
    assert owner.post(presses[3][0]).status_code == 409  # the owner gets past it (in use)
    assert editor.post(presses[3][0]).status_code == 409  # and so does the maker


def test_go_back_waits_for_the_later_steps_being_made(app, db, editor, setup):  # noqa: F811
    """Flow-QA on #957: an Update everything after this run (or a new storyboard) still going
    would land on the breakdown being replaced and read out of date at once, after paying."""
    from app.models.breakdowns import BreakdownVersion
    from tests.test_update_after import _drain, _made

    url = f"/projects/{setup['project']}"
    providers = _made(app, db, editor, url)
    first = db.query(BreakdownVersion).order_by(BreakdownVersion.id).first().id
    assert editor.post(f"{url}/update-after").status_code == 202  # the run is queued
    busy = editor.post(f"{url}/breakdown/versions/{first}/use")
    assert (
        busy.status_code == 409 and "storyboard, stills and clip prompts" in busy.json()["detail"]
    )
    _drain(app, db, providers)
    _drain(app, db, providers)
    _drain(app, db, providers)
    assert editor.post(f"{url}/breakdown/versions/{first}/use").status_code == 200  # then free
