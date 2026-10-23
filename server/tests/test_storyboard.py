"""Storyboard frame prompts with a mocked Claude (no paid calls)."""

import copy
import json

import httpx2 as httpx

from app.models.jobs import Job
from app.providers.replicate import ReplicateProvider
from app.worker import run_once
from tests.conftest import PNG, upload
from tests.helpers import assert_hidden, assert_no_dollars
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_replicate import BASE


def _frames(char: str, screen: str) -> dict:
    return {
        "frames": [
            {
                "clip_id": "c1",
                "shot_id": "1.1",
                "prompt": "Generate a still of the mom from image 1 holding the wallet.",
                "reference_ids": [char, screen],
            }
        ]
    }


def _with_breakdown(app, db, editor, setup):  # noqa: F811
    editor.post(f"/projects/{setup['project']}/breakdown")
    _run(app, db, FakeClaude(BREAKDOWN))


def test_storyboard_frames_made_checked_and_edited(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/storyboard"
    assert editor.post(url, json={}).status_code == 409  # needs a breakdown first
    mom = editor.post(
        "/library/character", json={"name": "Mom", "image_file_ids": [upload(editor)]}
    ).json()["id"]
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": [mom]})
    _with_breakdown(app, db, editor, setup)

    job = editor.post(url, json={"per_shot": True})
    assert job.status_code == 201
    assert editor.post(url, json={}).status_code == 409  # one at a time
    char, screen = f"char:{mom}", f"screen:{setup['screen']}"
    fake = FakeClaude(_frames(char, screen))
    _run(app, db, fake)
    assert db.get(Job, job.json()["id"]).status == "succeeded"
    message = fake.requests[0]["messages"][0]["content"]
    assert "<image_model>\nname: Nano Banana 2.1" in message and "aspect: 9:16" in message
    assert f"{char} | character | Mom" in message and f"{screen} | screen | Buy" in message
    assert '"clips": [' in message and "<per_shot>true</per_shot>" in message

    frames = editor.get(url).json()
    assert [(f["clip_id"], f["problems"], f["stale"]) for f in frames] == [("c1", [], False)]
    edit = {"prompt": "Close on the wallet.", "reference_ids": [char, "char:999"]}
    edited = editor.put(f"{url}/frames/{frames[0]['id']}", json=edit).json()
    assert edited["prompt"] == "Close on the wallet."
    assert edited["problems"] == ["c1: unknown reference char:999"]
    too_many = {"prompt": "x", "reference_ids": [char] * 5}
    over = editor.put(f"{url}/frames/{frames[0]['id']}", json=too_many).json()
    assert over["problems"] == ["c1: more references than the image model keeps"]

    editor.put(f"/projects/{setup['project']}/breakdown", json=BREAKDOWN)  # a newer breakdown
    assert editor.get(url).json()[0]["stale"] is True


def test_storyboard_switch_workspace_and_dollars(app, db, editor, outsider, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/storyboard"
    assert_hidden(outsider, [("POST", url, {}), ("GET", url)])
    _with_breakdown(app, db, editor, setup)
    app.state.settings.generation_enabled = False
    try:
        assert editor.post(url, json={}).status_code == 503
    finally:
        app.state.settings.generation_enabled = True
    assert (
        editor.put(f"{url}/frames/999", json={"prompt": "x", "reference_ids": []}).status_code
        == 404
    )
    assert_no_dollars(editor, [url])


def test_breakdown_ids_must_be_the_projects(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/breakdown"
    bad = copy.deepcopy(BREAKDOWN)
    bad["scenes"][0]["shots"][0]["character_ids"] = ["char:999"]
    r = editor.put(url, json=bad)
    assert r.status_code == 422 and r.json()["detail"].startswith("shot 1.1: unknown char:999.")
    good = copy.deepcopy(BREAKDOWN)
    good["scenes"][0]["shots"][0]["screen_ids"] = [f"screen:{setup['screen']}"]
    assert editor.put(url, json=good).status_code == 200
    editor.post(url)  # Claude naming an unknown place is saved, with the problem shown
    bad["scenes"][0]["shots"][0]["character_ids"] = []
    bad["scenes"][0]["shots"][0]["place_id"] = "place:7"
    _run(app, db, FakeClaude(bad))
    assert "shot 1.1: unknown place:7" in editor.get(url).json()["problems"]


class FakeNanoBanana:
    """Replicate answering one image prediction: done on the first check, a PNG to fetch."""

    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        url = str(request.url)
        if request.method == "POST":
            return httpx.Response(201, json={"id": "p1", "status": "starting"})
        if url.endswith("/predictions/p1"):
            done = {"id": "p1", "status": "succeeded", "metrics": {"predict_time": 3.0}}
            return httpx.Response(200, json={**done, "output": "https://replicate.delivery/a.png"})
        if url == "https://replicate.delivery/a.png":
            return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
        return httpx.Response(404)


def test_render_a_frame_still(app, db, editor, setup):  # noqa: F811
    mom = editor.post(
        "/library/character", json={"name": "Mom", "image_file_ids": [upload(editor)]}
    ).json()
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": [mom["id"]]})
    _with_breakdown(app, db, editor, setup)
    url = f"/projects/{setup['project']}/storyboard"
    editor.post(url, json={})
    screen = f"screen:{setup['screen']}"
    _run(app, db, FakeClaude(_frames(f"char:{mom['id']}", screen)))
    frame = editor.get(url).json()[0]

    job = editor.post(f"{url}/frames/{frame['id']}/render")
    assert job.status_code == 201 and job.json()["credits"] == 0.33  # Nano Banana 2.1
    assert editor.post(f"{url}/frames/{frame['id']}/render").status_code == 409  # once
    fake = FakeNanoBanana()
    client = httpx.Client(transport=httpx.MockTransport(fake))
    for _ in range(2):
        run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage)
    sent = json.loads(next(q for q in fake.requests if q.method == "POST").content)["input"]
    assert sent["aspect_ratio"] == "9:16" and len(sent["image_input"]) == 2  # sheet, screen
    assert db.get(Job, job.json()["id"]).status == "succeeded"
    still = editor.get(url).json()[0]["file_id"]
    assert still and editor.get(f"/files/{still}").content == PNG

    stale = f"/projects/{setup['project']}/script"
    editor.put(stale, json={"text": editor.get(stale).json()["text"] + "\nMOM: Fine."})
    r = editor.post(f"{url}/frames/{frame['id']}/render")  # its breakdown is for an old script
    assert r.status_code == 409 and "older breakdown" in r.json()["detail"]
    editor.put(f"/projects/{setup['project']}/breakdown", json=BREAKDOWN)  # newer breakdown
    r = editor.post(f"{url}/frames/{frame['id']}/render")
    assert r.status_code == 409 and "older breakdown" in r.json()["detail"]
    editor.put(f"{url}/frames/{frame['id']}", json={"prompt": "x", "reference_ids": ["char:9"]})
    assert editor.post(f"{url}/frames/{frame['id']}/render").status_code == 409  # has problems
