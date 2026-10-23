"""Storyboard frame prompts with a mocked Claude (no paid calls)."""

from app.models.jobs import Job
from tests.conftest import upload
from tests.helpers import assert_hidden, assert_no_dollars
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture


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
