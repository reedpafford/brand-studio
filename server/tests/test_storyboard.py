"""Storyboard frame prompts with a mocked Claude (no paid calls)."""

import copy
import json

import httpx2 as httpx

from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.storyboards import StoryboardFrame
from app.providers.replicate import ReplicateProvider
from app.worker import run_once
from tests.conftest import PNG, upload
from tests.helpers import assert_hidden, assert_no_dollars, with_sheet
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
    with_sheet(db, mom)
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
    assert edited["problems"] == ["A character that isn't part of this video"]
    too_many = {"prompt": "x", "reference_ids": [char] * 5}
    over = editor.put(f"{url}/frames/{frames[0]['id']}", json=too_many).json()
    assert over["problems"] == ["More references than the image model keeps"]
    bd = db.get(BreakdownVersion, db.get(StoryboardFrame, frames[0]["id"]).breakdown_id)
    shot = bd.data["scenes"][0]["shots"][0]
    bd.data = {
        **bd.data,
        "scenes": [{**bd.data["scenes"][0], "shots": [{**shot, "character_ids": [char]}]}],
    }
    db.commit()
    no_mom = editor.put(
        f"{url}/frames/{frames[0]['id']}", json={"prompt": "x", "reference_ids": []}
    )
    assert no_mom.json()["reference_ids"] == [char]  # her sheet comes back on its own
    assert no_mom.json()["problems"] == []
    assert no_mom.json()["prompt"] == "x Keep Mom from image 1 exactly as on their sheet."
    db.get(LibraryItem, mom).sheet_approved = False  # no approved look: named, never an id
    db.commit()
    no_look = editor.put(
        f"{url}/frames/{frames[0]['id']}", json={"prompt": "x", "reference_ids": []}
    )
    assert no_look.json()["problems"] == ["Mom has no approved look yet. Approve one in Assets."]

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
    assert r.status_code == 422 and r.json()["detail"] == (
        "shot 1.1: a character that isn't part of this video. "
        "Pick from the video's cast, places and screens."
    )
    good = copy.deepcopy(BREAKDOWN)
    good["scenes"][0]["shots"][0]["screen_ids"] = [f"screen:{setup['screen']}"]
    assert editor.put(url, json=good).status_code == 200
    editor.post(url)  # Claude naming an unknown place is saved, with the problem shown
    bad["scenes"][0]["shots"][0]["character_ids"] = []
    bad["scenes"][0]["shots"][0]["place_id"] = "place:7"
    _run(app, db, FakeClaude(bad))
    assert "shot 1.1: a place that isn't part of this video" in editor.get(url).json()["problems"]


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
    with_sheet(db, mom["id"])
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
    assert job.json()["frame_id"] == frame["id"] and job.json()["step"] == "frame"
    from app.models.library import LibraryItem

    db.get(LibraryItem, mom["id"]).sheet_approved = False  # e.g. Mom was edited since
    db.commit()
    r = editor.post(f"{url}/frames/{frame['id']}/render")
    assert (r.status_code, r.json()["detail"]) == (422, "Approve Mom's sheet first.")
    with_sheet(db, mom["id"])
    # A place named in the frame's shot needs an approved sheet too, even if the frame
    # doesn't attach it: editors find out here, before spending on stills.
    from app.models.breakdowns import BreakdownVersion

    kitchen = editor.post(
        "/library/place",
        json={"name": "Kitchen", "image_file_ids": [upload(editor)]},
    ).json()["id"]
    bd = db.get(BreakdownVersion, frame_breakdown(db, frame["id"]))
    data = copy.deepcopy(bd.data)
    data["scenes"][0]["shots"][0]["place_id"] = f"place:{kitchen}"
    bd.data = data
    db.commit()
    r = editor.post(f"{url}/frames/{frame['id']}/render")
    assert (r.status_code, r.json()["detail"]) == (422, "Approve Kitchen's sheet first.")
    with_sheet(db, kitchen)
    fid = frame["id"]
    assert editor.post(f"{url}/frames/{fid}/approve").json()["approved"] is True
    assert editor.delete(f"{url}/frames/{fid}/approve").json()["approved"] is False
    editor.post(f"{url}/frames/{fid}/approve")
    redo = editor.post(f"{url}/frames/{fid}/render", json={"note": "Make Mom angrier."})
    assert redo.status_code == 201
    fake = FakeNanoBanana()
    client = httpx.Client(transport=httpx.MockTransport(fake))
    for _ in range(2):
        run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage)
    sent = json.loads(next(q for q in fake.requests if q.method == "POST").content)["input"]
    assert sent["prompt"].endswith("Change from the last still: Make Mom angrier.")
    after = editor.get(url).json()[0]
    assert after["approved"] is False and after["prompt"] == frame["prompt"]  # note not kept
    editor.post(f"{url}/frames/{fid}/approve")

    stale = f"/projects/{setup['project']}/script"
    editor.put(stale, json={"text": editor.get(stale).json()["text"] + "\nMOM: Fine."})
    r = editor.post(f"{url}/frames/{frame['id']}/render")  # its breakdown is for an old script
    assert r.status_code == 409 and "older breakdown" in r.json()["detail"]
    assert editor.get(url).json()[0]["approved"] is False  # stale frames aren't approved
    assert editor.post(f"{url}/frames/{fid}/approve").status_code == 409
    editor.put(f"/projects/{setup['project']}/breakdown", json=BREAKDOWN)  # newer breakdown
    r = editor.post(f"{url}/frames/{frame['id']}/render")
    assert r.status_code == 409 and "older breakdown" in r.json()["detail"]
    editor.put(f"{url}/frames/{frame['id']}", json={"prompt": "x", "reference_ids": ["char:9"]})
    assert editor.post(f"{url}/frames/{frame['id']}/render").status_code == 409  # has problems


def test_products_are_labelled_as_products(app, db, editor, setup):  # noqa: F811
    from app.models.projects import Project
    from app.storyboard import assets

    brand = editor.get(f"/projects/{setup['project']}").json()["brand_id"]
    bag = editor.post(
        f"/brands/{brand}/screens",
        json={"name": "Bag", "file_id": upload(editor), "tags": ["product", "bag"]},
    ).json()["id"]
    lines = {k: line for k, (line, _) in assets(db, db.get(Project, setup["project"])).items()}
    assert lines[f"screen:{bag}"].startswith(f"screen:{bag} | product | Bag | fomo product,")
    assert "fomo app screen" in lines[f"screen:{setup['screen']}"]


def frame_breakdown(db, frame_id):
    from app.models.storyboards import StoryboardFrame

    return db.get(StoryboardFrame, frame_id).breakdown_id
