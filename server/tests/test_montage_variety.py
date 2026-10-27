"""Montage variety (Reed, 2026-10-27): a video's payoffs never repeat a recent video of the
same brand. The breakdown (and the script writers) are told where the brand's last 5 other
montages landed, and a word-for-word repeat is advice. Free; library drafts don't count."""

import copy

from app.models.jobs import Job
from app.models.projects import Project
from app.prompts import check
from app.prompts.schemas import Breakdown
from tests.test_breakdown import BREAKDOWN, _shot
from tests.test_enhance import SCRIPT, FakeClaude, _run, setup  # noqa: F401 - fixture

ACTIONS = ["A red day on the chart.", "Late night, still trading.", "A small win.",
           "The balance jumps to $348,920.", "He tosses his keys to a valet."]  # fmt: skip


def _montage() -> dict:
    bd = copy.deepcopy(BREAKDOWN)
    quick = [_shot(f"1.{n}", [], None, None, 0.5) | {"action": a} for n, a in enumerate(ACTIONS, 3)]
    bd["scenes"][0]["shots"] += quick
    bd["clips"][0]["shot_ids"] += [s["id"] for s in quick]
    return bd


def _video(editor, name: str) -> int:
    fomo = editor.get("/brands").json()[0]["id"]
    pid = editor.post(
        "/projects", json={"brand_id": fomo, "name": name, "planned_seconds": 30}
    ).json()["id"]
    editor.put(f"/projects/{pid}/script", json={"text": SCRIPT})
    return pid


def test_the_payoff_is_where_the_montage_lands():
    shots = [s for scene in Breakdown.model_validate(_montage()).scenes for s in scene.shots]
    assert [s.action for s in check.payoff(shots)] == ACTIONS[-3:]
    assert check.payoff(shots[:2]) == []  # no montage, no payoff


def test_recent_payoffs_are_told_and_a_repeat_is_advice(app, db, editor, setup):  # noqa: F811
    first = setup["project"]
    db.get(Project, first).name = "Altar reel"
    db.commit()
    editor.post(f"/projects/{first}/breakdown")
    _run(app, db, FakeClaude(_montage()))
    gone = _video(editor, "Put away")
    editor.post(f"/projects/{gone}/breakdown")
    _run(app, db, FakeClaude(_montage()))
    db.get(Project, gone).archived_at = db.get(Project, first).created_at  # archived: left out
    db.commit()

    second = _video(editor, "Second")
    editor.post(f"/projects/{second}/breakdown")
    job = db.query(Job).filter(Job.input["project_id"].as_integer() == second).one()
    block = job.input["prompt"].split("<recent_payoffs>")[1].split("</recent_payoffs>")[0]
    assert block.strip() == '"Altar reel": ' + "; ".join(ACTIONS[-3:])
    _run(app, db, FakeClaude(_montage()))  # the same payoff again
    problems = editor.get(f"/projects/{second}/breakdown").json()["problems"]
    repeats = [p for p in problems if "repeats one of a recent video" in p]
    assert len(repeats) == 3 and all(p.startswith("Advice: ") for p in repeats)
    first_job = db.query(Job).filter(Job.input["project_id"].as_integer() == first).one()
    assert "<recent_payoffs>" not in first_job.input["prompt"]  # nothing before it


def test_a_video_whose_script_is_private_to_someone_else_is_left_out(app, db, owner, editor, setup):  # noqa: F811
    # QA: the model never sees another person's private work.
    from app.breakdown import recent_payoffs
    from app.models.script_library import Script, ScriptDraft

    first = setup["project"]
    editor.post(f"/projects/{first}/breakdown")
    _run(app, db, FakeClaude(_montage()))
    made = owner.post(
        "/scripts", json={"brand_id": db.get(Project, first).brand_id, "title": "Mine"}
    )
    script = db.get(Script, made.json()["id"])  # owner's, never published
    project = db.get(Project, first)
    project.script_draft_id = db.query(ScriptDraft).filter_by(script_id=script.id).one().id
    db.commit()
    brand = project.brand_id
    assert recent_payoffs(db, brand, viewer=script.created_by_id)  # its author sees it
    editor_id = db.get(Project, _video(editor, "Theirs")).created_by_id
    assert recent_payoffs(db, brand, viewer=editor_id) == []  # someone else doesn't
