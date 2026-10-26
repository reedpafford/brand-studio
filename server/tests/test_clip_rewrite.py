"""Clips never dead-ends (Reed, 2026-10-26, #503): stale clip prompts are rewritten in place,
their takes kept; after a breakdown change it happens by itself within the budget; a recast
carries clips for free; Reed's stale videos are repaired once, free to him. Mocked: no paid
calls."""

import copy

from app import cast_roles, clip_prompts
from app.models.accounts import Role, User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.seed import rewrite_owner_clips
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_project_clips import _answer, _prompt


def _rewrites(db, pid):
    return [j for j in db.query(Job).filter_by(project_id=pid).all()
            if j.input.get("step") == "clip_prompts" and j.status == "queued"]  # fmt: skip


def _current(db, pid):
    return copy.deepcopy(clip_prompts.newest(db, db.get(Project, pid)).data)


def _newer_breakdown(db, pid):
    """A breakdown change that isn't a recast (saved directly: nothing follows it)."""
    bd = clip_prompts.newest(db, db.get(Project, pid))
    row = BreakdownVersion(project_id=pid, script_version=bd.script_version, source="edit",
                           data=copy.deepcopy(bd.data), problems=[])  # fmt: skip
    db.add(row)
    db.commit()
    return row


def test_a_breakdown_change_rewrites_stale_clips(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    editor.post(f"{base}/clips/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    before = editor.get(f"{base}/clips").json()[0]
    assert len(before["takes"]) == 1 and before["picked_take_id"]

    editor.put(f"{base}/breakdown", json=_current(db, setup["project"]))
    assert editor.get(f"{base}/clips").json()[0]["stale"] is True
    (job,) = _rewrites(db, setup["project"])  # queued by itself, for the stale clip
    assert job.input["clip_ids"] == ["c1"]
    refused = editor.post(f"{base}/clips/{clip['id']}/generate")
    assert refused.json()["detail"] == (
        "This clip was made for an older breakdown. Rewrite its prompt first."
    )

    _run(app, db, FakeClaude(_answer(clip["references"][0]["id"][5:], setup["screen"], _prompt())))
    db.expire_all()
    after = editor.get(f"{base}/clips").json()[0]
    assert after["stale"] is False and after["id"] == before["id"]
    assert [t["id"] for t in after["takes"]] == [t["id"] for t in before["takes"]]  # kept
    assert after["picked_take_id"] == before["picked_take_id"]
    assert editor.post(f"{base}/clips/{clip['id']}/generate").status_code == 201  # unblocked


def test_past_the_budget_nothing_is_rewritten_by_itself(app, db, editor, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    project = db.get(Project, setup["project"])
    spent = Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
                project_id=project.id, credits=project.budget_credits,
                status="succeeded")  # fmt: skip
    db.add(spent)
    db.commit()
    saved = editor.put(f"{base}/breakdown", json=_current(db, setup["project"]))
    assert saved.status_code == 200  # never blocked
    assert not _rewrites(db, setup["project"])  # past the budget: skipped
    price = editor.get(f"{base}/clips/prompts/price").json()
    assert price == {"clip_ids": ["c1"], "credits": 3}  # the button stays, with its price
    pressed = editor.post(f"{base}/clips/prompts")
    assert pressed.status_code == 409 and "budget" in pressed.json()["detail"]


def test_a_recast_carries_clips_for_free(app, db, editor, setup, clip):  # noqa: F811
    project = db.get(Project, setup["project"])
    mom = clip["references"][0]["id"]
    kid = editor.post(
        "/library/character", json={"name": "Kid", "image_file_ids": [upload(editor)]}
    )
    with_sheet(db, kid.json()["id"])
    old = clip_prompts.newest(db, project)
    data = copy.deepcopy(old.data)
    data["scenes"][0]["shots"][0]["character_ids"] = [f"char:{kid.json()['id']}"]
    new = BreakdownVersion(project_id=project.id, script_version=old.script_version,
                           source="edit", data=data, problems=[])  # fmt: skip
    db.add(new)
    db.flush()
    assert cast_roles.carry_clips(db, project, old, new) == 1
    db.commit()
    row = db.get(ProjectClip, clip["id"])
    assert row.breakdown_id == new.id and mom not in [r["id"] for r in row.references]
    assert "Kid" in row.prompt and not _rewrites(db, project.id)  # no model call


def test_reeds_current_video_is_rewritten_once_free(app, db, owner, editor, setup, clip):  # noqa: F811
    """Producer: only the owner-made video edited most recently, once, free; never while a
    take is being made on it."""
    project = db.get(Project, setup["project"])
    reed = db.query(User).filter_by(role=Role.owner).one()
    project.created_by_id = reed.id  # Reed's own video
    db.commit()
    _newer_breakdown(db, project.id)
    take = Job(workspace_id=project.workspace_id, created_by_id=reed.id, kind="video",
               provider="fake", input={"step": "clip_take"}, project_id=project.id)  # fmt: skip
    db.add(take)
    db.commit()
    assert rewrite_owner_clips(db) == 0  # a take is being made: not now
    take.status = "succeeded"
    db.commit()
    assert rewrite_owner_clips(db) == 1
    (job,) = _rewrites(db, project.id)
    assert (job.credits, job.input["repair"], job.input["clip_ids"]) == (0, True, ["c1"])
    _run(app, db, FakeClaude(_answer(clip["references"][0]["id"][5:], setup["screen"], _prompt())))
    db.expire_all()
    assert db.get(Job, job.id).credits == 0  # free to him: no budget, no week
    assert editor.get(f"/projects/{project.id}/clips").json()[0]["stale"] is False
    _newer_breakdown(db, project.id)
    assert rewrite_owner_clips(db) == 0  # once ever: next time it's the button


def test_only_the_video_edited_last_is_repaired(app, db, owner, editor, setup, clip):  # noqa: F811
    reed = db.query(User).filter_by(role=Role.owner).one()
    first = db.get(Project, setup["project"])
    first.created_by_id = reed.id
    other = Project(workspace_id=first.workspace_id, brand_id=first.brand_id, name="Other",
                    created_by_id=reed.id)  # fmt: skip
    db.add(other)
    db.commit()
    bd = clip_prompts.newest(db, first)
    db.add(BreakdownVersion(project_id=other.id, script_version=bd.script_version,
                            source="edit", data=copy.deepcopy(bd.data), problems=[]))  # fmt: skip
    db.add(ProjectClip(project_id=other.id, breakdown_id=bd.id, clip_id="c1", seconds=5,
                       prompt="x", references=[]))  # fmt: skip
    db.commit()
    _newer_breakdown(db, first.id)  # the first video was edited last
    assert rewrite_owner_clips(db) == 1
    assert len(_rewrites(db, first.id)) == 1 and not _rewrites(db, other.id)
