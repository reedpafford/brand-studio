"""Breakdown step with a mocked Claude (no paid calls)."""

import copy

from app.models.jobs import Job
from tests.helpers import assert_hidden, assert_no_dollars
from tests.test_enhance import SCRIPT, FakeClaude, _run, setup  # noqa: F401 - fixture


def _shot(id, lines, speaker, line, seconds):
    return {
        "id": id,
        "script_lines": lines,
        "speaker": speaker,
        "line": line,
        "action": "They argue.",
        "reaction": None,
        "camera": "Close-up, push in",
        "seconds": seconds,
        "character_ids": [],
        "place_id": None,
        "moment": None,
        "screen_ids": [],
    }


BREAKDOWN = {
    "hook": "Mom bursts in with the empty wallet.",
    "scenes": [
        {
            "id": 1,
            "heading": "INT. KITCHEN — MORNING",
            "look": "Cold morning light.",
            "shots": [
                _shot("1.1", [2, 3], "Mom", "Nate, where is all your money?", 2.5),
                _shot("1.2", [4], "Nate", "I bought the dip.", 1.5),
            ],
        }
    ],
    "clips": [{"id": "c1", "shot_ids": ["1.1", "1.2"], "seconds": 5, "seam": "End of scene."}],
}


def test_breakdown_made_checked_and_edited(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/breakdown"
    assert editor.get(url).status_code == 404
    job = editor.post(url)
    assert job.status_code == 201 and job.json()["credits"] == 3
    assert editor.post(url).status_code == 409  # one at a time
    fake = FakeClaude(BREAKDOWN)
    _run(app, db, fake)
    assert db.get(Job, job.json()["id"]).status == "succeeded"
    sent = fake.requests[0]
    assert sent["max_tokens"] == 32000
    message = sent["messages"][0]["content"]
    assert "<places>" in message and "<video_model>Seedance 2.5: 4–30 s" in message
    assert "3| MOM: Nate, where is all your money?" in message

    got = editor.get(url).json()
    assert (got["source"], got["problems"], got["stale"]) == ("claude", [], False)
    assert got["breakdown"]["clips"][0]["shot_ids"] == ["1.1", "1.2"]

    edited = copy.deepcopy(BREAKDOWN)
    edited["scenes"][0]["shots"].pop()
    edited["clips"][0]["shot_ids"] = ["1.1"]
    saved = editor.put(url, json=edited).json()
    assert saved["source"] == "edit" and "line 4 is in no shot" in saved["problems"]
    assert editor.get(url).json()["id"] == saved["id"]

    editor.put(f"/projects/{setup['project']}/script", json={"text": SCRIPT + "\nMOM: Fine."})
    assert editor.get(url).json()["stale"] is True


def test_breakdown_needs_a_script_switch_and_workspace(app, editor, outsider, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/breakdown"
    assert_hidden(outsider, [("POST", url), ("GET", url), ("PUT", url, BREAKDOWN)])
    app.state.settings.generation_enabled = False
    try:
        assert editor.post(url).status_code == 503
    finally:
        app.state.settings.generation_enabled = True
    editor.post(url)
    assert_no_dollars(editor, [f"/projects/{setup['project']}"])
