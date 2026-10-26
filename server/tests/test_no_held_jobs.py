"""Reed, 2026-10-26: past a limit an editor is refused with the reason, and nothing ever waits
for Reed's OK. Every paid route is walked as an editor past the limit: a library version past
its budget, and the editor's own work past their week."""

from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_cast_roles import _video
from tests.test_script_library import SCRIPT, _make

BUDGET = "That's more than this video's budget."


def _spent(db, project, credits):
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=project.id, credits=credits, status="succeeded"))  # fmt: skip
    db.commit()


def _posts(client, calls):
    """POST each (url, body); the answers keyed by url."""
    return {url: client.post(url, json=body) for url, body in calls}


def test_every_paid_video_route_refuses_an_editor_past_the_budget(owner, editor, db):
    pid, mia, kid = _video(owner, editor, db)
    with_sheet(db, kid)
    project = db.get(Project, pid)
    newest = (
        db.query(BreakdownVersion)
        .filter_by(project_id=pid)
        .order_by(BreakdownVersion.id.desc())
        .first()
    )
    frame = StoryboardFrame(project_id=pid, breakdown_id=newest.id, clip_id="c1", shot_id="1.2",
                            prompt="Kid at the table.", reference_ids=[f"char:{kid}"],
                            file_id=upload(editor))  # fmt: skip
    clip = ProjectClip(project_id=pid, breakdown_id=newest.id, clip_id="c1", seconds=5,
                       prompt="Shot 1 | 0-5 s. Kid eats.", references=[])  # fmt: skip
    db.add_all([frame, clip])
    db.commit()
    _spent(db, project, project.budget_credits)  # the video's budget is all spent
    jobs = db.query(Job).count()
    slot = next(r for r in editor.get(f"/projects/{pid}/assets").json() if r["role"] == "Nate")
    v = f"/projects/{pid}"
    answers = _posts(editor, [
        (f"{v}/breakdown", {}),
        (f"{v}/storyboard", {}),
        (f"{v}/storyboard/frames/{frame.id}/render", {}),
        (f"{v}/storyboard/frames/{frame.id}/change", {"note": "Brighter."}),
        (f"{v}/clips/prompts", {"clip_id": "c1"}),  # rewrite one clip (paid)
        (f"{v}/clips/{clip.id}/generate", {}),
        (f"{v}/clips/{clip.id}/change", {"note": "Slower push in."}),
        (f"{v}/assets/slots/{slot['slot_id']}/make-look", {}),
    ])  # fmt: skip
    for url, r in answers.items():
        assert r.status_code in (409, 422), (url, r.status_code, r.text)
    assert {u: r.json()["detail"] for u, r in answers.items()} == dict.fromkeys(answers, BUDGET)
    assert not any("Reed" in str(r.json()["detail"]) for r in answers.values())
    assert db.query(Job).count() == jobs  # nothing queued, nothing held
    assert not db.query(Job).filter_by(status=JobStatus.needs_owner_approval).count()


def test_an_editors_own_work_past_the_week_is_refused_never_held(owner, editor, db):
    limits = owner.get("/credits/limits").json()
    owner.put("/credits/limits", json={**limits, "weekly_quick_clip_credits": 0})
    fomo = editor.get("/brands").json()[0]["id"]
    sid = _make(editor, text=SCRIPT)["id"]
    s = f"/scripts/{sid}"
    look = editor.post("/library/character", json={"name": "Bo", "notes": "a pug"}).json()["id"]
    jobs = db.query(Job).count()
    answers = _posts(editor, [
        (f"{s}/write", {}),
        (f"{s}/variations", {}),
        (f"{s}/cast/read", {}),
        (f"{s}/drafts/0/enhance", {}),
        (f"{s}/drafts/0/breakdown", {}),
        ("/clips/improve", {"brand_id": fomo, "prompt": "A dog eats.", "duration": 5}),
        (f"/library/character/{look}/sheet", {}),
    ])  # fmt: skip
    for url, r in answers.items():
        assert r.status_code in (409, 422), (url, r.status_code, r.text)
    other = {u: r.json()["detail"] for u, r in answers.items() if "this week" not in r.text}
    # Variations and the cast read need an approved original first; every other is the week
    assert other == dict.fromkeys(
        [f"{s}/variations", f"{s}/cast/read"], "Approve the original first."
    )
    assert db.query(Job).count() == jobs
    assert not db.query(Job).filter_by(status=JobStatus.needs_owner_approval).count()
