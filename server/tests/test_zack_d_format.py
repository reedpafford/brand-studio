"""The Zack D format, with its own Zack D style, on the stand-ins (Reed, 7 Nov: every style
tested and finished this round): offered on the picker, a script can take it (narrated),
and a pasted script is made end to end, brief to cut."""

from app import guides
from app.models.clips import FinalVideo
from app.models.freestyles import Freestyle
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import _run

SCRIPT = (
    "Your stomach replaces its whole lining every few days.\n"
    "Acid eats it from the inside, so new cells push up from below.\n"
    "Skip a meal and the acid has nothing to work on but you.\n"
    "That growl is the lining asking for lunch."
)


def test_the_zack_d_format_is_offered_and_a_script_takes_it(owner):
    (f,) = [f for f in guides.formats() if f["id"] == "zack-d"]
    assert (f["on"], f["engine"]) == (True, "narrated")
    shown = {x["id"]: x for x in owner.get("/formats").json()}
    assert shown["zack-d"]["on"] and shown["zack-d"]["off"] is None  # on the picker
    made = owner.post(
        "/scripts",
        json={
            "brand_id": first_brand(owner),
            "title": "Gut",
            "format": "zack-d",
            "look": "zack-d",
            "text": SCRIPT,
        },
    )
    assert made.status_code == 201, made.text  # never "That format isn't available."
    assert made.json()["kind"] == "narrated"


def test_a_pasted_zack_d_video_goes_from_brief_to_cut(app, db, owner, monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)  # the narration's
    body = {"type": "zack-d", "look": "zack-d", "shape": "9:16", "text": SCRIPT,
            "brand_id": first_brand(owner)}  # fmt: skip
    sent = owner.post("/freestyles", json=body)
    assert sent.status_code == 201, sent.text
    _run(app, db, ticks=160)
    fs = owner.get(f"/freestyles/{sent.json()['id']}").json()
    assert fs["status"] == "delivered", [m["text"][:120] for m in fs["thread"]][-6:]
    pid = db.get(Freestyle, sent.json()["id"]).project_id
    steps = owner.get(f"/projects/{pid}/director").json()["turns"]
    tools = {t["tool"] for t in steps}
    assert {"narration", "plan", "storyboard", "make_take", "final_cut"} <= tools, tools
    assert db.query(FinalVideo).filter_by(project_id=pid).count() >= 1  # the cut
    video = owner.get(f"/projects/{pid}").json()
    assert video["look"] == "zack-d"
