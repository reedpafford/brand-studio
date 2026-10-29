"""Producing a library version: its project, once, with the saved breakdown or a new one."""

import json

from fastapi.testclient import TestClient

from app import credits, plans, prompts
from app.db import utcnow
from app.models.accounts import User
from app.models.clips import FinalVideo
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.routes.jobs import enqueue
from tests.conftest import PASSWORD, upload
from tests.helpers import approved_plan, with_sheet
from tests.test_breakdown import BREAKDOWN
from tests.test_media import _file
from tests.test_script_library import IMPORTED, SCRIPT, _imported, _make


def _published(owner, db, *, breakdown=None, target=None):
    made = _make(owner, text=SCRIPT, reference_id="fomo-DehudnaAmce")
    base = f"/scripts/{made['id']}"
    if target:
        owner.put(f"{base}/drafts/0", json={"text": SCRIPT, "target_seconds": target})
    mia = owner.post("/library/character", json={"name": "Mia", "image_file_ids": [upload(owner)]})
    with_sheet(db, mia.json()["id"])
    slot = owner.post(f"{base}/cast", json={"role": "Mom"}).json()[0]["id"]
    owner.post(f"{base}/cast/{slot}/lock", json={"library_item_id": mia.json()["id"]})
    if breakdown:
        owner.put(f"{base}/drafts/0/breakdown", json=breakdown)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return base, mia.json()["id"]


def test_produce_with_the_saved_breakdown_is_free_and_once(owner, editor, db):
    base, mia = _published(owner, db, breakdown=BREAKDOWN)
    made = editor.post(f"{base}/drafts/0/produce")
    assert made.status_code == 201, made.text
    assert made.json()["breakdown_job_id"] is None and db.query(Job).count() == 0
    project = editor.get(f"/projects/{made.json()['project_id']}").json()
    assert project["cast_ids"] == [mia] and project["planned_seconds"] is None
    assert project["reference_breakdown"]["source_id"] == "fomo-DehudnaAmce"
    assert project["breakdown_seconds"] == 5 and project["budget_credits"] > 10
    pid = project["id"]
    assert editor.get(f"/projects/{pid}/script").json()["text"] == SCRIPT
    bd = editor.get(f"/projects/{pid}/breakdown").json()
    assert bd["source"] == "library" and bd["breakdown"]["clips"] == BREAKDOWN["clips"]
    again = owner.post(f"{base}/drafts/0/produce")
    assert (
        again.status_code == 409 and again.json()["detail"] == "This version already has a video."
    )
    library = owner.get(base).json()
    assert library["versions"][0]["status"] == "in_production" and library["versions_left"] == 0
    assert library["versions"][0]["project_id"] == pid


def test_produce_without_a_saved_breakdown_makes_its_plan(app, owner, editor, db):
    """flows 1b (Reed): every video gets a plan before its shots. The plan call is what Make
    this version charges, at the price it shows; a failed plan opens on Plan, never stuck."""
    base, _ = _published(owner, db, target=40)
    shown = next(r for r in editor.get("/credits/rates").json() if r["kind"] == "write-claude")
    made = editor.post(f"{base}/drafts/0/produce").json()
    assert made["breakdown_job_id"] is None
    job = db.get(Job, made["plan_job_id"])
    assert job.input["step"] == "plan" and job.project_id == made["project_id"]
    assert job.credits == shown["credits_per_unit"]  # the quote is the charge
    url = f"/projects/{made['project_id']}/plan"
    job.status, job.error = JobStatus.failed, ""
    db.commit()
    failed = editor.get(url).json()
    assert (failed["job"]["status"], failed["job"]["reason"]) == ("failed", plans.FAILED)
    assert editor.post(url, json={}).status_code == 201  # Try again
    db.query(Job).update({"status": JobStatus.cancelled})
    db.commit()
    assert editor.post(f"{url}/by-hand").json()["source"] == "hand"  # or plan it yourself
    project = editor.get(f"/projects/{made['project_id']}").json()
    assert project["planned_seconds"] == 40 and project["budget_credits"] > 80  # Reed's target


def test_only_approved_versions_of_published_scripts(owner, editor):
    made = _make(owner, text=SCRIPT)
    url = f"/scripts/{made['id']}/drafts/0/produce"
    assert owner.post(url).json()["detail"] == "Publish this script first."
    owner.put(f"/scripts/{made['id']}/drafts/1", json={"text": SCRIPT + "\nMOM: Fine."})
    assert editor.post(url).status_code == 404  # private until published


def _editors_script(editor) -> str:
    made = _make(editor, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    assert editor.post(f"{base}/drafts/0/approve").status_code == 200
    assert editor.post(f"{base}/publish").status_code == 200
    return base


def _second_editor(app, owner, db):
    token = owner.post("/team/invites", json={"email": "two@example.com"}).json()["token"]
    client = TestClient(app)
    r = client.post(
        "/auth/accept-invite", json={"token": token, "name": "Two", "password": PASSWORD}
    )
    assert r.status_code == 201, r.text
    return client, db.query(User).filter_by(email="two@example.com").one()


def test_only_the_author_uses_their_allowance_for_a_script(app, owner, editor, db):
    """QA #218: another editor's script runs on the video's budget, never the producer's
    allowance (so a spent allowance doesn't decline it, and it isn't billed there)."""
    base = _editors_script(editor)
    two, second = _second_editor(app, owner, db)
    enqueue(db, second, "video-480p", {}, units=145)  # Two's allowance is spent
    made = two.post(f"{base}/drafts/0/produce")
    assert made.status_code == 201, made.text
    project = db.get(Project, made.json()["project_id"])
    assert not credits.own_script(db, project, second)
    ed = db.query(User).filter_by(email="ed@example.com").one()
    assert credits.own_script(db, project, ed)  # the author's, were they producing it


def test_a_video_says_whether_it_runs_on_the_viewers_allowance(owner, editor, db):
    base = _editors_script(editor)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    assert editor.get(f"/projects/{pid}").json()["own_script"] is True
    assert owner.get(f"/projects/{pid}").json()["own_script"] is False  # unlimited, no allowance
    theirs, _ = _published(owner, db, breakdown=BREAKDOWN)
    other = editor.post(f"{theirs}/drafts/0/produce").json()["project_id"]
    assert editor.get(f"/projects/{other}").json()["own_script"] is False


def test_a_declined_breakdown_leaves_the_version_free(editor, db):
    """QA #218: past the allowance the breakdown is declined and nothing is kept: no
    project, no reservation, so the version can be produced later."""
    base = _editors_script(editor)
    ed = db.query(User).filter_by(email="ed@example.com").one()
    enqueue(db, ed, "video-480p", {}, units=145)
    declined = editor.post(f"{base}/drafts/0/produce")
    assert declined.status_code == 409
    assert declined.json()["detail"] == "You've used this week's 145 credits. It resets on Monday."
    db.expire_all()
    assert db.query(Project).count() == 0 and db.query(ScriptDraft).one().reserved_by_id is None
    assert editor.get(base).json()["versions_left"] == 1
    db.query(Job).delete()
    db.commit()
    assert editor.post(f"{base}/drafts/0/produce").status_code == 201


def test_a_produced_version_names_its_editor_and_the_video_its_version(owner, editor, db):
    """For the library's "In production · Ed" chip, and to keep script videos out of
    "Videos made before scripts"."""
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    assert owner.get("/scripts").json()[0]["versions"][0]["editor"] is None
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    ed = editor.get("/auth/me").json()
    row = next(s for s in owner.get("/scripts").json() if f"/scripts/{s['id']}" == base)
    assert row["versions"][0]["editor"] == {"id": ed["id"], "name": "Ed"}
    draft_id = db.get(Project, pid).script_draft_id
    assert draft_id is not None
    assert editor.get(f"/projects/{pid}").json()["script_draft_id"] == draft_id
    fomo = owner.get("/brands").json()[0]["id"]
    older = owner.post("/projects", json={"brand_id": fomo, "name": "Old way"}).json()
    assert older["script_draft_id"] is None


def test_a_version_whose_video_failed_says_so_and_a_done_one_has_a_poster(owner, editor, db):
    from app.db import utcnow
    from app.models.breakdowns import BreakdownVersion
    from app.models.storyboards import StoryboardFrame

    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    ed = db.query(User).filter_by(email="ed@example.com").one()
    job = enqueue(db, ed, "video-480p", {}, project=db.get(Project, pid))
    job.status = "failed"
    db.commit()
    script = owner.get(base).json()
    assert script["versions"][0]["status"] == "failed"  # "Didn't finish"
    still = upload(editor)
    first = db.get(Project, pid)
    breakdown_id = db.query(BreakdownVersion).filter_by(project_id=pid).one().id
    db.add(StoryboardFrame(project_id=pid, breakdown_id=breakdown_id, clip_id="c1",
                           shot_id="s1", prompt="x", file_id=still))  # fmt: skip
    first.finished_at = utcnow()
    db.commit()
    row = next(s for s in owner.get("/scripts").json() if f"/scripts/{s['id']}" == base)
    assert row["versions"][0]["status"] == "done" and row["poster_file_id"] == still


def test_produce_uses_the_scripts_own_imported_reel(owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    _imported(db, int(base.rsplit("/", 1)[1]))  # wins over the catalogue reel
    made = editor.post(f"{base}/drafts/0/produce").json()
    ref = editor.get(f"/projects/{made['project_id']}").json()["reference_breakdown"]
    assert ref == IMPORTED
    block = prompts.reference_block(ref)
    assert "She says no" in block and "Creator talks to camera" not in block  # live action


def test_a_started_version_can_be_released_and_made_again(app, owner, editor, db):
    base, _ = _published(owner, db, target=40)
    made = editor.post(f"{base}/drafts/0/produce").json()  # its plan job is queued
    pid = made["project_id"]
    two, _ = _second_editor(app, owner, db)
    assert two.post(f"/projects/{pid}/release").status_code == 403  # not theirs
    released = editor.post(f"/projects/{pid}/release").json()
    assert released["archived_at"] and released["script_draft_id"] is None
    assert db.get(Job, made["plan_job_id"]).status == "cancelled"  # credits come back
    assert released["credits_used"] == 0
    assert owner.get(base).json()["versions"][0]["status"] == "approved"  # Ready to make
    again = two.post(f"{base}/drafts/0/produce")
    assert again.status_code == 201 and again.json()["project_id"] != pid
    late = editor.post(f"/projects/{pid}/restore")  # Undo, too late: the version is taken
    assert late.json()["detail"] == "Two started version A again, so this video can't come back."
    assert editor.post(f"/projects/{again.json()['project_id']}/release").status_code == 403
    assert owner.post(f"/projects/{again.json()['project_id']}/release").status_code == 200


def test_releasing_never_gives_the_allowance_back(editor, db):
    """QA #328: an editor can't release their own video to spend their week again."""
    base = _editors_script(editor)
    made = editor.post(f"{base}/drafts/0/produce").json()
    pid, me = made["project_id"], db.query(User).filter_by(role="editor").one()
    db.get(Job, made["plan_job_id"]).status = JobStatus.succeeded  # credits really spent
    db.commit()
    spent = credits.quick_clip_used(db, me)
    assert spent > 0
    editor.post(f"/projects/{pid}/release")
    db.expire_all()
    assert credits.quick_clip_used(db, me) == spent
    assert credits.own_script(db, db.get(Project, pid), me)  # still on their allowance


def test_restore_right_after_release_gives_the_version_back(owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    project = db.get(Project, pid)
    final = _file(db, project.workspace_id, "video/mp4")
    db.add(FinalVideo(project_id=pid, file_id=final, take_ids=[],
                      created_by_id=project.created_by_id))  # fmt: skip
    db.commit()
    gone = editor.post(f"/projects/{pid}/release").json()
    assert gone["released"] and owner.get(f"/projects/{pid}").json()["released"]
    tiles = owner.get(f"/brands/{gone['brand_id']}/media", params={"kind": "final"}).json()["items"]
    assert [(i["from_deleted_video"], i["deleted_video_released"]) for i in tiles] == [(True, True)]
    back = editor.post(f"/projects/{pid}/restore").json()
    assert back["script_draft_id"] is not None and back["archived_at"] is None
    assert not back["released"]
    version = owner.get(base).json()["versions"][0]
    assert (version["status"], version["project_id"]) == ("in_production", pid)
    again = editor.post(f"/projects/{pid}/release")  # Undo of Restore: back to Ready to make
    assert again.status_code == 200 and again.json()["released"]
    assert owner.get(base).json()["versions"][0]["status"] != "in_production"


def test_an_archived_video_is_not_released(owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    assert not editor.post(f"/projects/{pid}/archive").json()["released"]


def test_a_done_video_cant_be_released(owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    from app.db import utcnow

    db.get(Project, pid).finished_at = utcnow()
    db.commit()
    assert editor.post(f"/projects/{pid}/release").status_code == 409


def test_a_video_can_be_archived_and_brought_back(app, owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    two, _ = _second_editor(app, owner, db)
    assert two.post(f"/projects/{pid}/archive").status_code == 403
    assert editor.post(f"/projects/{pid}/archive").json()["archived_at"]
    paid = editor.post(f"/projects/{pid}/breakdown")  # nothing new runs on an archived video
    assert paid.status_code == 409 and "archived" in paid.json()["detail"]
    assert [p["id"] for p in editor.get("/projects").json()] == []
    assert [p["id"] for p in editor.get("/projects?archived=true").json()] == [pid]
    assert editor.post(f"/projects/{pid}/restore").json()["archived_at"] is None
    assert [p["id"] for p in owner.get("/projects").json()] == [pid]


def test_deleting_a_produced_script_keeps_its_video(owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    assert owner.delete(base).status_code == 204
    assert editor.get(f"/projects/{pid}").status_code == 200  # the video stays
    (row,) = owner.get("/scripts?removed=1").json()
    assert (row["removed"], row["purge_on"]) == ("archived", None)  # never removed for good
    assert row["removed_at"]
    assert owner.post(f"{base}/restore").json()["versions"][0]["project_id"] == pid


def test_an_unlocked_slot_in_the_breakdown_is_known_and_waits_only_for_its_look(owner, editor, db):
    """Reed: "shot X: unknown slot:28" on every shot blocked the storyboard. The role is
    known; only its missing look stops the storyboard (Reed, 2026-10-27), pointing to Assets."""
    from tests.test_unknown_cast import _look
    from tests.test_video_looks import NATE_ONLY

    made = _make(owner, text=NATE_ONLY)
    base = f"/scripts/{made['id']}"
    nate = owner.post(f"{base}/cast", json={"role": "Nate"}).json()[0]["id"]  # unlocked
    other = _make(owner, title="Other", text=SCRIPT)
    stranger = owner.post(f"/scripts/{other['id']}/cast", json={"role": "X"}).json()[0]["id"]
    bd = json.loads(json.dumps(BREAKDOWN))
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"slot:{nate}"]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    url = f"/projects/{pid}/breakdown"
    assert not [p for p in editor.get(url).json()["problems"] if "isn't part of this" in p]
    assert editor.put(url, json=bd).status_code == 200  # an edit naming it is fine too
    board = f"/projects/{pid}/storyboard"
    refused = editor.post(board, json={"per_shot": False})
    assert refused.status_code == 409
    assert refused.json()["detail"] == "Nate has no approved look yet. Approve one in Cast."
    look = {"library_item_id": _look(owner, db, "Nate look")}
    assert editor.put(f"/projects/{pid}/assets/slots/{nate}", json=look).status_code == 200
    assert editor.post(board, json={"per_shot": False}).status_code == 201
    bd["scenes"][0]["shots"][1]["character_ids"] = [f"slot:{stranger}"]
    landed = editor.put(url, json=bd).json()  # another script's role: the shot's speaker's
    assert landed["breakdown"]["scenes"][0]["shots"][1]["character_ids"] == [f"slot:{nate}"]
    assert "Advice: Shot 1.2 now shows Nate, a role in this video." in landed["problems"]


def test_editors_search_and_filter_their_videos(app, owner, editor, db):
    """Gaps #13: by name, mine only, making or done, and brand."""
    dip, _ = _published(owner, db, breakdown=BREAKDOWN)
    mine = editor.post(f"{dip}/drafts/0/produce").json()["project_id"]
    two, _ = _second_editor(app, owner, db)
    fomo = owner.get("/brands").json()[0]["id"]
    theirs = two.post("/projects", json={"brand_id": fomo, "name": "Salmon"}).json()["id"]

    def ids(**params):
        return [p["id"] for p in editor.get("/projects", params=params).json()]

    assert ids(q="dip") == [mine] and ids(q="SALM") == [theirs]
    assert ids(mine=True) == [mine]
    assert ids(status="making") == [mine, theirs] and ids(status="done") == []
    db.get(Project, mine).finished_at = utcnow()
    db.commit()
    assert ids(status="done") == [mine]
    assert editor.get("/projects", params={"status": "done"}).json()[0]["finished_at"]
    assert ids(brand_id=fomo, mine=True, status="done", q="d") == [mine]


def test_a_versions_length_is_its_videos_once_it_has_a_breakdown(owner, editor, db):
    """LW9: the library said "about 40 s" (the owner's target) while the video's own breakdown,
    made inside the video, said 22 s. Once the video has a breakdown, its length is the one."""
    base, _ = _published(owner, db, target=40)
    made = editor.post(f"{base}/drafts/0/produce").json()
    assert owner.get(base).json()["versions"][0]["seconds"] == 40  # no breakdown yet: target
    db.get(Project, made["project_id"]).breakdown_seconds = 22
    db.commit()
    assert owner.get(base).json()["versions"][0]["seconds"] == 22


def test_only_a_video_made_from_a_script_waits_for_its_plan(owner, editor, db):
    """flows 1b: a script video's shots come from an approved plan; an earlier-way video (no
    script version, the old video page) keeps making its breakdown as before."""
    base, _ = _published(owner, db, target=40)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    db.query(Job).update({"status": JobStatus.cancelled})
    db.commit()
    refused = editor.post(f"/projects/{pid}/breakdown")
    assert (refused.status_code, refused.json()["detail"]) == (409, "Approve the plan first.")
    approved_plan(db, pid)
    assert editor.post(f"/projects/{pid}/breakdown").status_code == 201
    fomo = owner.get("/brands").json()[0]["id"]
    older = editor.post("/projects", json={"brand_id": fomo, "name": "Old way"}).json()["id"]
    editor.put(f"/projects/{older}/script", json={"text": SCRIPT})
    made = editor.post(f"/projects/{older}/breakdown")
    assert made.status_code == 201, made.text  # no plan asked for
