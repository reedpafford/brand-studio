"""Write a library script's words with Claude: one script, or Write all after bulk create."""

from app.models.jobs import Job
from tests.test_script_library import SCRIPT, _make
from tests.test_script_preview import _work


def _bulk(client, n):
    fomo = client.get("/brands").json()[0]["id"]
    rows = [{"brand_id": fomo, "title": f"Idea {i}", "description": "Mom finds the wallet"}
            for i in range(n)]  # fmt: skip
    return [s["id"] for s in client.post("/scripts/bulk", json={"scripts": rows}).json()]


def test_write_one_script_from_its_title_and_description(app, db, owner):
    made = _make(owner, title="Dip", description="Mom finds the wallet", text=SCRIPT,
                 reference_id="fomo-DehudnaAmce")  # fmt: skip
    url = f"/scripts/{made['id']}"
    assert owner.get(f"{url}/write/estimate").json()["credits"] == 3
    job = owner.post(f"{url}/write")
    assert job.status_code == 201, job.text
    assert owner.post(f"{url}/write").status_code == 409  # one at a time
    prompt = db.get(Job, job.json()["id"]).input["prompt"]
    assert "Title: Dip" in prompt and "Goal: Mom finds the wallet" in prompt
    assert "<reference>" in prompt and prompt.rstrip().endswith("</reference>")
    _work(app, db)
    written = owner.get(url).json()["versions"][0]["text"]
    assert written != SCRIPT and "BRIDE: HELL NO!" in written  # the stand-in keeps reel lines
    (earlier,) = owner.get(f"{url}/drafts/0/history").json()
    assert (earlier["text"], earlier["source"]) == (SCRIPT, "write")
    owner.post(f"{url}/drafts/0/approve")
    assert owner.post(f"{url}/write").json()["detail"].endswith("the words are approved.")


def test_write_all_after_bulk_create_with_its_estimate(app, db, owner):
    ids = _bulk(owner, 3)
    est = owner.post("/scripts/write/estimate", json={"script_ids": ids}).json()
    assert (est["count"], est["credits"], est["credits_left"]) == (3, 9, None)  # owner: no cap
    assert (est["writing"], est["reading"], est["waiting"], est["failed"]) == (3, 0, [], [])
    jobs = owner.post("/scripts/write", json={"script_ids": ids})
    assert jobs.status_code == 201 and len(jobs.json()) == 3
    _work(app, db)
    assert all(owner.get(f"/scripts/{i}").json()["versions"][0]["text"] for i in ids)
    again = owner.post("/scripts/write", json={"script_ids": [ids[0]]})
    assert again.status_code == 201  # not approved yet: can be written again


def test_write_all_is_declined_past_an_editors_allowance_and_queues_nothing(owner, editor, db):
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 5, "per_video_max_credits": 729}
    )
    ids = _bulk(editor, 2)
    est = editor.post("/scripts/write/estimate", json={"script_ids": ids}).json()
    assert (est["credits"], est["credits_left"]) == (6, 5)
    declined = editor.post("/scripts/write", json={"script_ids": ids})
    assert declined.status_code == 409 and "6 credits" in declined.json()["detail"]
    assert db.query(Job).count() == 0  # all or none
    assert editor.post("/scripts/write", json={"script_ids": ids[:1]}).status_code == 201
