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
from tests.conftest import run_writer, upload
from tests.helpers import with_sheet
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_replicate import BASE
from tests.test_storyboard import FakeNanoBanana, _frames, _with_breakdown


@pytest.fixture(autouse=True)
def checks_on(monkeypatch):
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins


def test_a_take_gets_advice_looks_fine_and_the_review_list(app, db, editor, setup, clip):  # noqa: F811
    clips, url = f"/projects/{setup['project']}/clips", f"/projects/{setup['project']}/checks"
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    (take,) = editor.get(clips).json()[0]["takes"]
    assert take["check"]["status"] == "checking"  # never blocks: Approve works meanwhile
    assert editor.post(f"{clips}/{clip['id']}/approve").json()["approved"] is True
    editor.delete(f"{clips}/{clip['id']}/approve")
    run_writer(app, db)
    job = db.query(Job).filter(Job.kind == "check-claude").one()
    assert len(job.input["files"]["reference_images"]) == 1  # Mom's sheet; frames come first
    assert job.input["take_frames"]["count"] == 1  # key_takes: one frame keeps it to cents
    assert editor.post(f"{clips}/approve-all").json()["approved_with_advice"] == 1
    assert (
        editor.post(f"{clips}/approve-all").json()["approved_with_advice"] == 0
    )  # only this press's
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
    assert review["check_credits_per_video"] == 1  # one speaking clip: 0.2, rounded up
    fine = editor.post(f"{url}/{check['id']}/findings/0/dismiss").json()
    assert (fine["status"], fine["findings"]) == ("ok", [])
    assert db.get(ItemCheck, check["id"]).dismissed[0]["index"] == 0  # kept in its history
    assert editor.get(url).json()["items"] == []
    back = editor.post(f"{url}/{check['id']}/findings/0/restore").json()  # Undo of Looks fine
    assert back["status"] == "advice" and len(back["findings"]) == 1
    assert len(editor.get(url).json()["items"]) == 1
    assert editor.post(f"{url}/{check['id']}/findings/5/restore").status_code == 404


def test_stills_are_checked_only_when_the_scope_is_everything(app, db, editor, setup, monkeypatch):  # noqa: F811, E501
    mom = editor.post("/library/character",
                      json={"name": "Mom", "image_file_ids": [upload(editor)]}).json()  # fmt: skip
    with_sheet(db, mom["id"])
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": [mom["id"]]})
    _with_breakdown(app, db, editor, setup)
    url = f"/projects/{setup['project']}/storyboard"
    editor.post(url, json={})
    _run(app, db, FakeClaude(_frames(f"char:{mom['id']}", f"screen:{setup['screen']}")))
    frame = editor.get(url).json()[0]

    def draw():
        editor.post(f"{url}/frames/{frame['id']}/render")
        client = httpx.Client(transport=httpx.MockTransport(FakeNanoBanana()))
        replicate = ReplicateProvider(BASE, client, token="test-token")
        for _ in range(2):
            run_once(db, {"replicate": replicate}, app.state.storage, only={"replicate"})
        run_writer(app, db)

    draw()
    assert editor.get(url).json()[0]["check"] is None  # key_takes: stills aren't checked
    monkeypatch.setattr("app.item_checks.scope", lambda: "everything")
    draw()
    assert editor.get(url).json()[0]["check"]["status"] == "advice"
    review = editor.get(f"/projects/{setup['project']}/checks").json()
    assert review["check_credits_per_video"] == 1  # a still and a take for its one clip: 0.4


def test_over_budget_is_skipped_and_a_failed_check_is_free(app, db, editor, setup, clip):  # noqa: F811
    clips = f"/projects/{setup['project']}/clips"
    project = db.get(Project, setup["project"])
    editor.post(f"{clips}/{clip['id']}/generate")
    # after this take, 1 credit is left: enough for a check, not for one more take
    spent = project.budget_credits - credits_used(db, project) - 1
    db.add(Job(workspace_id=project.workspace_id, kind="video", provider="fake", input={},
               project_id=project.id, credits=spent, status="succeeded"))  # fmt: skip
    db.commit()
    _work(app, db, FakeSeedance([_mp4("red")]))
    assert editor.get(clips).json()[0]["takes"][0]["check"]["status"] == "skipped"
    assert editor.get(f"/projects/{setup['project']}/checks").json()["paused"] is True  # PL7
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


def test_a_narrators_lines_dont_make_a_clip_key(app, db, editor, setup, clip, monkeypatch):  # noqa: F811
    url = f"/projects/{setup['project']}/checks"
    assert editor.get(url).json()["check_credits_per_video"] == 1  # Mom speaks: one key take
    monkeypatch.setattr("app.item_checks.video_format", lambda db, project: "narrated")
    assert editor.get(url).json()["check_credits_per_video"] == 0  # heard over the picture
