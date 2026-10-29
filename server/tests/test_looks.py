"""Format and Look (flows ST1, ST3, VS1): the look cards, who may pick an Off look, the owner's
switch (on only with a sample), and a video's look reaching its prompts."""

from app import looks, prompts
from app.enhance import project_context
from app.models.looks import LookSwitch
from app.models.projects import Project
from app.models.script_library import Script
from tests.test_script_produce import _published


def _cards(client):
    return {c["id"]: c for c in client.get("/looks").json()}


def test_the_cards_are_looks_only_house_first_and_on(editor):
    cards = editor.get("/looks").json()
    assert cards[0]["id"] == "house" and cards[0]["on"]
    assert [c["id"] for c in cards[1:4]] == ["disney-pixar", "zack-d", "skeleton"]  # Reed's order
    assert not any(c["on"] for c in cards[1:])
    assert {"song", "vox", "podcast"}.isdisjoint(c["id"] for c in cards)  # formats aren't looks


def test_an_editor_picks_only_a_look_thats_on_and_the_owner_may_try_any(owner, editor):
    brand = owner.get("/brands").json()[0]["id"]
    tried = editor.post("/scripts", json={"brand_id": brand, "title": "T", "look": "zack-d"})
    assert tried.status_code == 409 and tried.json()["detail"] == looks.OFF.format("Zack D")
    mine = owner.post("/scripts", json={"brand_id": brand, "title": "T", "look": "zack-d"})
    assert mine.status_code == 201 and mine.json()["look"] == "zack-d"
    url = f"/scripts/{mine.json()['id']}"
    assert owner.patch(url, json={"look": "disney-pixar"}).json()["look"] == "disney-pixar"
    assert owner.patch(url, json={"look": "house"}).json()["look"] == "house"  # Undo: free
    assert owner.patch(url, json={"look": "song"}).status_code == 422  # a format, not a look
    plain = editor.post("/scripts", json={"brand_id": brand, "title": "T"}).json()
    assert plain["look"] == "house"


def test_a_look_is_switched_on_only_with_a_sample(db, owner, editor):
    no = owner.patch("/looks/claymation", json={"on": True})
    assert (no.status_code, no.json()["detail"]) == (409, looks.NO_SAMPLE)
    assert owner.patch("/looks/house", json={"on": False}).status_code == 409
    assert editor.patch("/looks/claymation", json={"on": True}).status_code == 403
    ws = owner.get("/auth/me").json()["workspace_id"]
    db.add(LookSwitch(workspace_id=ws, look_id="claymation", sample_still_id=None))
    db.commit()
    db.query(LookSwitch).one().sample_still_id = _a_file(db)  # a sample made (ST3)
    db.commit()
    on = owner.patch("/looks/claymation", json={"on": True})
    assert on.status_code == 200 and on.json()["on"] and _cards(editor)["claymation"]["on"]
    brand = owner.get("/brands").json()[0]["id"]
    picked = editor.post("/scripts", json={"brand_id": brand, "title": "T", "look": "claymation"})
    assert picked.status_code == 201
    assert not owner.patch("/looks/claymation", json={"on": False}).json()["on"]  # Undo
    assert editor.get(f"/scripts/{picked.json()['id']}").json()["look"] == "claymation"  # kept


def _a_file(db):
    from app.models.files import StoredFile

    row = StoredFile(workspace_id=1, key="sample", filename="s.png", content_type="image/png",
                     size=1, sha256="0" * 64)  # fmt: skip
    db.add(row)
    db.commit()
    return row.id


def test_a_video_takes_its_scripts_look_and_its_prompts_use_its_own(owner, editor, db):
    base, _ = _published(owner, db)
    assert owner.patch(base, json={"look": "zack-d"}).status_code in (403, 409)  # published
    script = db.get(Script, int(base.rsplit("/", 1)[1]))
    script.look = "disney-pixar"  # as if picked before publishing
    db.commit()
    made = editor.post(f"{base}/drafts/0/produce").json()
    video = f"/projects/{made['project_id']}"
    assert editor.get(video).json()["look"] == "disney-pixar"
    project = db.get(Project, made["project_id"])
    system, _ = project_context(db, project, "storyboard")
    assert system[0] == prompts.system("storyboard", "disney-pixar") != prompts.system("storyboard")
    assert editor.patch(video, json={"look": "zack-d"}).status_code == 409  # off for editors
    assert owner.patch(video, json={"look": "house"}).json()["look"] == "house"
