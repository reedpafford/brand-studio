"""Reed, 30 Oct ("Hold requests"): past a limit an editor's press waits for the owner, charged
nothing until approved, and says why (never "ask Reed"). Every paid route is walked as an
editor past the limit: a video past its budget, and the editor's Quick clips past their week."""

from app.credits import credits_used
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


def test_every_paid_video_route_holds_an_editors_press_past_the_budget(owner, editor, db):
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
    calls = [
        (f"{v}/breakdown", {}),
        (f"{v}/storyboard", {}),
        (f"{v}/storyboard/frames/{frame.id}/render", {}),
        (f"{v}/storyboard/frames/{frame.id}/change", {"note": "Brighter."}),
        (f"{v}/clips/prompts", {"clip_id": "c1"}),  # rewrite one clip (paid)
        (f"{v}/clips/{clip.id}/generate", {}),
        (f"{v}/clips/{clip.id}/change", {"note": "Slower push in."}),
        (f"{v}/assets/slots/{slot['slot_id']}/make-look", {}),
    ]  # fmt: skip
    for url, body in calls:
        r = editor.post(url, json=body)
        assert r.status_code in (200, 201) and "Reed" not in r.text, (url, r.status_code, r.text)
        (held,) = db.query(Job).filter_by(status=JobStatus.needs_owner_approval).all()
        assert held.input["held"] == BUDGET  # why, as the editor sees it
        assert editor.get(f"/jobs/{held.id}").json()["held"] == BUDGET
        assert credits_used(db, project) == project.budget_credits  # nothing charged
        withdrawn = editor.post(f"/jobs/{held.id}/cancel").json()
        assert (withdrawn["status"], withdrawn["declined"]) == ("cancelled", False)
        db.expire_all()
    assert db.query(Job).count() == jobs + len(calls)  # one held request per press


def test_past_the_week_only_a_quick_clip_waits_for_the_owner(owner, editor, db):
    """One allowance (Reed, 30 Oct): the week counts Quick clips only. Script work, looks and
    Improve are a brand's work, never held for the week; a Quick clip past it waits."""
    limits = owner.get("/credits/limits").json()
    owner.put("/credits/limits", json={**limits, "weekly_quick_clip_credits": 0})
    fomo = editor.get("/brands").json()[0]["id"]
    sid = _make(editor, text=SCRIPT)["id"]
    s = f"/scripts/{sid}"
    look = editor.post("/library/character", json={"name": "Bo", "notes": "a pug"}).json()["id"]
    answers = {url: editor.post(url, json=body) for url, body in [
        (f"{s}/write", {}),
        (f"{s}/drafts/0/enhance", {}),
        (f"{s}/drafts/0/breakdown", {}),
        ("/clips/improve", {"brand_id": fomo, "prompt": "A dog eats.", "duration": 5}),
        (f"/library/character/{look}/sheet", {}),
    ]}  # fmt: skip
    for url, r in answers.items():
        assert "this week" not in r.text, (url, r.text)
    assert not db.query(Job).filter_by(status=JobStatus.needs_owner_approval).count()
    clip = editor.post("/clips", json={"brand_id": fomo, "prompt": "A dog eats.", "duration": 5})
    assert clip.status_code == 201 and clip.json()["status"] == "needs_owner_approval"
    assert clip.json()["held"] == "You've used this week's 0 credits. It resets on Monday."
