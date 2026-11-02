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
    assert _moves(fs) == [("message", None, SCRIPT), ("move", "held", "Waiting for Reed's OK.")]
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
    assert _moves(fs)[-1] == ("move", "refused", "Reed declined: Too dark for the brand.")


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
    for kind in ("dialogue", "song", "narrated"):
        r = editor.post("/freestyles", json={**HOUSE, "type": kind, "text": SCRIPT})
        assert r.status_code == 422 and "One clip works now" in r.text
    r = editor.post("/freestyles", json={**HOUSE, "look": "nope", "text": SCRIPT})
    assert r.status_code == 422
    assert db.query(Job).count() == 0
