"""Omni edits (Reed, 9 Nov, runway item 7): "Change this…" on a nearly-right Omni take edits
that take (Omni's `video` input, up to 15 s, "keep everything else the same") instead of making
a new one. The prompt rewrite the note already makes judges whether it's a look change (an
edit) or more (a new take, saying why); the server checks Omni, 15 s, the same length and no
new picture itself. Stand-ins and a mocked Claude only: no paid calls."""

from decimal import Decimal

import pytest

from app import change, clip_prompts, clip_takes, model_map, prompts
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
    """The clip on Omni 1.2 with an Omni take of it in use, made from its pictures."""
    file_id = upload(editor)  # before this session writes (one writer at a time)
    row.model = {"id": model_map.OMNI, "why": "Realistic.", "by": "director"}
    row.prompt_ok = True
    video = db.get(Project, row.project_id)
    sent = clip_takes.take_input(db, video, row, check=False)["files"]  # as a take is sent
    asked = {"duration": seconds or row.seconds, "resolution": "720p"}
    made = Job(workspace_id=video.workspace_id, created_by_id=video.created_by_id, kind="video",
               provider="fake", project_id=video.id, status="succeeded",
               input={"step": "clip_take", "project_clip_id": row.id, "model": model_map.OMNI,
                      "input": asked, "files": sent})  # fmt: skip
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


def _change(app, db, editor, setup, clip, note: str, edit: bool, why: str) -> ProjectClip:  # noqa: F811
    """Change this… with the note, the rewrite judging it an edit or not (`edit`, `why`)."""
    url = f"/projects/{setup['project']}/clips/{clip['id']}/change"
    assert editor.post(url, json={"note": note}).status_code == 201
    after = _noted(db.get(ProjectClip, clip["id"]).prompt, note)
    _run(app, db, FakeClaude({"prompt": after, "edit": edit, "why": why}))
    db.expire_all()
    return db.get(ProjectClip, clip["id"])


def test_an_edit_is_priced_from_its_own_catalogue_line():
    omni = get_model(model_map.OMNI)
    assert omni.edit.max_seconds == 15
    assert omni.usd_per_unit("720p", edit=True) == omni.edit.price.usd["720p"]
    job = {"model": omni.id, "edit": True, "input": {"resolution": "720p"}}
    assert estimate(None, 0, "video", Decimal(8), job) == 8 * omni.credits_per_unit("720p", True)
    made = {"input": {"video": "https://x/take.mp4", "resolution": "720p"},
            "metrics": {"video_output_duration_seconds": 8}}  # fmt: skip
    assert _usage(omni, made, 1).cost_usd == 8 * omni.edit.price.usd["720p"]  # as Usage records


def test_a_look_note_on_an_omni_take_edits_that_take(app, db, editor, setup, clip, monkeypatch):  # noqa: F811
    row = db.get(ProjectClip, clip["id"])
    take = _on_omni(db, editor, row)
    project = db.get(Project, row.project_id)
    url = f"/projects/{setup['project']}/clips/{clip['id']}/change"
    write = estimate(db, project.workspace_id, "write-claude", Decimal(1))
    edit = clip_takes.take_credits(db, project, row, edit=True)
    assert editor.get(url).json()["credits"] == price(write + edit)  # the price first
    note = "Warmer evening light, a red scarf on Mom."
    row = _change(app, db, editor, setup, clip, note, True, "only the light and a scarf change")
    assert row.change["how"] == change.EDITING.format(n=1, why="only the light and a scarf change")
    made = db.get(Job, row.change["made_job_id"])
    assert made.input["edit"] and made.input["edit_of"] == take.id
    assert made.input["files"] == {"video": [take.file_id]}  # the take, and no pictures
    assert made.input["input"] == {"prompt": f"{note.rstrip('.')}. {change.KEEP}",
                                   "resolution": "720p"}  # no duration with `video`  # fmt: skip
    assert made.input["seconds"] == row.seconds  # its length, kept out of what's sent
    watched = []
    monkeypatch.setattr("app.take_watch.queue_safely", lambda db, job, t, c: watched.append(t))
    made.output = {"file_ids": [upload(editor)]}  # the edited take lands as any take does
    save_take(db, made)
    db.commit()
    clip_prompts.repair(db, project)  # as Clips opening runs it
    db.commit()
    row = db.get(ProjectClip, clip["id"])
    new = db.get(ClipTake, row.picked_take_id)
    assert new.number == 2 and watched == [new]  # picked, and watched like any take
    assert not clip_prompts.take_stale(row)  # made from its source's pictures: not out of date
    assert new.prompt == row.prompt and "red scarf" in row.prompt  # the clip's own prompt
    assert db.get(ClipTake, take.id).prompt is not None  # the take before stays: the Undo


@pytest.mark.parametrize(
    ("note", "edit", "why"),
    [
        ("She should sound angrier.", False, "the delivery changes"),
        ("Slowly push in on her.", False, "a camera move changes"),
        ("Make it 6s.", False, "the length changes"),
        ("Warmer colour tone.", True, "only the colour tone changes"),
        ("Shorter hair.", True, "only her hair changes"),
        ("Change the words on the poster to SALE.", True, "only the poster's text changes"),
    ],
)
def test_the_rewrite_judges_an_edit_or_a_new_take_and_says_why(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
    note,
    edit,
    why,
):
    assert "**A clip: edit or new take.**" in prompts.system("change")  # QA's cases, its guide
    _on_omni(db, editor, db.get(ProjectClip, clip["id"]))
    row = _change(app, db, editor, setup, clip, note, edit, why)
    made = db.get(Job, row.change["made_job_id"])
    assert bool(made.input.get("edit")) is edit
    line = change.EDITING if edit else change.NEW_TAKE
    assert row.change["how"] == line.format(n=1, why=why)  # the owner sees why


def test_the_servers_own_checks_make_a_new_take(app, db, editor, setup, clip):  # noqa: F811
    row = db.get(ProjectClip, clip["id"])
    project = db.get(Project, row.project_id)
    take = _on_omni(db, editor, row, seconds=row.seconds + 2)  # the clip's length changed
    assert change.editable(db, project, row) == (None, change.HARD["length"])
    db.get(Job, take.job_id).input = {"model": "seedance-2.0", "input": {"duration": 5}}
    db.commit()
    assert change.editable(db, project, row) == (None, "")  # not Omni: as ever, no line
    _on_omni(db, editor, row)
    row.references = [r for r in row.references if not r["id"].startswith("char:")]
    db.commit()  # the rewrite attaches Mom's sheet again: a picture an edit can't take
    row = _change(app, db, editor, setup, clip, "Mom holds the phone.", True, "a prop changes")
    assert any(r["id"].startswith("char:") for r in row.references)
    assert row.change["how"] == change.NEW_TAKE.format(why=change.HARD["pictures"])
    assert "edit" not in db.get(Job, row.change["made_job_id"]).input


def test_the_director_edits_only_a_take_omni_can_edit(app, db, editor, setup, clip):  # noqa: F811
    from app import director_tools
    from app.models.accounts import User

    row = db.get(ProjectClip, clip["id"])
    take = _on_omni(db, editor, row)
    project = db.get(Project, row.project_id)
    user = db.get(User, project.created_by_id)
    move = {"tool": "make_take", "clip_id": row.clip_id, "note": "Hide the cup.", "edit_take": True}
    said = director_tools.run(db, user, project, move, None)
    assert said.endswith(f"{row.clip_id}: {change.MAYBE.format(n=1)}")  # it says so
    row = db.get(ProjectClip, row.id)
    assert db.get(Job, row.change["job_id"]).input["step"] == "change"  # its rewrite judges it
    db.get(Job, row.change["job_id"]).status = "succeeded"  # done: the clip is free again
    db.get(Job, take.job_id).input = {**db.get(Job, take.job_id).input,
                                      "input": {"duration": row.seconds + 2}}  # fmt: skip
    db.commit()
    writes = db.query(Job).filter(Job.kind == "write-claude").count()
    said = director_tools.run(db, user, project, move, None)  # can't be edited: a plain redo
    assert f"{row.clip_id}: {change.NEW_TAKE.format(why=change.HARD['length'])}" in said
    assert db.query(Job).filter(Job.kind == "write-claude").count() == writes  # no rewrite


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


def test_only_text_on_a_thing_passes_the_dialogue_guard():
    from app.prompts.check import _rewords

    said = ["Change the dialogue in clip 2", "Reword the line in shot 3", "Cut the line in the "
            "middle", "Add a line in Spanish", "Swap the lines in the second half", "Change her "
            "line in the kitchen", "Drop the line on the phone call", "Change the words on the "
            "phone call", "Change the words on the poster and reword the line"]  # fmt: skip
    assert [n for n in said if not _rewords(n)] == []  # every one still refused
    assert not _rewords("Change the words on the poster to SALE.")  # text in the picture
    assert not _rewords("Make the text on her shirt read FOMO.")


def test_an_edit_with_no_reported_length_is_recorded_at_its_takes_seconds():
    from app.providers import Result, UsageItem
    from app.providers.fake import FakeProvider
    from app.worker import _usage as recorded

    job = Job(workspace_id=1, provider="replicate", kind="video", credits=Decimal(6),
              input={"edit": True, "seconds": 5})  # fmt: skip
    longest = UsageItem(Decimal(15), "second", Decimal("1.65"), True)  # Omni's longest, guessed
    (row,) = recorded(job, FakeProvider(), Result("succeeded", usage=[longest]))
    assert (row.units, row.cost_usd, row.estimated) == (5, Decimal("0.55"), True)
