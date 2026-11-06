"""The advisory check on stills (flows 1b, P4), on the free stand-in writer. A take is
watched by the director instead: tests/test_take_watch.py."""

import httpx2 as httpx
import pytest

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
    assert editor.get(url).json()[0]["check"] is None  # by default stills aren't checked
    monkeypatch.setattr("app.item_checks.scope", lambda: "everything")
    draw()
    assert editor.get(url).json()[0]["check"]["status"] == "advice"
    review = editor.get(f"/projects/{setup['project']}/checks").json()
    assert review["check_credits_per_video"] == 2  # a still and a take's watch: 1.4
