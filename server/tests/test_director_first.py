"""P1 (Reed's first walk, the Producer): "Make a video" is a freestyle, the director-first
video. From pasted words with a brand, or from any version of a script, it makes a visible
script and video; the version is frozen (rule 31), its saved shots reused free (item 8),
and the director runs at once (an editor's waits for the owner)."""

from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.script_library import Script, ScriptDraft
from app.routes.estimate import run_price
from tests.conftest import first_brand
from tests.test_breakdown import BREAKDOWN
from tests.test_freestyle_dialogue import BODY, SCRIPT, _run
from tests.test_script_library import _make


def test_make_a_video_from_a_scripts_version_freezes_it_and_reuses_its_shots(
    app, owner, editor, db
):
    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    assert owner.put(f"{base}/drafts/0/breakdown", json=BREAKDOWN).status_code == 200
    draft = db.query(ScriptDraft).filter_by(script_id=made["id"], slot=0).one()
    est = owner.get("/freestyles/estimate", params={"shape": "9:16", "script_id": made["id"]})
    assert est.json()["credits"] == float(run_price(db, draft))
    r = owner.post("/freestyles", json={"shape": "9:16", "script_id": made["id"], "slot": 0})
    assert r.status_code == 201, r.text
    fs = r.json()
    assert fs["type"] == "dialogue" and fs["status"] == "working"  # the owner's runs at once
    db.expire_all()
    script = db.get(Script, made["id"])
    assert script.published and not script.hidden  # published with it, in Scripts
    assert db.get(ScriptDraft, draft.id).status == "approved"  # frozen (rule 31)
    assert fs["script_id"] == made["id"] and fs["project_id"]
    video = owner.get(f"/projects/{fs['project_id']}").json()
    assert video["freestyle_id"] == fs["id"]
    assert fs["project_id"] in [p["id"] for p in owner.get("/projects").json()]  # in Videos
    (bd,) = db.query(BreakdownVersion).filter_by(project_id=fs["project_id"]).all()
    assert bd.source == "library"  # the saved shots, landed free (item 8)
    steps = {j.input.get("step") for j in db.query(Job).filter_by(project_id=fs["project_id"])}
    assert steps == {"director"}  # no plan or breakdown call: only the director's first turn
    _run(app, db)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]]
    steps = {j.input.get("step") for j in db.query(Job).filter_by(project_id=fs["project_id"])}
    assert not steps & {"plan", "breakdown"}  # the shots were never made again
    shown = owner.get(f"/projects/{fs['project_id']}/breakdown").json()
    assert shown["director_run"] is True and shown["needs_you"] is None  # item 9
    assert owner.put(f"{base}/drafts/0", json={"text": SCRIPT + "\nMIA: More."}).status_code == 409


def test_pasted_words_with_a_brand_make_a_visible_script_and_video_an_editors_waits(
    owner, editor, db
):
    r = editor.post("/freestyles", json={**BODY, "brand_id": first_brand(owner)})
    assert r.status_code == 201, r.text
    fs = r.json()
    assert fs["status"] == "waiting" and fs["project_id"] and fs["script_id"]
    assert fs["script_id"] in [s["id"] for s in owner.get("/scripts").json()]  # in Scripts
    assert fs["project_id"] in [p["id"] for p in owner.get("/projects").json()]  # in Videos
    shown = owner.get(f"/projects/{fs['project_id']}/breakdown")
    assert shown.status_code == 404 or shown.json()["needs_you"]["action"] == "approvals"
    again = owner.post("/freestyles", json={**BODY, "text": None, "script_id": fs["script_id"]})
    assert again.status_code == 409  # one version, one video
    both = editor.post("/freestyles", json={**BODY, "script_id": fs["script_id"]})
    assert both.status_code == 422 and "not both" in both.text
