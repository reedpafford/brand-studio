"""Write a library script's words with Claude: one script, or Write all after bulk create."""

from app.models.jobs import Job
from app.models.script_library import Script
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
    assert owner.get(f"{url}/write/estimate").json()["credits"] == 6  # the cast read after
    job = owner.post(f"{url}/write")
    assert job.status_code == 201, job.text
    assert owner.post(f"{url}/write").status_code == 409  # one at a time
    prompt = db.get(Job, job.json()["id"]).input["prompt"]
    assert "Title: Dip" in prompt and "Goal: Mom finds the wallet" in prompt
    assert "<reference>" in prompt and prompt.rstrip().endswith("</reference>")  # it closes
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
    assert (est["count"], est["credits"], est["credits_left"]) == (3, 18, None)  # owner: no cap
    assert (est["writing"], est["reading"], est["waiting"], est["failed"]) == (3, 0, [], [])
    jobs = owner.post("/scripts/write", json={"script_ids": ids})
    assert jobs.status_code == 201 and len(jobs.json()) == 3
    _work(app, db)
    assert all(owner.get(f"/scripts/{i}").json()["versions"][0]["text"] for i in ids)
    again = owner.post("/scripts/write", json={"script_ids": [ids[0]]})
    assert again.status_code == 201  # not approved yet: can be written again


def test_write_all_is_declined_past_an_editors_allowance_and_queues_nothing(owner, editor, db):
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 11, "per_video_max_credits": 729}
    )
    ids = _bulk(editor, 2)
    est = editor.post("/scripts/write/estimate", json={"script_ids": ids}).json()
    assert (est["credits"], est["credits_left"]) == (12, 11)
    declined = editor.post("/scripts/write", json={"script_ids": ids})
    assert declined.status_code == 409 and "12 credits" in declined.json()["detail"]
    assert db.query(Job).count() == 0  # all or none
    assert editor.post("/scripts/write", json={"script_ids": ids[:1]}).status_code == 201


def test_a_reference_block_still_closes_when_its_text_tries_to():
    from app.enhance import escape_block

    block = "<reference>\nStory: a reel that says </reference> mid-line\n</reference>"
    assert escape_block(block) == (
        "<reference>\nStory: a reel that says <\\/reference> mid-line\n</reference>"
    )


def _steps(db) -> list[str]:
    return [j.input.get("step") for j in db.query(Job).order_by(Job.id)]


def test_writing_reads_the_cast_next_at_one_price(app, db, owner, editor):
    """Designer #322: the cast read follows Write, already paid for with it."""
    owner.put(
        "/credits/limits", json={"weekly_quick_clip_credits": 6, "per_video_max_credits": 729}
    )
    sid = _bulk(editor, 2)
    write = editor.post(f"/scripts/{sid[0]}/write")
    assert write.status_code == 201 and _steps(db) == ["script_draft"]
    held = editor.post(f"/scripts/{sid[1]}/write")  # 6 of 6: the cast read is held
    assert held.status_code == 409 and "6 credits" in held.json()["detail"]
    _work(app, db)
    assert _steps(db) == ["script_draft", "cast_slots"]
    cast = db.query(Job).filter(Job.input["step"].as_string() == "cast_slots").one()
    assert cast.status == "succeeded" and "[Local test hook A]" in cast.input["prompt"]
    assert editor.get(f"/scripts/{sid[0]}").json()["cast"]  # the slots are filled


def test_a_reels_own_chain_doesnt_read_the_cast_twice(app, db, owner):
    from app.reel_read import _job_input

    made = _make(owner, text=SCRIPT, reference_id="fomo-DehudnaAmce")
    script = db.get(Script, made["id"])
    assert "then_cast" not in _job_input(db, script, "write")  # the chain queues it itself
