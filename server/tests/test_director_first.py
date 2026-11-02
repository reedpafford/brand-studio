"""P1 (Reed's first walk, the Producer): "Make a video" is a freestyle, the director-first
video. From pasted words with a brand, or from any version of a script, it makes a visible
script and video; the version is frozen (rule 31), its saved shots reused free (item 8),
and the director runs at once (an editor's waits for the owner)."""

from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.routes.estimate import run_price
from tests.conftest import first_brand
from tests.test_breakdown import BREAKDOWN
from tests.test_flavours import _brand_flavours
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


def test_an_editors_video_is_real_only_from_the_owners_ok_and_a_no_leaves_nothing(
    owner, editor, db
):
    """Next-Lead: an editor's held send freezes nothing and shows nothing; the owner's OK makes
    the script and video real; a decline (or a withdraw) leaves the version as it was."""
    r = editor.post("/freestyles", json={**BODY, "brand_id": first_brand(owner)})
    assert r.status_code == 201, r.text
    fs = r.json()
    assert fs["status"] == "waiting" and fs["project_id"] and fs["script_id"]
    assert fs["script_id"] not in [s["id"] for s in owner.get("/scripts").json()]  # not yet
    assert fs["project_id"] not in [p["id"] for p in owner.get("/projects").json()]
    (held,) = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    asked = held["freestyle"]  # v5: Needs you lists it as a request, before the video shows
    assert (asked["script_id"], asked["slot"], held["created_by_name"]) == (
        fs["script_id"],
        0,
        "Ed",
    )
    assert (asked["hidden"], asked["script_title"], asked["brand_id"]) == (
        True, "", first_brand(owner))  # fmt: skip  # pasted: the web never reads its script
    assert owner.post(f"/jobs/{held['id']}/approve").status_code == 200
    assert fs["script_id"] in [s["id"] for s in owner.get("/scripts").json()]  # in Scripts
    assert fs["project_id"] in [p["id"] for p in owner.get("/projects").json()]  # in Videos
    both = editor.post("/freestyles", json={**BODY, "script_id": fs["script_id"]})
    assert both.status_code == 422 and "not both" in both.text

    _brand_flavours(db, owner)
    made = _make(editor, text=f"{SCRIPT}\nLEO: Again.")  # the editor's own draft
    pick = {"shape": "9:16", "script_id": made["id"]}
    sent = editor.post("/freestyles", json=pick)
    assert sent.status_code == 201, sent.text
    mine = sent.json()
    assert mine["status"] == "waiting", mine["thread"]
    db.expire_all()
    script, draft = (
        db.get(Script, made["id"]),
        (db.query(ScriptDraft).filter_by(script_id=made["id"], slot=0).one()),
    )
    assert not script.published and draft.status == "draft"  # nothing frozen while it waits
    words = f"/scripts/{made['id']}/drafts/0"
    for edit in (editor.put(words, json={"text": f"{SCRIPT}\nLEO: Changed."}),  # QA-10: every
                 editor.put(f"{words}/breakdown", json=BREAKDOWN),  # write on what it's made of
                 editor.put(f"{words}/flavours", json={"bag": "Peanut butter"}),
                 editor.post(f"/scripts/{made['id']}/cast", json={"role": "Leo"})):  # fmt: skip
        assert edit.status_code == 409 and "waiting for the owner's OK" in edit.text, edit.text
    held = next(j for j in owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
                if j["freestyle"]["id"] == mine["id"])  # fmt: skip
    assert (held["freestyle"]["script_id"], held["freestyle"]["slot"]) == (made["id"], 0)
    assert (held["freestyle"]["hidden"], held["freestyle"]["script_title"]) == (
        False, script.title)  # fmt: skip  # from a script: its own title
    owner.post(f"/jobs/{held['id']}/decline", json={"reason": "Not this one."})
    db.expire_all()
    assert not db.get(Script, made["id"]).published
    assert db.get(ScriptDraft, draft.id).status == "draft"
    assert mine["project_id"] not in [p["id"] for p in owner.get("/projects").json()]
    assert editor.put(words, json={"text": f"{SCRIPT}\nLEO: Again."}).status_code == 200
    assert editor.put(f"{words}/breakdown", json=BREAKDOWN).status_code == 200  # free again
    again = owner.post("/freestyles", json=pick)  # the version is free to make again
    assert again.status_code == 201, again.text
    twice = editor.post("/freestyles", json=pick)  # (the owner's own twice is a double tap)
    assert twice.status_code == 409  # one version, one video, and which one
    db.expire_all()  # the breakdown saved since
    up_to = float(run_price(db, db.get(ScriptDraft, draft.id)))
    assert twice.json()["detail"] == {"text": "This version already has a video.", "up_to": up_to,
                                      "project_id": again.json()["project_id"]}  # fmt: skip
    another = editor.post("/freestyles", json={**pick, "make_another": True})  # the Producer
    assert another.status_code == 201, another.text
    second = another.json()
    assert second["status"] == "waiting" and second["up_to"] == up_to  # an editor's waits
    assert second["project_id"] != again.json()["project_id"]  # a new video, same version
    video = db.get(Project, second["project_id"], execution_options={"see_hidden": True})
    assert video.hidden and video.script_draft_id == draft.id  # hidden until the OK
