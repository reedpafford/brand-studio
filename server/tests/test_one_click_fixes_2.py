"""No dead ends, part 2 (Reed, #520; spec one-click-fixes.md §4-5): a frame the image model
may refuse is softened (by itself when it's made, or with Soften it), and Fix this clip's
prompt is free: its shape is put right in code, and what code can't fix Claude rewrites for
that clip only, charged to no budget or week."""

from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.storyboards import StoryboardFrame
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_project_clips import _answer, _prompt
from tests.test_storyboard import _frames, _with_breakdown


def _mom(editor, db, setup):  # noqa: F811
    mom = editor.post(
        "/library/character", json={"name": "Mom", "image_file_ids": [upload(editor)]}
    ).json()["id"]
    with_sheet(db, mom)
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": [mom]})
    return mom


def test_a_frame_is_softened_by_itself_and_with_soften_it(app, db, editor, setup):  # noqa: F811
    mom = _mom(editor, db, setup)
    _with_breakdown(app, db, editor, setup)
    url = f"/projects/{setup['project']}/storyboard"
    editor.post(url, json={})
    made = _frames(f"char:{mom}", f"screen:{setup['screen']}")
    made["frames"][0]["prompt"] = "Mom from image 1 in leggings, wallet in her lap."
    _run(app, db, FakeClaude(made))
    (frame,) = editor.get(url).json()
    assert frame["prompt"] == "Mom from image 1 in workout pants, wallet in her knees."
    assert frame["softened"]["before"] == made["frames"][0]["prompt"]
    assert not [p for p in frame["problems"] if "refuse" in p]

    row = db.get(StoryboardFrame, frame["id"])
    row.prompt, row.change = "Close-up: Blood on the thighs.", None  # an editor wrote it
    db.commit()
    jobs = db.query(Job).count()
    out = editor.post(f"{url}/frames/{row.id}/soften").json()
    assert (out["before"], out["after"]) == ("Close-up: Blood on the thighs.",
                                             "Close-up: Red on the legs.")  # fmt: skip
    assert out["frame"]["change"]["after"] == out["after"]
    assert not [p for p in out["frame"]["problems"] if "refuse" in p]
    assert db.query(Job).count() == jobs  # free: no model call, nothing drawn
    again = editor.post(f"{url}/frames/{row.id}/soften")
    assert again.status_code == 409 and "nothing" in again.json()["detail"]


def _clip(db, setup, prompt, seconds=5, mom=None):  # noqa: F811
    bd = db.query(BreakdownVersion).filter_by(project_id=setup["project"]).one()
    refs = _answer(mom, setup["screen"], prompt)["clips"][0]["references"]
    row = ProjectClip(project_id=setup["project"], breakdown_id=bd.id, clip_id="c1",
                      seconds=seconds, prompt=prompt, references=refs, problems=["x"])  # fmt: skip
    db.add(row)
    db.commit()
    return row


def test_fix_this_clips_prompt_puts_its_shape_right_in_code(app, db, editor, setup):  # noqa: F811
    mom = _mom(editor, db, setup)
    _with_breakdown(app, db, editor, setup)
    no_keep = "\n".join(x for x in _prompt().splitlines() if not x.startswith("Keep: "))
    row = _clip(db, setup, no_keep, seconds=4, mom=mom)  # no Keep line, 4 s of 5
    jobs = db.query(Job).count()
    out = editor.post(f"/projects/{setup['project']}/clips/{row.id}/fix").json()
    assert out["fixed"] is True, out
    assert out["clip"]["seconds"] == 5
    assert "Keep: Mom as in [Image1], the same look in every shot." in out["after"]
    assert out["after"].splitlines()[-2].startswith("Keep: ")
    assert out["clip"]["change"]["before"] == no_keep
    assert db.query(Job).count() == jobs  # no model call
    again = editor.post(f"/projects/{setup['project']}/clips/{row.id}/fix")
    assert again.status_code == 409


def test_what_code_cant_fix_claude_rewrites_free(app, db, owner, editor, setup):  # noqa: F811
    from app.models.accounts import User

    mom = _mom(editor, db, setup)
    _with_breakdown(app, db, editor, setup)
    wrong = _prompt().replace("where is all your money", "where is your money")
    row = _clip(db, setup, wrong, mom=mom)
    ed = db.query(User).filter_by(email=editor.get("/auth/me").json()["email"]).one()
    limits = owner.get("/credits/limits").json()
    owner.put("/credits/limits", json={**limits, "weekly_quick_clip_credits": 0})  # past it
    out = editor.post(f"/projects/{setup['project']}/clips/{row.id}/fix")
    assert out.status_code == 200, out.text
    assert out.json()["fixed"] is None and out.json()["job"]["credits"] == 0  # never refused
    job = db.get(Job, out.json()["job"]["id"])
    assert job.input["clip_ids"] == ["c1"] and "word for word" in job.input["prompt"]
    _run(app, db, FakeClaude(_answer(mom, setup["screen"], _prompt())))
    db.expire_all()
    fixed = db.get(ProjectClip, row.id)
    assert fixed.prompt == _prompt() and fixed.change["before"] == wrong
    assert db.get(Job, job.id).credits == 0 and ed.id == job.created_by_id  # free to them


def test_the_free_claude_fix_runs_once_per_prompt(app, db, editor, setup):  # noqa: F811
    """Reed, 2026-10-27 (spec #530): one free rewrite per clip per prompt version, one in
    flight at a time; a second press after it answers "We couldn't fix this one
    automatically."; a manual edit makes it free again, its Undo doesn't."""
    mom = _mom(editor, db, setup)
    _with_breakdown(app, db, editor, setup)
    wrong = _prompt().replace("where is all your money", "where is your money")
    row = _clip(db, setup, wrong, mom=mom)
    url = f"/projects/{setup['project']}/clips/{row.id}"

    def fixes():
        return [j for j in db.query(Job).all() if j.input.get("fix")]

    first = editor.post(f"{url}/fix").json()
    second = editor.post(f"{url}/fix").json()  # while it's on its way: the same job
    assert first["job"]["id"] == second["job"]["id"] and len(fixes()) == 1
    _run(app, db, FakeClaude(_answer(mom, setup["screen"], wrong)))  # Claude can't clear it
    db.expire_all()
    shown = editor.get(f"/projects/{setup['project']}/clips").json()[0]
    assert shown["free_fix_used"] is True
    third = editor.post(f"{url}/fix")
    assert third.status_code == 409
    assert third.json()["detail"] == "We couldn't fix this one automatically."
    assert len(fixes()) == 1  # three presses, one Claude call

    body = {"prompt": wrong, "references": shown["references"]}  # its Undo: the same prompt
    assert editor.put(url, json=body).json()["free_fix_used"] is True
    edited = wrong.replace("Close-up, push in.", "Close-up.")  # the editor's own change
    assert editor.put(url, json={**body, "prompt": edited}).json()["free_fix_used"] is False
    assert editor.post(f"{url}/fix").json()["job"]["id"] != first["job"]["id"]
    assert len(fixes()) == 2


def test_a_deleted_first_frame_tag_comes_back_whole():
    # QA-2: only "[Image1]" was deleted; the fix put the sentence in front and left the half.
    from app.clip_prompts import repair_shape
    from app.prompts.schemas import Breakdown, ClipPrompt, Reference
    from tests.test_breakdown import BREAKDOWN

    prompt = _prompt().replace(
        'References: [Image1] is Mom. [Image2] is the fomo "Buy" screen.',
        "References: is the first frame. [Image2] is Mom.",
    )
    refs = [Reference(kind="image", id="frame:c1", role="first frame"),
            Reference(kind="image", id="char:1", role="Mom")]  # fmt: skip
    fixed = repair_shape(ClipPrompt(clip_id="c1", seconds=5, prompt=prompt, references=refs),
                         Breakdown.model_validate(BREAKDOWN))  # fmt: skip
    line = next(x for x in fixed.prompt.splitlines() if x.startswith("References: "))
    assert line == "References: [Image1] is the first frame. [Image2] is Mom."


def _overlapping() -> str:
    """Mary's c4 (2026-10-27): a shot starting before the one before ends, and a shot with no
    line that doesn't say no one speaks."""
    lines = _prompt().splitlines()
    lines.insert(7, "Shot 2 | 1-2 s. Wide. Nate stares at his phone.")
    return "\n".join(lines).replace("Shot 2 | 2–5 s.", "Shot 3 | 2–5 s.")


def test_shot_times_and_no_one_speaks_are_repaired_free_on_save_and_open(app, db, editor, setup):  # noqa: E501, F811
    mom = _mom(editor, db, setup)
    _with_breakdown(app, db, editor, setup)
    editor.post(f"/projects/{setup['project']}/clips/prompts")
    _run(app, db, FakeClaude(_answer(mom, setup["screen"], _overlapping())))  # saved: repaired
    db.expire_all()
    saved = db.query(ProjectClip).one()
    assert "Shot 2 | 2-3 s. Wide. Nate stares at his phone. No one speaks." in saved.prompt
    assert "Shot 3 | 3-5 s." in saved.prompt and saved.problems == []

    fixed = saved.prompt
    saved.prompt, saved.problems, saved.free_fix_used = _overlapping(), ["x"], True
    db.commit()  # a clip saved before this repair existed: put right when Clips opens
    (shown,) = editor.get(f"/projects/{setup['project']}/clips").json()
    assert shown["prompt"] == fixed  # the same repair as on save
    assert shown["problems"] == [] and shown["free_fix_used"] is True  # never handed back


def test_a_free_fix_that_fails_is_not_free_again(app, db, editor, setup):  # noqa: F811
    """QA on #605: a failed free fix stays used (once per prompt version), then it's priced."""
    import httpx2 as httpx

    from tests.helpers import claude_stream

    mom = _mom(editor, db, setup)
    _with_breakdown(app, db, editor, setup)
    wrong = _prompt().replace("where is all your money", "where is your money")
    row = _clip(db, setup, wrong, mom=mom)
    url = f"/projects/{setup['project']}/clips/{row.id}"
    job = editor.post(f"{url}/fix").json()["job"]

    def cut_off(request):
        body = claude_stream('{"clips": [{"clip_id": "c1", "pro', "max_tokens")
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    _run(app, db, cut_off)
    db.expire_all()
    assert db.get(Job, job["id"]).status == "failed"
    assert editor.get(f"/projects/{setup['project']}/clips").json()[0]["free_fix_used"] is True
    assert editor.post(f"{url}/fix").json()["detail"] == "We couldn't fix this one automatically."
