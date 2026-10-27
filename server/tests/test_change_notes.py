"""Change it in plain English (change-notes.md §1), with a mocked Claude (no paid calls): a
note rewrites a still's or a clip's prompt, then the still or a new take is made; dialogue
notes are refused before any charge; a prompt that comes back the same costs nothing; picking
the earlier still or take puts its prompt back. And the owner's refund of one charge."""

from decimal import Decimal

from app.clip_takes import save_take
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus, Usage
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.storyboard import save_still
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_cast_roles import _video
from tests.test_clip_takes import clip  # noqa: F401 - fixture
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_storyboard import _frames, _with_breakdown


def _frame(app, db, editor, setup):  # noqa: F811
    mom = editor.post(
        "/library/character", json={"name": "Mom", "image_file_ids": [upload(editor)]}
    )
    with_sheet(db, mom.json()["id"])
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": [mom.json()["id"]]})
    _with_breakdown(app, db, editor, setup)
    url = f"/projects/{setup['project']}/storyboard"
    editor.post(url, json={})
    _run(app, db, FakeClaude(_frames(f"char:{mom.json()['id']}", f"screen:{setup['screen']}")))
    frame = db.get(StoryboardFrame, editor.get(url).json()[0]["id"])
    frame.file_id, frame.approved = upload(editor), True  # a still, approved
    db.commit()
    return url, frame


def test_a_note_changes_a_still_and_picking_the_earlier_one_undoes_it(app, db, editor, setup):  # noqa: F811
    url, frame = _frame(app, db, editor, setup)
    change = f"{url}/frames/{frame.id}/change"
    assert editor.get(change).json()["credits"] >= 1  # Change it · N
    jobs = db.query(Job).count()
    empty = editor.post(change, json={"note": " "})
    assert (empty.status_code, empty.json()["detail"]) == (422, "Say what should change.")
    said = editor.post(change, json={"note": 'Make her say "where is the dip?"'})
    assert said.status_code == 422 and "never its words" in said.json()["detail"]
    assert db.query(Job).count() == jobs  # nothing charged

    before, old_still = frame.prompt, frame.file_id
    job = editor.post(change, json={"note": "She looks surprised, not sad."})
    assert job.status_code == 201 and job.json()["step"] == "change"
    assert "The Keep line follows the change" in db.get(Job, job.json()["id"]).input["system"][0]
    assert editor.post(change, json={"note": "again"}).json()["detail"] == (
        "This one is still being made."
    )
    after = f"{before} She looks surprised, ears up."
    _run(app, db, FakeClaude({"prompt": after}))
    db.expire_all()
    shown = next(f for f in editor.get(url).json() if f["id"] == frame.id)
    assert (shown["prompt"], shown["approved"]) == (after, False)
    assert shown["change"]["before"] == before and shown["change"]["after"] == after
    draw = db.get(Job, shown["change"]["made_job_id"])
    assert draw.input["step"] == "frame" and draw.input["was_prompt"] == before

    draw.output = {"file_ids": [upload(editor)]}  # the new still lands
    save_still(db, draw)
    db.commit()
    assert db.get(StoryboardFrame, frame.id).earlier[-1] == {"file_id": old_still, "prompt": before}
    back = editor.post(f"{url}/frames/{frame.id}/pick", json={"file_id": old_still}).json()
    assert (back["file_id"], back["prompt"]) == (old_still, before)  # Undo: free
    assert back["earlier"][-1]["prompt"] == after


def test_a_note_that_changes_nothing_makes_and_costs_nothing(app, db, editor, setup):  # noqa: F811
    url, frame = _frame(app, db, editor, setup)
    job = editor.post(f"{url}/frames/{frame.id}/change", json={"note": "Keep it as is."}).json()
    _run(app, db, FakeClaude({"prompt": f"  {frame.prompt}  "}))
    db.expire_all()
    row = db.get(StoryboardFrame, frame.id)
    assert row.change["unchanged"] is True and "made_job_id" not in row.change
    assert db.get(Job, job["id"]).credits == 0
    assert not [j for j in db.query(Job).all() if j.input.get("step") == "frame"]


def test_a_clip_note_rewrites_the_prompt_then_makes_a_new_take(app, db, editor, setup, clip):  # noqa: F811
    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    row = db.get(ProjectClip, clip["id"])
    row.prompt_ok = True
    db.commit()
    prompt_only = editor.get(f"{url}/change").json()["credits"]
    editor.post(f"{url}/change", json={"note": "Mom slams the wallet down harder."})
    first = f"{clip['prompt']}\nMom slams the wallet down harder."
    _run(app, db, FakeClaude({"prompt": first}))
    db.expire_all()
    row = db.get(ProjectClip, clip["id"])
    assert (row.prompt, row.prompt_ok) == (first, False)  # written again: read it again
    assert "made_job_id" not in row.change  # no take yet: only the prompt

    take = ClipTake(clip_id=row.id, number=1, job_id=row.job_id, file_id=upload(editor))
    db.add(take)
    db.flush()
    row.picked_take_id, row.file_id = take.id, take.file_id
    db.commit()
    assert editor.get(f"{url}/change").json()["credits"] > prompt_only  # now with a take
    editor.post(f"{url}/change", json={"note": "Slower push in."})
    _run(app, db, FakeClaude({"prompt": f"{first}\nSlower push in."}))
    db.expire_all()
    made = db.get(Job, db.get(ProjectClip, clip["id"]).change["made_job_id"])
    assert made.input["step"] == "clip_take" and made.input["clip_prompt"].endswith("push in.")
    assert db.get(ClipTake, take.id).prompt == first  # an older take keeps its prompt
    made.output = {"file_ids": [upload(editor)]}  # the new take lands, and is picked
    save_take(db, made)
    db.commit()
    back = editor.post(f"{url}/takes/{take.id}/pick").json()
    assert back["prompt"] == first  # picking it back puts its prompt back


def test_the_owner_refunds_one_charge_once(owner, editor, db):
    pid, _, _ = _video(owner, editor, db)
    project = db.get(Project, pid)
    job = Job(workspace_id=project.workspace_id, created_by_id=project.created_by_id, kind="image",
              provider="fake", input={"step": "frame"}, project_id=pid, credits=Decimal(4),
              status="succeeded")  # fmt: skip
    db.add(job)
    db.flush()
    charge = Usage(workspace_id=project.workspace_id, job_id=job.id, provider="fake", kind="image",
                   units=Decimal(1), unit="image", cost_usd=Decimal("0.04"))  # fmt: skip
    db.add(charge)
    db.commit()
    url = f"/usage/charges/{charge.id}/refund"
    assert editor.post(url, json={"reason": "wrong person"}).status_code == 404  # never seen
    before = owner.get(f"/projects/{pid}").json()["credits_used"]
    first = owner.post(url, json={"reason": "a still with the wrong person"}).json()
    assert (first["credits"], first["reason"], first["by"]["name"]) == (
        4, "a still with the wrong person", "Reed"
    )  # fmt: skip
    assert owner.get(f"/projects/{pid}").json()["credits_used"] == before - 4
    again = owner.post(url, json={"reason": "again"})
    assert (again.status_code, again.json()["detail"]) == (
        409, "Those credits were already given back."
    )  # fmt: skip
    assert owner.get(f"/projects/{pid}").json()["credits_used"] == before - 4  # not twice
    row = next(c for c in owner.get("/usage/charges").json()["items"] if c["id"] == charge.id)
    assert row["cost_usd"] == 0.04 and row["credits"] == 0  # the dollars stay spent
    assert (row["refunded"]["credits"], row["refunded"]["reason"]) == (
        4,
        "a still with the wrong person",
    )  # the struck credits and the reason, after a reload
    assert row["refunded"]["at"] == first["at"]
    others = [c for c in owner.get("/usage/charges").json()["items"] if c["id"] != charge.id]
    assert all(c["refunded"] is None for c in others)


def test_an_editors_change_holds_its_whole_price_on_their_week(app, db, owner, editor, setup):  # noqa: F811
    """Producer: on an editor's own script, the rewrite and the still it pays for are checked
    and held together, so nothing started meanwhile can take the week past its allowance."""
    from app.change import credits as price
    from app.credits import credits_left
    from app.models.accounts import User
    from app.models.script_library import ScriptDraft

    url, frame = _frame(app, db, editor, setup)
    fomo = editor.get("/brands").json()[0]["id"]
    script = editor.post("/scripts", json={"brand_id": fomo, "title": "S", "text": "A: hi"})
    project = db.get(Project, setup["project"])
    draft = db.query(ScriptDraft).filter_by(script_id=script.json()["id"]).one()
    project.script_draft_id = draft.id  # the editor's own script: their week pays
    db.commit()
    ed = db.query(User).filter_by(email=editor.get("/auth/me").json()["email"]).one()
    whole = price(db, project, frame)
    limits = owner.get("/credits/limits").json()
    used = float(145 - credits_left(db, ed))
    tight = used + float(whole) - 0.01  # the rewrite fits; the rewrite and the still don't
    owner.put("/credits/limits", json={**limits, "weekly_quick_clip_credits": tight})
    refused = editor.post(f"{url}/frames/{frame.id}/change", json={"note": "Brighter."})
    assert refused.status_code == 409 and "free credits" in refused.json()["detail"]
    owner.put("/credits/limits", json={**limits, "weekly_quick_clip_credits": 145})
    before = credits_left(db, ed)
    sent = editor.post(f"{url}/frames/{frame.id}/change", json={"note": "Brighter."})
    assert sent.status_code == 201
    assert before - credits_left(db, ed) == whole  # the still is held while the note is read


def test_undo_goes_back_to_the_take_picked_before_the_change(app, db, editor, setup, clip):  # noqa: F811
    """QA-2 on #427: three takes, take 1 picked; the change's Undo returns to take 1."""
    url = f"/projects/{setup['project']}/clips/{clip['id']}"
    row = db.get(ProjectClip, clip["id"])
    takes, files = [], [upload(editor) for _ in range(4)]
    for n in (1, 2, 3):
        take = ClipTake(clip_id=row.id, number=n, job_id=row.job_id, file_id=files[n],
                        prompt=row.prompt)  # fmt: skip
        db.add(take)
        db.flush()
        takes.append(take)
    row.picked_take_id, row.file_id = takes[0].id, takes[0].file_id
    db.commit()
    editor.post(f"{url}/change", json={"note": "Slower push in."})
    _run(app, db, FakeClaude({"prompt": f"{clip['prompt']}\nSlower push in."}))
    db.expire_all()
    made = db.get(Job, db.get(ProjectClip, clip["id"]).change["made_job_id"])
    made.output = {"file_ids": [files[0]]}
    save_take(db, made)  # take 4 lands and is picked
    db.commit()
    shown = editor.get(f"/projects/{setup['project']}/clips").json()[0]
    assert shown["change"]["was_take_id"] == takes[0].id  # not take 3
    back = editor.post(f"{url}/takes/{takes[0].id}/pick").json()
    assert (back["picked_take_id"], back["prompt"]) == (takes[0].id, clip["prompt"])


def test_a_stills_change_remembers_the_still_it_replaces(app, db, editor, setup):  # noqa: F811
    url, frame = _frame(app, db, editor, setup)
    old = frame.file_id
    editor.post(f"{url}/frames/{frame.id}/change", json={"note": "Brighter."})
    shown = next(f for f in editor.get(url).json() if f["id"] == frame.id)
    assert shown["change"]["was_file_id"] == old
    _run(app, db, FakeClaude({"prompt": f"{frame.prompt} Brighter."}))
    db.expire_all()
    assert db.get(StoryboardFrame, frame.id).change["was_file_id"] == old  # kept after the rewrite


def test_a_refused_still_never_loses_the_rewrite_it_paid_for(app, db, editor, setup):  # noqa: F811
    """A Change it rewrite lands after the video's money ran out: the still is refused, but
    the new prompt (a paid answer) is kept and the change says why."""
    url, frame = _frame(app, db, editor, setup)
    editor.post(f"{url}/frames/{frame.id}/change", json={"note": "Brighter."})
    project = db.get(Project, setup["project"])
    db.add(Job(workspace_id=project.workspace_id, kind="image", provider="fake", input={},
               project_id=project.id, credits=project.budget_credits * 10,
               status="succeeded"))  # fmt: skip
    db.commit()
    after = f"{frame.prompt} Brighter."
    _run(app, db, FakeClaude({"prompt": after}))
    db.expire_all()
    row = db.get(StoryboardFrame, frame.id)
    assert row.prompt == after  # kept, though nothing more could be made
    assert row.change["status"] == "failed" and row.change["error"]
    assert "made_job_id" not in row.change


def test_a_frame_says_drawing_until_its_new_still_lands_and_a_failed_rewrite_says_so(
    app,
    db,
    editor,
    setup,  # noqa: F811
):
    # Reed's "I submit and nothing happens": the page must keep checking until the still is in.
    url, frame = _frame(app, db, editor, setup)
    shown = lambda: next(f for f in editor.get(url).json() if f["id"] == frame.id)  # noqa: E731
    editor.post(f"{url}/frames/{frame.id}/change", json={"note": "Make it night."})
    _run(app, db, FakeClaude({"prompt": f"{frame.prompt} At night."}))
    db.expire_all()
    assert shown()["drawing"] is True
    draw = db.get(Job, shown()["change"]["made_job_id"])
    draw.status, draw.output = JobStatus.succeeded, {"file_ids": [upload(editor)]}
    save_still(db, draw)
    db.commit()
    assert shown()["drawing"] is False and shown()["file_id"] == draw.output["file_ids"][0]

    job = editor.post(f"{url}/frames/{frame.id}/change", json={"note": "Warmer."}).json()
    db.get(Job, job["id"]).status = JobStatus.failed  # the rewrite never came back
    db.commit()
    assert shown()["change"]["status"] == "failed" and shown()["change"]["error"]
