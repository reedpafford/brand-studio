"""Breakdown preview on a library version: run (stand-in Claude), edit, save."""

from sqlalchemy import select

from app.models.jobs import Job
from app.providers import get_providers
from app.worker import run_once
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import SCRIPT, _make


def _work(app, db):
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings)
    for _ in range(3):
        run_once(db, providers, app.state.storage)


def test_preview_runs_on_the_version_with_its_cast_and_saves(app, db, owner):
    made = _make(owner, text=SCRIPT, reference_id="fomo-DehudnaAmce")
    base = f"/scripts/{made['id']}"
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    with_sheet(db, mia.json()["id"])
    slots = owner.post(f"{base}/cast", json={"role": "Mom"}).json()
    owner.post(f"{base}/cast/{slots[0]['id']}/lock", json={"library_item_id": mia.json()["id"]})
    nate = owner.post(f"{base}/cast", json={"role": "Nate", "description": "teen"}).json()[1]
    url = f"{base}/drafts/0/breakdown"
    assert owner.get(url).json() == {
        "breakdown": None,
        "problems": [],
        "seconds": 0,
        "running": False,
        "kept": [],
        "stale": False,
    }
    assert owner.get(f"{url}/estimate").json()["credits"] == 3
    job = owner.post(url)
    assert job.status_code == 201, job.text
    assert owner.post(url).status_code == 409  # one at a time
    sent = db.get(Job, job.json()["id"]).input
    assert (sent["script_id"], sent["script_text"]) == (made["id"], SCRIPT)  # JobOut.script_id
    prompt = sent["prompt"]
    assert f"char:{mia.json()['id']} | Mia" in prompt  # locked slot: its character
    assert f"slot:{nate['id']} | Nate | teen (no look yet)" in prompt  # unlocked slot
    assert "<reference>" in prompt and "1| SCENE 1" in prompt
    _work(app, db)
    done = owner.get(url).json()
    assert done["breakdown"]["clips"] and done["seconds"] > 0 and not done["running"]
    assert owner.get(base).json()["versions"][0]["has_breakdown"] is True
    saved = owner.put(url, json=BREAKDOWN).json()
    assert saved["seconds"] == 5 and saved["breakdown"]["hook"] == BREAKDOWN["hook"]
    removed = owner.delete(url).json()  # the screen's Undo PUTs it back
    assert (removed["breakdown"], removed["problems"]) == (None, [])
    assert owner.get(base).json()["versions"][0]["has_breakdown"] is False
    assert db.scalars(select(Job)).all()[-1].status == "succeeded"


def test_preview_follows_the_script_rules(app, owner, editor):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/drafts/0/breakdown"
    assert editor.get(url).status_code == 404  # not published: private
    owner.post(f"/scripts/{made['id']}/drafts/0/approve")
    owner.post(f"/scripts/{made['id']}/publish")
    assert editor.get(url).status_code == 200
    assert editor.put(url, json=BREAKDOWN).status_code == 403
    assert owner.post(url).status_code == 409  # published: final
    empty = _make(owner)
    assert owner.post(f"/scripts/{empty['id']}/drafts/0/breakdown").status_code == 422
    app.state.settings.generation_enabled = False
    try:
        mine = _make(editor, text=SCRIPT)
        assert editor.post(f"/scripts/{mine['id']}/drafts/0/breakdown").status_code == 503
    finally:
        app.state.settings.generation_enabled = True


def test_a_version_shows_its_estimate_clips_planner_and_original(owner, db):
    """The version panel (#243)."""
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    owner.put(f"{base}/drafts/0", json={"text": SCRIPT, "target_seconds": 40})
    owner.put(f"{base}/drafts/1", json={"text": SCRIPT + "\nNATE: Fine."})
    first, second = owner.get(base).json()["versions"]
    assert (first["variation_of"], second["variation_of"]) == (None, "A")
    assert (first["estimate_credits"], first["clips"], first["planned_by"]) == (40, 0, None)
    owner.put(f"{base}/drafts/0/breakdown", json=BREAKDOWN)
    first = owner.get(base).json()["versions"][0]
    assert first["clips"] == len(BREAKDOWN["clips"]) and first["planned_by"]["name"] == "Reed"
    assert first["estimate_credits"] == sum(c["seconds"] for c in BREAKDOWN["clips"])


def test_a_plan_goes_stale_when_the_words_change_and_its_advice_can_be_kept(owner, db):
    from app.models.script_library import ScriptDraft

    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/drafts/0/breakdown"
    saved = owner.put(url, json=BREAKDOWN).json()
    assert (saved["stale"], saved["kept"]) == (False, [])
    advice = "Advice: shot 2 runs a little long for its words"
    db.query(ScriptDraft).update({"breakdown_problems": [advice]})
    db.commit()
    assert owner.post(f"{url}/keep", json={"problem": advice}).json()["kept"] == [advice]
    assert owner.delete(f"{url}/keep", params={"problem": advice}).json()["kept"] == []
    owner.put(f"/scripts/{made['id']}/drafts/0", json={"text": SCRIPT + "\nMOM: Fine."})
    assert owner.get(url).json()["stale"] is True  # planned from the old words
    assert owner.put(url, json=BREAKDOWN).json()["stale"] is False  # saved again: current
    db.query(ScriptDraft).update({"breakdown_problems": [advice]})
    db.commit()
    owner.post(f"{url}/keep", json={"problem": advice})
    removed = owner.delete(url).json()  # removing the plan clears what was kept
    assert (removed["kept"], removed["stale"]) == ([], False)
