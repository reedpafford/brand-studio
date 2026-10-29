"""The advisory check on stills and takes (flows 1b, P4), on the free stand-in writer."""

import httpx2 as httpx
import pytest

from app.credits import credits_used
from app.models.checks import ItemCheck
from app.models.jobs import Job
from app.models.projects import Project
from app.providers.fake_local import FakeWriter
from app.providers.replicate import ReplicateProvider
from app.worker import run_once
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_replicate import BASE
from tests.test_storyboard import FakeNanoBanana, _frames, _with_breakdown


@pytest.fixture(autouse=True)
def checks_on(monkeypatch):
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins


def _check(app, db):
    run_once(db, {"claude": FakeWriter()}, app.state.storage, only={"claude"})


def test_a_take_gets_advice_looks_fine_and_the_review_list(app, db, editor, setup, clip):  # noqa: F811
    clips, url = f"/projects/{setup['project']}/clips", f"/projects/{setup['project']}/checks"
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    (take,) = editor.get(clips).json()[0]["takes"]
    assert take["check"]["status"] == "checking"  # never blocks: Approve works meanwhile
    assert editor.post(f"{clips}/{clip['id']}/approve").json()["approved"] is True
    _check(app, db)
    job = db.query(Job).filter(Job.kind == "check-claude").one()
    assert len(job.input["files"]["reference_images"]) == 1  # Mom's sheet; frames come first
    (shown,) = editor.get(clips).json()
    check = shown["takes"][0]["check"]
    assert check["status"] == "advice" and shown["approved"] is True  # approval untouched
    (finding,) = check["findings"]
    assert (finding["index"], finding["kind"]) == (0, "face")
    assert finding["text"] == "Their face may differ from their sheet"  # a ready note too
    assert finding["note"] == "Keep their face exactly as on their sheet."
    review = editor.get(url).json()
    assert [(i["kind"], i["label"]) for i in review["items"]] == [("take", "Clip c1 · take 1")]
    assert review["on"] is True and review["credits_per_check"] == 1
    fine = editor.post(f"{url}/{check['id']}/findings/0/dismiss").json()
    assert (fine["status"], fine["findings"]) == ("ok", [])
    assert db.get(ItemCheck, check["id"]).dismissed[0]["index"] == 0  # kept in its history
    assert editor.get(url).json()["items"] == []


def test_a_still_that_matches_says_so(app, db, editor, setup):  # noqa: F811
    mom = editor.post("/library/character",
                      json={"name": "Mom", "image_file_ids": [upload(editor)]}).json()  # fmt: skip
    with_sheet(db, mom["id"])
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": [mom["id"]]})
    _with_breakdown(app, db, editor, setup)
    url = f"/projects/{setup['project']}/storyboard"
    editor.post(url, json={})
    _run(app, db, FakeClaude(_frames(f"char:{mom['id']}", f"screen:{setup['screen']}")))
    frame = editor.get(url).json()[0]
    editor.post(f"{url}/frames/{frame['id']}/render")
    client = httpx.Client(transport=httpx.MockTransport(FakeNanoBanana()))
    for _ in range(2):
        run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage,
                 only={"replicate"})  # fmt: skip
    _check(app, db)
    assert editor.get(url).json()[0]["check"]["status"] == "ok"  # "Checked · matches the sheets"


def test_over_budget_is_skipped_and_a_failed_check_is_free(app, db, editor, setup, clip):  # noqa: F811
    clips = f"/projects/{setup['project']}/clips"
    project = db.get(Project, setup["project"])
    editor.post(f"{clips}/{clip['id']}/generate")
    spent = project.budget_credits - credits_used(db, project)  # this take is all that's left
    db.add(Job(workspace_id=project.workspace_id, kind="video", provider="fake", input={},
               project_id=project.id, credits=spent, status="succeeded"))  # fmt: skip
    db.commit()
    _work(app, db, FakeSeedance([_mp4("red")]))
    assert editor.get(clips).json()[0]["takes"][0]["check"]["status"] == "skipped"
    assert not db.query(Job).filter(Job.kind == "check-claude").count()

    db.query(Job).filter(Job.credits == spent, Job.provider == "fake").delete()
    db.commit()
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red"), _mp4("blue")]))
    before = credits_used(db, project)

    class Broken(FakeWriter):
        def run(self, kind, input):
            raise RuntimeError("no answer")

    run_once(db, {"claude": Broken()}, app.state.storage, only={"claude"})
    newest = editor.get(clips).json()[0]["takes"][-1]["check"]
    assert newest["status"] == "failed"  # "Couldn't check this one."
    held = db.query(Job).filter(Job.kind == "check-claude").one().credits
    assert held and credits_used(db, project) == before - held  # nothing charged
