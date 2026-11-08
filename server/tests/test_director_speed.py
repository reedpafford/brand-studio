"""Reed, 8 Nov: "make the site much faster and remove every wasteful call and turn, without
lowering quality". The server takes the mechanical steps itself (no Claude call), flagged
stills are drawn again together, and work that never ran is never counted as used. On the
stand-ins."""

import copy
import re
from decimal import Decimal

from app import director, director_auto
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus, Usage
from app.models.projects import Project
from tests.test_breakdown import BREAKDOWN
from tests.test_director import _run
from tests.test_freestyle_dialogue import _run as _run_fakes
from tests.test_freestyle_song import NARRATION, _sent, songs_on  # noqa: F401
from tests.test_script_library import SCRIPT, _make


def _turns(db, pid) -> list[Job]:
    return director.all_turns(db, pid)


def test_a_narrated_run_takes_its_mechanical_steps_without_a_claude_call(app, db, owner):
    """Before: 18 Claude turns on this run, one after another. Now the server approves the
    plan, makes the storyboard and the stills, reviews them, writes the prompts, makes every
    first take and watches each cut itself, each logged in the run like a turn."""
    fs = _sent(owner, "narrated", NARRATION)
    _run_fakes(app, db, ticks=120)
    pid = db.get(Freestyle, fs["id"]).project_id
    assert owner.get(f"/freestyles/{fs['id']}").json()["status"] == "delivered"
    turns = _turns(db, pid)
    claude = [t for t in turns if not t.input.get(director_auto.SAID)]
    server = [t for t in turns if t.input.get(director_auto.SAID)]
    assert len(claude) <= 9 and len(turns) <= 20, [(t.output["tool"], t.input["result"])
                                                  for t in turns]  # fmt: skip
    assert {t.output["tool"] for t in server} >= {"plan", "storyboard", "stills",
                                                  "review_stills", "clip_prompts",
                                                  "make_take", "watch_cut"}  # fmt: skip
    assert all(t.kind == "director_step" and t.credits == 0 and t.status == JobStatus.succeeded
               and not t.input["result"].startswith("Refused") for t in server)  # fmt: skip
    assert {t.output["tool"] for t in claude} & {"treatment", "narration", "deliver"} == {
        "treatment",
        "narration",
        "deliver",
    }  # the judgments stay the director's
    shown = owner.get(f"/projects/{pid}/director").json()["turns"]
    assert len(shown) == len(turns)  # every step is in its log


def _two_clips(app, owner, editor) -> int:
    """A published script whose two lines are two clips, so two stills."""
    app.state.settings.fake_providers = True
    base = f"/scripts/{_make(owner, text=SCRIPT)['id']}"
    bd = copy.deepcopy(BREAKDOWN)
    bd["clips"] = [
        {"id": "c1", "shot_ids": ["1.1"], "seconds": 4, "seam": "Cut."},
        {"id": "c2", "shot_ids": ["1.2"], "seconds": 4, "seam": "End of scene."},
    ]
    owner.put(f"{base}/drafts/0/breakdown", json=bd)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return editor.post(f"{base}/drafts/0/produce").json()["project_id"]


def test_every_flagged_still_is_drawn_again_in_one_move(app, db, owner, editor, monkeypatch):
    """Video 261: four redraws, one turn and one wait each (3 min). One move draws them all."""
    from app.providers.fake_local import FakeWriter

    def every_still_off(self, prompt):
        return {"ready": False, "findings": [
            {"shot_id": s, "problem": "Off the hook.", "note": f"Open on the hook ({s})."}
            for s in re.findall(r"\[Image\d+\] shot (\S+):", prompt)]}  # fmt: skip

    monkeypatch.setattr(FakeWriter, "_review_stills", every_still_off)
    pid = _two_clips(app, owner, editor)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=150)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    (redraw,) = [t for t in out["turns"] if t["tool"] == "redraw_still"]
    assert redraw["result"].count("Drawing shot ") == 2, redraw["result"]
    run = _turns(db, pid)[-1].input[director.RUN]
    assert run["redraws"] == {"1.1": 1, "1.2": 1}
    changes = [j for j in db.query(Job).filter(Job.project_id == pid)
               if j.input.get("step") == "change"]  # fmt: skip
    assert len({j.created_at for j in changes}) <= 2 and len(changes) == 2  # queued together


def test_work_that_never_ran_is_never_counted_as_used(app, db, owner, editor):
    """A redo whose take failed (or was declined) and a watch that failed give their count
    back; a redo that was made stays spent."""
    from tests.test_director import _made

    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    project = db.get(Project, pid)
    take = db.query(Job).filter(Job.project_id == pid, Job.kind == "video").first()
    run = {"id": "r", "redos": {"c1": 2}, "watches": 1, director.SPENDS: [
        {"used": {"redos/c1": 1}, "jobs": [take.id]}]}  # fmt: skip
    assert director._refund(db, project, run)["redos"] == {"c1": 2}  # it ran: spent
    take.status = JobStatus.failed
    retry = Job(
        workspace_id=take.workspace_id,
        created_by_id=take.created_by_id,
        kind="video",
        provider=take.provider,
        project_id=pid,
        input=take.input,
        retry_of_id=take.id,
        auto=True,
        status=JobStatus.queued,
    )  # its automatic retry (clip_takes._again)
    db.add(retry)
    db.commit()
    assert director._refund(db, project, run) == run  # still going: kept
    retry.status = JobStatus.succeeded
    db.commit()
    assert director._refund(db, project, run)["redos"] == {"c1": 2}  # the retry ran: spent
    retry.status = JobStatus.failed
    db.add(
        Usage(
            workspace_id=take.workspace_id,
            job_id=retry.id,
            provider=take.provider,
            kind="video",
            units=1,
            unit="second",
            cost_usd=Decimal("0.4"),
        )
    )
    db.commit()
    assert director._refund(db, project, run)["redos"] == {"c1": 2}  # billed anyway: spent
    db.query(Usage).filter(Usage.job_id == retry.id).delete()
    db.commit()
    given = director._refund(db, project, run)
    assert given["redos"] == {"c1": 1} and given[director.SPENDS] == []
    assert director._refund(db, project, given) == given  # once
    cut = (
        db.query(Job)
        .filter(Job.project_id == pid, Job.input["step"].as_string() == "watch_cut")
        .all()[-1]
    )
    run = {"id": "r", "watches": 2, director.SPENDS: [
        {"used": {"watches": 1}, "cut": cut.input["final_video_id"]}]}  # fmt: skip
    assert director._refund(db, project, run)["watches"] == 2  # it watched
    cut.status = JobStatus.failed
    db.commit()
    assert director._refund(db, project, run)["watches"] == 1
