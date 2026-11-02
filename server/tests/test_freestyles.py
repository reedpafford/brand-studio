"""Freestyle (Reed's v4): an editor's every send waits for the owner before anything is spent;
the owner's run straight away. One clip works end to end on the stand-ins; the director-run
types answer that they're coming next."""

from app.credits import credits_left
from app.models.accounts import User
from app.models.jobs import Job
from app.providers.fake_local import FakeMedia
from app.worker import run_once
from tests.conftest import first_brand

SCRIPT = "MIA: The market opened at nine.\nLEO: And we were ready."
HOUSE = {"type": "one_clip", "look": "house", "shape": "9:16"}


def _run(app, db):
    media = FakeMedia()
    for _ in range(3):
        run_once(db, {"replicate": media}, app.state.storage)


def _moves(fs):
    return [(t["kind"], t["status"], t["text"]) for t in fs["thread"]]


def test_an_editors_sends_wait_for_the_owner_and_a_decline_says_why(app, owner, editor, db):
    ed = db.query(User).filter_by(email="ed@example.com").one()
    left = credits_left(db, ed)
    r = editor.post("/freestyles", json={**HOUSE, "brand_id": first_brand(owner), "text": SCRIPT})
    assert r.status_code == 201, r.text
    fs = r.json()
    assert (fs["title"], fs["status"], fs["file_id"]) == ("MIA: The market opened at nine.",
                                                          "waiting", None)  # fmt: skip
    assert _moves(fs) == [
        ("message", None, SCRIPT),
        ("move", "held", "Waiting for the owner's OK."),
    ]
    assert fs["thread"][0]["who"] == "Ed" and fs["credits"] > 0
    (job,) = db.query(Job).all()
    assert job.status == "needs_owner_approval" and job.input["held"]
    assert job.input["input"]["aspect_ratio"] == "9:16"
    _run(app, db)  # nothing runs before the owner's OK
    db.refresh(job)
    assert job.status == "needs_owner_approval"
    assert credits_left(db, ed) == left  # never gated by, nor counted in, the Quick clip week

    assert owner.post(f"/jobs/{job.id}/approve").status_code == 200
    _run(app, db)
    fs = editor.get(f"/freestyles/{fs['id']}").json()
    assert fs["status"] == "delivered" and fs["file_id"]
    assert _moves(fs)[-1] == ("move", "done", "Made the clip.")

    r = editor.post(f"/freestyles/{fs['id']}/messages", json={"text": "Make it night."})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "waiting"
    assert editor.post(f"/freestyles/{fs['id']}/messages", json={"text": "x"}).status_code == 409
    change = db.query(Job).order_by(Job.id.desc()).first()
    assert change.input["input"]["prompt"].endswith(f"{SCRIPT}\nChange: Make it night.")
    r = owner.post(f"/jobs/{change.id}/decline", json={"reason": "Too dark for the brand."})
    assert r.status_code == 200
    fs = editor.get(f"/freestyles/{fs['id']}").json()
    assert fs["status"] == "declined" and fs["file_id"]  # the first take is still there
    assert _moves(fs)[-1] == ("move", "refused", "The owner declined: Too dark for the brand.")


def test_the_owners_run_at_once_and_only_the_maker_and_owner_see_one(
    app, owner, editor, outsider, db
):
    mine = owner.post("/freestyles", json={**HOUSE, "text": SCRIPT}).json()
    assert mine["status"] == "working" and mine["brand_id"] is None
    assert db.query(Job).one().status == "queued"
    assert editor.get(f"/freestyles/{mine['id']}").status_code == 404
    assert outsider.get(f"/freestyles/{mine['id']}").status_code == 404
    stopped = owner.post(f"/freestyles/{mine['id']}/stop").json()
    assert stopped["status"] == "stopped" and stopped["credits"] == 0
    assert _moves(stopped)[-1] == ("move", "refused", "Stopped.")

    theirs = editor.post("/freestyles", json={**HOUSE, "text": "A cat trades at dawn."}).json()
    r = editor.post(f"/freestyles/{theirs['id']}/withdraw")
    assert r.json()["status"] == "withdrawn" and r.json()["credits"] == 0
    assert editor.post(f"/freestyles/{theirs['id']}/withdraw").status_code == 409
    assert owner.get(f"/freestyles/{theirs['id']}").json()["created_by_name"] == "Ed"
    assert owner.post(f"/freestyles/{theirs['id']}/messages", json={"text": "x"}).status_code == 403
    r = editor.patch(f"/freestyles/{theirs['id']}", json={"title": "Dawn cat"})
    assert r.json()["title"] == "Dawn cat"

    assert [f["id"] for f in editor.get("/freestyles").json()] == [theirs["id"]]
    assert editor.get("/freestyles?everyone=true").status_code == 403
    every = owner.get("/freestyles?everyone=true").json()
    assert [(f["id"], f["status"]) for f in every] == [(theirs["id"], "withdrawn"),
                                                       (mine["id"], "stopped")]  # fmt: skip
    assert outsider.get("/freestyles?everyone=true").json() == []


def test_the_estimate_is_free_and_the_director_types_are_coming_next(owner, editor, db):
    r = editor.get("/freestyles/estimate", params={**HOUSE, "text": SCRIPT})
    assert r.status_code == 200 and r.json()["credits"] > 0
    assert db.query(Job).count() == 0
    for kind in ("song", "narrated"):
        r = editor.post("/freestyles", json={**HOUSE, "type": kind, "text": SCRIPT})
        assert r.status_code == 422 and "One clip and Dialogue work now" in r.text
    r = editor.post("/freestyles", json={**HOUSE, "look": "nope", "text": SCRIPT})
    assert r.status_code == 422
    assert db.query(Job).count() == 0


def test_a_freestyle_is_one_video_under_the_cap_and_a_failed_take_costs_nothing(app, owner, db):
    one = owner.get("/freestyles/estimate", params={**HOUSE, "text": SCRIPT}).json()["credits"]
    limits = owner.get("/credits/limits").json()
    cap = int(one * 2) + 1  # room for two takes, not three
    owner.put("/credits/limits", json={**limits, "per_video_max_credits": cap})
    fs = owner.post("/freestyles", json={**HOUSE, "text": SCRIPT}).json()
    _run(app, db)
    url = f"/freestyles/{fs['id']}/messages"
    assert owner.post(url, json={"text": "Brighter."}).status_code == 201
    _run(app, db)
    r = owner.post(url, json={"text": "Warmer."})
    assert r.status_code == 409, r.text  # the third take would pass the cap, owner or not
    assert db.query(Job).count() == 2

    other = owner.post("/freestyles", json={**HOUSE, "text": "A cat trades at dawn."}).json()
    job = db.query(Job).order_by(Job.id.desc()).first()
    job.status, job.error = "failed", "The model refused it."
    db.commit()
    out = owner.get(f"/freestyles/{other['id']}").json()
    assert (out["status"], out["credits"]) == ("failed", 0)


def test_a_double_tap_makes_one_freestyle_and_cancel_says_withdrawn(owner, editor, db):
    body = {**HOUSE, "text": SCRIPT}
    first, again = (editor.post("/freestyles", json=body).json() for _ in range(2))
    assert first["id"] == again["id"] and db.query(Job).count() == 1  # one held take
    (job,) = db.query(Job).all()
    assert editor.post(f"/jobs/{job.id}/cancel").status_code == 200
    out = editor.get(f"/freestyles/{first['id']}").json()
    assert out["status"] == "withdrawn" and _moves(out)[-1][2] == "Withdrawn."


def test_changes_stop_where_one_clip_prompt_would_overflow(owner, db):
    fs = owner.post("/freestyles", json={**HOUSE, "text": "A cat trades at dawn."}).json()
    change = "Make the light warmer and the cat slower. " * 45  # about 1,900 letters
    codes = []
    for _ in range(4):
        db.query(Job).update({Job.status: "succeeded"})  # each take done before the next
        db.commit()
        codes.append(
            owner.post(f"/freestyles/{fs['id']}/messages", json={"text": change[:2000]}).status_code
        )
    assert codes[:3] == [201, 201, 201] and codes[3] == 409
    r = owner.post(f"/freestyles/{fs['id']}/messages", json={"text": change[:2000]})
    assert "Start a new freestyle" in r.json()["detail"]


def test_media_names_a_freestyle_takes_freestyle(owner, db):
    from tests.conftest import upload

    brand = first_brand(owner)
    fs = owner.post("/freestyles", json={**HOUSE, "brand_id": brand, "text": SCRIPT}).json()
    job = db.query(Job).one()
    job.status, job.output = "succeeded", {"file_ids": [upload(owner)]}
    db.commit()
    (row,) = [
        r
        for r in owner.get(f"/brands/{brand}/media").json()["items"]
        if r["key"].startswith("quick:")
    ]
    assert row["freestyle_id"] == fs["id"]


def test_needs_you_says_which_freestyle_and_what_it_asks(owner, editor, db):
    """QA-9 on #1161: held freestyle sends read as their freestyle, never as the look's lines."""
    fs = editor.post("/freestyles", json={**HOUSE, "text": SCRIPT}).json()
    job = db.query(Job).one()
    owner.post(f"/jobs/{job.id}/approve")
    db.query(Job).update({Job.status: "succeeded"})
    db.commit()
    editor.post(f"/freestyles/{fs['id']}/messages", json={"text": "Make it night."})
    held = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    (row,) = held
    assert row["freestyle"] == {"id": fs["id"], "title": fs["title"], "type": "one_clip",
                                "said": "Make it night.", "change": True,
                                "up_to": None, "total": None, "spent": 4.0}  # fmt: skip
    assert row["prompt_summary"] == "Make it night."
    first = owner.get(f"/jobs/{job.id}").json()["freestyle"]
    assert (first["said"], first["change"]) == (SCRIPT, False)


def test_freestyle_takes_stay_out_of_the_quick_clip_history(owner, editor, db):
    """QA-10 on #1165: Freestyle takes show on Freestyle and Media only. Needs you still lists
    a held one; `freestyle=true` asks for them anyway."""
    fs = editor.post("/freestyles", json={**HOUSE, "text": SCRIPT}).json()
    job = db.query(Job).one()
    for who in (editor, owner):
        assert (
            who.get("/jobs").json() == [] and who.get("/jobs", params={"mine": True}).json() == []
        )
    held = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    assert [j["id"] for j in held] == [job.id]
    owner.post(f"/jobs/{job.id}/approve")
    assert owner.get("/jobs").json() == []  # running or done: still not a Quick clip
    assert [
        j["freestyle"]["id"] for j in editor.get("/jobs", params={"freestyle": True}).json()
    ] == [fs["id"]]
