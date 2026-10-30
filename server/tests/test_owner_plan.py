"""The owner's scene plan on a script version (flows S6, 1b), on the free stand-in writer."""

from app.models.jobs import Job
from tests.conftest import run_writer
from tests.test_script_library import SCRIPT, _make


def test_the_owners_plan_is_each_new_videos_start(app, owner, editor, db):
    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    url = f"{base}/drafts/0/plan"
    assert owner.get(url).status_code == 404  # no plan yet
    job = owner.post(url, json={}).json()
    assert db.get(Job, job["id"]).project_id is None  # the version's, from the author's week
    assert owner.get(url).json()["job"]["status"] == "queued"
    run_writer(app, db)
    plan = owner.get(url).json()
    assert plan["status"] == "ready" and plan["scenes"] and plan["earlier"] == []
    assert owner.post(f"{url}/approve").json()["status"] == "approved"

    preview = owner.post(f"{base}/drafts/0/breakdown").json()  # the preview films the plan
    queued = db.get(Job, preview["id"])
    assert "<plan>" in queued.input["prompt"] and queued.input["plan_version"] == plan["version"]
    db.delete(queued)
    db.commit()

    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    final = owner.put(url, json={"scenes": []})
    assert final.status_code == 409 and "published" in final.json()["detail"]  # rule 31
    assert editor.get(url).json()["status"] == "approved"  # read only, for everyone

    made = editor.post(f"{base}/drafts/0/produce").json()
    pid = made["project_id"]
    video = editor.get(f"/projects/{pid}/plan").json()
    assert (video["status"], video["source"]) == ("approved", "owner")  # "From Reed's plan"
    assert editor.get(f"/projects/{pid}").json()["plan_status"] == "approved"
    shots = db.get(Job, made["breakdown_job_id"])
    assert "<plan>" in shots.input["prompt"]  # its shots are made from the owner's plan


def test_a_preview_made_before_the_plan_never_starts_the_video(app, owner, editor, db):
    """Flow-QA on #934: preview → plan → approve → publish. The old preview is "Made for an
    older plan", and Make this version makes the shots again from the plan (paid), never the
    old ones; a preview made from the plan lands free and knows its plan."""
    from tests.test_breakdown import BREAKDOWN
    from tests.test_enhance import FakeClaude, _run

    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    url = f"{base}/drafts/0/plan"
    owner.put(f"{base}/drafts/0/breakdown", json=BREAKDOWN)  # the preview, before any plan
    owner.post(url, json={})
    run_writer(app, db)
    owner.post(f"{url}/approve")
    version = next(v for v in owner.get(base).json()["versions"] if v["slot"] == 0)
    assert version["preview_older_plan"] is True  # "Make the preview again"
    assert version["has_breakdown"] is False  # so Make this version shows its price
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    made = editor.post(f"{base}/drafts/0/produce").json()
    shots = db.get(Job, made["breakdown_job_id"])  # paid, from Reed's plan
    assert "<plan>" in shots.input["prompt"] and shots.input["plan_version"] == 1

    again = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    plan = f"{again}/drafts/0/plan"
    owner.post(plan, json={})
    run_writer(app, db)
    owner.post(f"{plan}/approve")
    owner.post(f"{again}/drafts/0/breakdown")  # the preview films the approved plan
    _run(app, db, FakeClaude(BREAKDOWN))
    version = next(v for v in owner.get(again).json()["versions"] if v["slot"] == 0)
    assert version["has_breakdown"] and version["preview_older_plan"] is False
    owner.post(f"{again}/drafts/0/approve")
    owner.post(f"{again}/publish")
    made = editor.post(f"{again}/drafts/0/produce").json()
    assert made["breakdown_job_id"] is None  # free: the preview follows the plan
    landed = editor.get(f"/projects/{made['project_id']}/breakdown").json()
    assert landed["older_plan"] is False
    from app.models.breakdowns import BreakdownVersion

    row = db.query(BreakdownVersion).filter_by(project_id=made["project_id"]).one()
    assert row.data["plan_version"] == 1  # an edit to the video's plan makes it older


def test_a_versions_plan_reads_while_made_and_once_landed(app, owner, db, monkeypatch):
    """#945 with S6: the read-after-the-job re-reads only a video's row; a version's plan (a
    stand-in, no row) reads fine while its job runs, and when the job lands mid-read."""
    from app import plans

    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    url = f"{base}/drafts/0/plan"
    owner.post(url, json={})
    running = owner.get(url)
    assert running.status_code == 200 and running.json()["job"]["status"] == "queued"
    real = plans.job_state

    def lands_now(db_, project):
        run_writer(app, db)  # the worker, in its own session, mid-request
        return real(db_, project)

    monkeypatch.setattr(plans, "job_state", lands_now)
    landed = owner.get(url)
    assert landed.status_code == 200, landed.text
    monkeypatch.undo()
    assert owner.get(url).json()["status"] == "ready" and owner.get(url).json()["scenes"]


WALK = """[Intro]
Wake up hungry, bowl is bright
[Verse 1]
Iron Paws, it feels so right
Gut so happy, tail so high
[Chorus] [Lip-sync]
Iron Paws, my best ally
Link in my bio"""


def test_a_songs_section_tags_are_never_plan_lines_and_name_the_lines_under_them(app, owner, db):
    """Next-Layout's walk, row 7: 5 sung lines and 3 tags make 5 plan lines, each with its
    section, by hand or from Claude (a tag it plans anyway is dropped, not a fix)."""
    from app import plans

    app.state.settings.fake_providers = True
    brand = owner.get("/brands").json()[0]["id"]
    made = owner.post("/scripts", json={"brand_id": brand, "title": "Paws", "kind": "song",
                                        "text": WALK}).json()  # fmt: skip
    url = f"/scripts/{made['id']}/drafts/0/plan"
    plan = owner.post(f"{url}/by-hand").json()
    lines = [(x["n"], x["section"]) for s in plan["scenes"] for x in s["lines"]]
    assert lines == [(2, "Intro"), (4, "Verse 1"), (5, "Verse 1"), (7, "Chorus"), (8, "Chorus")]
    assert [s["part"] for s in plan["scenes"]] == ["Intro", "Verse 1", "Chorus"]

    every = [{"line": n, "action": "We see it.", "product": None} for n in range(1, 9)]
    claude = {"structure": {"name": "Song", "parts": [], "based_on": "pattern"}, "cast": [],
              "scenes": [{"id": 1, "part": "", "place": "INT. KITCHEN — DAY", "cast": [],
                          "lines": every}]}  # fmt: skip
    given = {"script": WALK, "fmt": "song", "cast_ids": [], "stars": [], "max_seconds": 15}
    kept, fixes = plans.checked(given, claude)
    assert [x["line"] for x in kept["scenes"][0]["lines"]] == [2, 4, 5, 7, 8] and fixes == []
    assert plans.checked({**given, "fmt": "dialogue"}, claude)[1] == []  # a story keeps them
