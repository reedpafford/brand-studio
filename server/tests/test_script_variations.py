"""Variations of a library script: one price per run, slots 1 and 2, regenerate kept apart."""

from app.models.jobs import Job
from app.models.script_library import Script, ScriptDraft
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_script_library import SCRIPT, _make
from tests.test_script_preview import _work

LONGER = SCRIPT + "\nMOM: You bought the dip with my birthday money?\nNATE: It was on sale, Mom."


def test_write_two_variations_then_regenerate_one(app, db, owner):
    made = _make(owner, text=LONGER, reference_id="fomo-DehudnaAmce")
    base = f"/scripts/{made['id']}"
    url = f"{base}/variations"
    assert owner.post(url, json={}).json()["detail"] == "Approve the original first."
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    with_sheet(db, mia.json()["id"])
    mom = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    owner.post(f"{base}/cast/{mom}/lock", json={"library_item_id": mia.json()["id"]})
    owner.post(f"{base}/drafts/0/approve")
    assert owner.get(f"{url}/estimate").json()["credits"] == 3  # one call, one price

    job = owner.post(url, json={})
    assert job.status_code == 201, job.text
    assert owner.post(url, json={}).status_code == 409  # one run at a time
    prompt = db.get(Job, job.json()["id"]).input["prompt"]
    assert "<count>2</count>" in prompt and f"char:{mia.json()['id']} Mia (Mom)" in prompt
    assert "<reference>" in prompt and "<keep_apart>" not in prompt
    _work(app, db)
    versions = owner.get(base).json()["versions"]
    assert [v["slot"] for v in versions] == [0, 1, 2]
    first = versions[1]
    assert first["title"] == "Local variation 1" and first["status"] == "draft"
    assert first["text"] != LONGER and first["premise"] and first["changes"]
    assert first["text"].splitlines()[-1] == LONGER.splitlines()[-1]  # the last line stays

    owner.post(f"{base}/drafts/1/approve")
    assert owner.post(url, json={"slots": [1]}).status_code == 409  # approved: can't change
    again = owner.post(url, json={"slots": [2], "note": "make it about a car"})
    assert again.status_code == 201, again.text
    prompt = db.get(Job, again.json()["id"]).input["prompt"]
    assert "<count>1</count>" in prompt and "<note>make it about a car</note>" in prompt
    assert f"<keep_apart>\n{first['text']}" in prompt  # stay apart from the approved one
    _work(app, db)
    rows = {d.slot: d for d in db.query(ScriptDraft).filter_by(script_id=made["id"])}
    assert rows[1].text == first["text"] and rows[1].status == "approved"  # untouched
    assert rows[2].job_id == again.json()["id"] and rows[2].text not in (first["text"], LONGER)


def test_variations_follow_the_script_rules(owner, editor):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/variations"
    assert editor.post(url, json={}).status_code == 404  # private until published
    assert owner.post(url, json={"slots": [0]}).status_code == 422  # only slots 1 and 2
    mine = _make(editor, text=SCRIPT)
    editor.post(f"/scripts/{mine['id']}/drafts/0/approve")
    made = editor.post(f"/scripts/{mine['id']}/variations", json={"slots": [1]})
    assert made.status_code == 201  # on the editor's own allowance


def test_publish_waits_for_variations_and_a_late_result_is_dropped(app, db, owner):
    """QA #234: a published script is final, so variations can't land in it."""
    made = _make(owner, text=LONGER)
    base = f"/scripts/{made['id']}"
    owner.post(f"{base}/drafts/0/approve")
    assert owner.post(f"{base}/variations", json={}).status_code == 201
    blocked = owner.post(f"{base}/publish")
    assert blocked.status_code == 409 and "still writing" in blocked.json()["detail"]
    db.query(Script).filter_by(id=made["id"]).update({"published": True})  # published anyway
    db.commit()
    _work(app, db)
    assert [d.slot for d in db.query(ScriptDraft).filter_by(script_id=made["id"])] == [0]


def test_a_regenerated_variation_keeps_its_earlier_text(app, db, owner):
    made = _make(owner, text=LONGER)
    base = f"/scripts/{made['id']}"
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/variations", json={"slots": [1]})
    _work(app, db)
    first = owner.get(base).json()["versions"][1]["text"]
    owner.put(f"{base}/drafts/2", json={"text": "NATE: Kept apart."})  # the stand-in then differs
    owner.post(f"{base}/variations", json={"slots": [1], "note": "again"})
    _work(app, db)
    (earlier,) = owner.get(f"{base}/drafts/1/history").json()
    assert (earlier["text"], earlier["source"]) == (first, "variations")
