"""New video's front door (Reed, 10 Nov): the products picked for a video, an idea written into
a script first, and "Make without asking" (the owner's start card pressed for them). Stand-ins
only."""

from decimal import Decimal

from app import asks, picks
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from app.providers import get_providers
from app.worker import run_once
from tests.conftest import first_brand, run_writer
from tests.helpers import ok_when_asked
from tests.test_freestyle_dialogue import SCRIPT, _run

IDEA = "A barista proves her regulars wrong about decaf."


def _send(client, **more) -> dict:
    return {"shape": "9:16", "text": SCRIPT, "brand_id": first_brand(client), **more}


def _video(db, fs: dict) -> Project:
    db.expire_all()
    return db.get(Project, db.get(Freestyle, fs["id"]).project_id)


def _steps(db, step: str) -> list[Job]:
    return db.query(Job).filter(Job.input["step"].as_string() == step).order_by(Job.id).all()


def _bag(owner) -> int:
    return owner.post("/library/prop", json={
        "name": "Chicken bag", "brand_ids": [first_brand(owner)], "product_type": "physical",
        "main_claim": "Real chicken first"}).json()["id"]  # fmt: skip


def test_the_products_picked_reach_the_video_and_its_treatment(app, owner, db):
    bag = _bag(owner)
    mia = owner.post("/library/character", json={"name": "Mia"}).json()["id"]
    no = owner.post("/freestyles", json=_send(owner, look="house", product_ids=[mia]))
    assert (no.status_code, no.json()["detail"]) == (422, "Pick products from this brand.")
    fs = owner.post("/freestyles", json=_send(owner, look="house", product_ids=[bag, bag]))
    assert fs.status_code == 201 and _video(db, fs.json()).product_ids == [bag]
    run_writer(app, db)
    run_writer(app, db)
    (treatment,) = _steps(db, "treatment")
    assert f"prop:{bag} | Chicken bag | claim: Real chicken first" in treatment.input["prompt"]
    plain = owner.post("/freestyles", json=_send(owner, look="house", text="MIA: No bag.")).json()
    assert picks.context(db, _video(db, plain)) == ""  # none picked: nothing added


def _to_the_card(app, db, fs: dict) -> Job:
    """Run until the send's start card exists: its run's first generating turn."""
    app.state.settings.fake_providers = True
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(40):
        run_once(db, providers, app.state.storage)
        db.expire_all()
        ok_when_asked(db)  # the person approves the cast and places when asked
        mine = Job.project_id == db.get(Freestyle, fs["id"]).project_id
        if card := db.query(Job).filter(mine, Job.input[asks.START].as_boolean()).first():
            return card
    raise AssertionError("no start card")


def test_make_without_asking_presses_the_owners_start_card_for_them(app, owner, db):
    asked = owner.post("/freestyles", json=_send(owner, look="house")).json()
    card = _to_the_card(app, db, asked)
    assert card.status == "needs_owner_approval"  # as today: it waits for Make it
    assert owner.get(f"/freestyles/{asked['id']}").json()["make_it"]
    owner.post(f"/freestyles/{asked['id']}/stop")
    auto = owner.post("/freestyles", json=_send(owner, look="house", mode="auto",
                                                text="MIA: Watch this.")).json()  # fmt: skip
    card = _to_the_card(app, db, auto)
    assert card.status != "needs_owner_approval" and card.approved_by_id  # pressed for them
    assert Decimal(card.input["price"]) == db.get(Freestyle, auto["id"]).up_to  # as shown
    out = owner.get(f"/freestyles/{auto['id']}").json()
    assert out["make_it"] is None and out["status"] == "working"
    _run(app, db, ticks=6, start=False)
    assert _steps(db, "storyboard")  # it goes on to the pictures, with no press


def test_an_editors_make_without_asking_still_waits_for_the_owner(app, owner, editor, db):
    fs = editor.post("/freestyles", json=_send(editor, look="house", mode="auto")).json()
    card = _to_the_card(app, db, fs)
    _run(app, db, ticks=3, start=False)
    db.refresh(card)
    assert card.status == "needs_owner_approval" and asks.AUTO not in card.input
    assert editor.get(f"/freestyles/{fs['id']}").json()["status"] == "waiting"


def test_an_idea_is_written_into_a_script_first_then_its_video_starts(app, owner, db):
    mine = _send(owner, text=IDEA, idea=True, look="house", product_ids=[_bag(owner)])
    est = owner.post("/freestyles/estimate", json=mine).json()
    assert est["expected"] and est["credits"] > 0  # "about": no script to measure yet
    fs = owner.post("/freestyles", json=mine)
    assert fs.status_code == 201, fs.text
    out = fs.json()
    assert out["status"] == "working" and out["project_id"] is None  # no video yet
    assert [t["text"] for t in out["thread"]] == [IDEA, "Writing the script from your idea."]
    (write,) = _steps(db, "script_draft")
    assert f"Goal: {IDEA}" in write.input["prompt"]
    assert "<products>" in write.input["prompt"]  # the picks reach the writer too
    assert db.query(Project).count() == 0  # the video it was checked on was never kept
    run_writer(app, db)  # the script is written; its video starts as a pasted script's does
    out = owner.get(f"/freestyles/{out['id']}").json()
    video = _video(db, out)
    assert out["project_id"] == video.id and video.product_ids and out["up_to"] > 0
    wrote = out["thread"][1]
    assert out["thread"][0]["text"] == IDEA and wrote["who"] == "Director"
    assert wrote["text"].startswith("Here's the script I wrote from your idea:\n\n")
    assert "HERO: This is a practice script." in wrote["text"]
    run_writer(app, db)
    run_writer(app, db)
    (treatment,) = _steps(db, "treatment")
    assert "HERO: This is a practice script." in treatment.input["prompt"]  # the written words


def test_an_idea_that_cant_be_written_says_so_and_sending_again_tries_again(app, owner, db):
    fs = owner.post("/freestyles", json=_send(owner, text=IDEA, idea=True, look="house")).json()
    busy = owner.post(f"/freestyles/{fs['id']}/messages", json={"text": "Again."})
    assert busy.status_code == 409  # still being written
    (write,) = _steps(db, "script_draft")
    write.status, write.error = "failed", "The writer was busy."
    db.commit()
    out = owner.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "failed" and out["thread"][-1]["text"] == (
        "I couldn't write the script from your idea: The writer was busy. Send the idea again "
        "to try again.")  # fmt: skip
    again = owner.post(f"/freestyles/{fs['id']}/messages", json={"text": "A barista, take two."})
    assert again.status_code == 201 and again.json()["status"] == "working"
    run_writer(app, db)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    assert out["project_id"] and out["thread"][0]["text"] == "A barista, take two."
