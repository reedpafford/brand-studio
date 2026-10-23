"""Script drafts and the stored reference breakdown, with a mocked Claude (no paid calls)."""

import json
from pathlib import Path

from app.models.jobs import Job, Usage
from tests.helpers import assert_hidden, assert_no_dollars
from tests.test_enhance import FakeClaude, _run

REFERENCE = Path(__file__).parents[2] / "docs/references/fomo-DehudnaAmce/BREAKDOWN.json"
DRAFTS = {
    "drafts": [
        {"hook_idea": "Mom finds the wallet", "script": "SCENE 1\nMOM: Where is it?"},
        {"hook_idea": "A dare", "script": "SCENE 1\nNATE: Bet I can."},
    ]
}


def _project(owner, editor) -> int:
    fomo = owner.get("/brands").json()[0]["id"]
    body = {"brand_id": fomo, "name": "Dip", "planned_seconds": 30, "goal": "Show the dip"}
    return editor.post("/projects", json=body).json()["id"]


def test_draft_pick_one_and_it_becomes_the_script(app, db, owner, editor):
    project = _project(owner, editor)
    url = f"/projects/{project}/script"
    job = editor.post(f"{url}/draft")
    assert job.status_code == 201 and job.json()["credits"] == 3
    assert editor.post(f"{url}/draft").status_code == 409  # one set at a time
    assert editor.get(f"{url}/drafts").json() == []
    fake = FakeClaude(DRAFTS)
    _run(app, db, fake)
    assert db.get(Job, job.json()["id"]).status == "succeeded"
    assert db.query(Usage).one().unit == "call"
    sent = fake.requests[0]
    assert "Goal: Show the dip" in sent["messages"][0]["content"]
    assert "<reference>" not in sent["messages"][0]["content"]

    drafts = editor.get(f"{url}/drafts").json()
    assert [(d["n"], d["hook_idea"]) for d in drafts] == [
        (1, "Mom finds the wallet"),
        (2, "A dare"),
    ]
    used = editor.post(f"{url}/drafts/{drafts[1]['job_id']}/2/use")
    assert used.status_code == 201 and used.json()["source"] == "draft"
    assert editor.get(url).json()["text"] == "SCENE 1\nNATE: Bet I can."
    assert editor.post(f"{url}/drafts/{drafts[1]['job_id']}/3/use").status_code == 404


def test_reference_breakdown_is_checked_and_sent(app, db, owner, editor):
    project = _project(owner, editor)
    breakdown = json.loads(REFERENCE.read_text())
    bad = editor.patch(f"/projects/{project}", json={"reference_breakdown": {"logline": "x"}})
    assert bad.status_code == 422
    assert bad.json()["detail"].startswith("The reference breakdown doesn't fit: duration_seconds")
    broken = {**breakdown, "shots": [{"n": 1}]}
    r = editor.patch(f"/projects/{project}", json={"reference_breakdown": broken})
    assert r.status_code == 422 and "shots.0.start" in r.json()["detail"]

    body = {"reference_breakdown": breakdown, "reference_replace": "the montage"}
    saved = editor.patch(f"/projects/{project}", json=body).json()
    assert saved["reference_replace"] == "the montage"
    assert "montage" not in saved["reference_breakdown"]  # trimmed to what the prompts use
    editor.post(f"/projects/{project}/script/draft")
    fake = FakeClaude(DRAFTS)
    _run(app, db, fake)
    message = fake.requests[0]["messages"][0]["content"]
    assert "<reference>" in message and "Replace: the montage" in message
    cleared = editor.patch(f"/projects/{project}", json={"reference_breakdown": None})
    assert cleared.json()["reference_breakdown"] is None


def test_drafts_respect_the_switch_workspaces_and_dollars(app, owner, editor, outsider):
    project = _project(owner, editor)
    url = f"/projects/{project}/script"
    assert_hidden(outsider, [("POST", f"{url}/draft"), ("GET", f"{url}/drafts")])
    assert_no_dollars(editor, [f"{url}/drafts"])
    app.state.settings.generation_enabled = False
    try:
        assert editor.post(f"{url}/draft").status_code == 503
    finally:
        app.state.settings.generation_enabled = True
