"""Omni edits (Reed, 9 Nov, runway item 7): "Change this…" on a nearly-right Omni take edits
that take (Omni's `video` input, up to 15 s, "keep everything else the same") instead of making
a new one; a note about the words or the timing makes a new take, saying why. Stand-ins and a
mocked Claude only: no paid calls."""

from decimal import Decimal

from app import change, clip_takes, model_map
from app.catalogue import get_model
from app.clip_takes import save_take
from app.credits import estimate, price
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.providers.replicate import _usage
from tests.conftest import upload
from tests.test_change_notes import _noted
from tests.test_clip_takes import clip  # noqa: F401 - fixture
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture


def _on_omni(db, editor, row: ProjectClip, seconds: int | None = None) -> ClipTake:
    """The clip on Omni 1.2 with an Omni take of it in use."""
    file_id = upload(editor)  # before this session writes (one writer at a time)
    row.model = {"id": model_map.OMNI, "why": "Realistic.", "by": "director"}
    row.prompt_ok = True
    video = db.get(Project, row.project_id)
    asked = {"duration": seconds or row.seconds, "resolution": "720p"}
    made = Job(workspace_id=video.workspace_id, created_by_id=video.created_by_id, kind="video",
               provider="fake", project_id=video.id, status="succeeded",
               input={"step": "clip_take", "project_clip_id": row.id, "model": model_map.OMNI,
                      "input": asked})  # fmt: skip
    db.add(made)
    db.flush()
    number = len(db.query(ClipTake).filter_by(clip_id=row.id).all()) + 1
    take = ClipTake(clip_id=row.id, number=number, job_id=made.id, file_id=file_id,
                    prompt=row.prompt)  # fmt: skip
    db.add(take)
    db.flush()
    row.picked_take_id, row.file_id = take.id, take.file_id
    db.commit()
    return take


def _change(app, db, editor, setup, clip, note: str) -> ProjectClip:  # noqa: F811
    url = f"/projects/{setup['project']}/clips/{clip['id']}/change"
    assert editor.post(url, json={"note": note}).status_code == 201
    _run(app, db, FakeClaude({"prompt": _noted(db.get(ProjectClip, clip["id"]).prompt, note)}))
    db.expire_all()
    return db.get(ProjectClip, clip["id"])


def test_an_edit_is_priced_from_its_own_catalogue_line():
    omni = get_model(model_map.OMNI)
    assert omni.edit.max_seconds == 15
    assert omni.usd_per_unit("720p", edit=True) == omni.edit.price.usd["720p"]
    job = {"model": omni.id, "edit": True, "input": {"resolution": "720p"}}
    assert estimate(None, 0, "video", Decimal(8), job) == 8 * omni.credits_per_unit("720p", True)
    sent = {"input": {"video": "https://x/take.mp4", "duration": 8, "resolution": "720p"}}
    assert _usage(omni, sent, 1).cost_usd == 8 * omni.edit.price.usd["720p"]  # as Usage records it


def test_a_visual_note_on_an_omni_take_edits_that_take(app, db, editor, setup, clip, monkeypatch):  # noqa: F811
    row = db.get(ProjectClip, clip["id"])
    take = _on_omni(db, editor, row)
    project = db.get(Project, row.project_id)
    url = f"/projects/{setup['project']}/clips/{clip['id']}/change"
    write = estimate(db, project.workspace_id, "write-claude", Decimal(1))
    edit = clip_takes.take_credits(db, project, row, edit=True)
    assert editor.get(url).json()["credits"] == price(write + edit)  # the price first
    row = _change(app, db, editor, setup, clip, "Warmer evening light, a red scarf on Mom.")
    assert row.change["how"] == change.EDITING.format(n=1)
    made = db.get(Job, row.change["made_job_id"])
    assert made.input["edit"] and made.input["edit_of"] == take.id
    assert made.input["files"] == {"video": [take.file_id]}  # the take, and no pictures
    assert made.input["input"]["prompt"] == (
        f"Warmer evening light, a red scarf on Mom. {change.KEEP}"
    )
    assert made.input["input"]["duration"] == row.seconds  # an edit keeps its length
    watched = []
    monkeypatch.setattr("app.take_watch.queue_safely", lambda db, job, t, c: watched.append(t))
    made.output = {"file_ids": [upload(editor)]}  # the edited take lands as any take does
    save_take(db, made)
    db.commit()
    row = db.get(ProjectClip, clip["id"])
    new = db.get(ClipTake, row.picked_take_id)
    assert new.number == 2 and watched == [new]  # picked, and watched like any take
    assert new.prompt == row.prompt and "red scarf" in row.prompt  # the clip's own prompt
    assert db.get(ClipTake, take.id).prompt is not None  # the take before stays: the Undo


def test_a_note_on_the_words_or_timing_makes_a_new_take_and_says_why(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    row = db.get(ProjectClip, clip["id"])
    _on_omni(db, editor, row)
    project = db.get(Project, row.project_id)
    assert change.editable(db, project, row, "She speaks softer.")[1] == change.NEW_TAKE["says"]
    assert change.editable(db, project, row, "A shorter pause.")[1] == change.NEW_TAKE["timed"]
    row = _change(app, db, editor, setup, clip, "Slower push in.")
    assert row.change["how"] == change.NEW_TAKE["timed"]  # the owner sees why
    made = db.get(Job, row.change["made_job_id"])
    assert "edit" not in made.input and "Slower push in." in made.input["clip_prompt"]
    take = _on_omni(db, editor, row, seconds=row.seconds + 2)  # the clip's length changed
    assert change.editable(db, project, row, "Brighter.") == (None, change.NEW_TAKE["length"])
    db.get(Job, take.job_id).input = {"model": "seedance-2.0", "input": {"duration": 5}}
    db.commit()
    assert change.editable(db, project, row, "Brighter.") == (None, "")  # not Omni: as ever


def test_the_director_may_edit_an_omni_take_instead_of_remaking_it(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    from app import director_tools
    from app.models.accounts import User

    row = db.get(ProjectClip, clip["id"])
    _on_omni(db, editor, row)
    project = db.get(Project, row.project_id)
    user = db.get(User, project.created_by_id)
    said = director_tools.run(db, user, project, {"tool": "make_take", "clip_id": row.clip_id,
                              "note": "Hide the coffee cup.", "edit_take": True}, None)  # fmt: skip
    assert said.endswith(f"{row.clip_id}: {change.EDITING.format(n=1)}")  # it says so
    job = db.get(Job, db.get(ProjectClip, row.id).change["job_id"])
    assert job.input["step"] == "change"  # through Change this…: it edits once rewritten


def test_a_revision_prices_an_omni_edit_as_an_edit(app, db, owner, editor):
    from app.revision import revision
    from app.routes import estimate as est
    from tests.test_revision_price import _one_clip, _prices

    pid, _, _ = _one_clip(app, db, owner, editor)  # "Make clip 1 brighter."
    video = db.get(Project, pid)
    (row,), _ = revision(db, video)
    row.model = {"id": model_map.OMNI, "why": "Realistic.", "by": "director"}
    taken = db.get(Job, db.get(ClipTake, row.picked_take_id).job_id)
    seconds = model_map.billed(get_model(model_map.OMNI), row.seconds)
    taken.input = {**taken.input, "model": model_map.OMNI,
                   "input": {**taken.input["input"], "duration": seconds}}  # fmt: skip
    db.commit()
    _, up_to, work = _prices(db, pid)
    assert work == clip_takes.take_credits(db, video, row, edit=True)  # no still drawn again
    still = est._still(db, video.workspace_id, video)
    assert up_to >= work + est._shots(db, video, [row]) * still  # the "up to" keeps a remake
