"""Clip pictures attached in code (Reed, 2026-10-26; the clip twin of frames' sheets): every
character in a clip's shots gets their approved sheet, in the order they first appear, after
the first frame and within the video model's limit; every [ImageN] follows its picture. Saved
clips are repaired for free, and a locked look never reads as not approved."""

from app import clip_prompts
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot, ScriptDraft
from app.prompts.schemas import Breakdown, ClipPrompt, Reference
from app.seed import repair_clips
from tests.conftest import upload
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture
from tests.test_frame_sheets import _people

AUDIO = "Audio: kitchen hum, no music."


def _prompt(refs: str, keep: str) -> str:
    return "\n".join(
        [
            AUDIO,
            f"References: {refs}",
            "Summary: Mom finds the empty wallet; Nate is proud he bought the dip.",
            'Shot 1 | 0–2 s. Close-up. Mom (sharp): "Nate, where is all your money?"',
            'Shot 2 | 2–5 s. Close-up. Nate (proud): "I bought the dip." Shows [Image2].',
            f"Keep: {keep}",
            AUDIO,
        ]
    )


def _clip(screen: str) -> ClipPrompt:
    """The AI attached the first frame and the screen, and forgot both people."""
    refs = [Reference(kind="image", id="frame:c1", role="storyboard frame"),
            Reference(kind="image", id=screen, role="fomo Buy screen")]  # fmt: skip
    prompt = _prompt(
        "[Image1] is the first frame. [Image2] is the fomo screen.", "the screen as [Image2]."
    )
    return ClipPrompt(clip_id="c1", seconds=5, references=refs, prompt=prompt)


def test_a_clip_gets_its_peoples_sheets_after_the_first_frame(app, db, editor, setup):  # noqa: F811
    row, nate, mom = _people(app, db, editor, setup)
    project, bd = db.get(Project, setup["project"]), Breakdown.model_validate(row.data)
    screen = f"screen:{setup['screen']}"
    done = clip_prompts.with_cast(db, project, _clip(screen), bd)
    assert [r.id for r in done.references] == ["frame:c1", mom, nate, screen]
    assert done.prompt == _prompt(  # the screen follows its picture; the people are named
        "[Image1] is the first frame. [Image4] is the fomo screen. [Image2] is Mom."
        " [Image3] is Nate.",
        "the screen as [Image4]. Mom as in [Image2], the same look as on their sheet."
        " Nate as in [Image3], the same look as on their sheet.",
    ).replace("Shows [Image2]", "Shows [Image4]")
    assert clip_prompts.with_cast(db, project, done, bd) == done  # nothing changes again
    problems = clip_prompts.clip_problems(db, project, bd, done)
    assert not [p for p in problems if "attached in the order" in p or "sheet isn't" in p]
    assert not [p for p in problems if "approved look" in p]


def test_over_the_video_models_limit_the_nearest_are_kept(app, db, editor, setup, monkeypatch):  # noqa: F811
    row, nate, mom = _people(app, db, editor, setup)
    project, bd = db.get(Project, setup["project"]), Breakdown.model_validate(row.data)
    three = clip_prompts.video_model().model_copy(update={"max_reference_images": 3})
    monkeypatch.setattr(clip_prompts, "video_model", lambda: three)
    screen = f"screen:{setup['screen']}"
    done = clip_prompts.with_cast(db, project, _clip(screen), bd)
    assert [r.id for r in done.references] == ["frame:c1", mom, screen]  # Mom speaks
    assert "Shows [Image3]" in done.prompt and "Nate as in" not in done.prompt
    attached = _clip(screen).model_copy(  # an editor's own pick is never dropped
        update={
            "references": [*_clip(screen).references, Reference(kind="image", id=nate, role="Nate")]
        }  # fmt: skip
    )
    kept = clip_prompts.with_cast(db, project, attached, bd, trim=False)
    assert [r.id for r in kept.references] == ["frame:c1", nate, screen]  # no room for Mom


def test_a_look_with_no_approved_sheet_is_named(app, db, editor, setup):  # noqa: F811
    row, nate, mom = _people(app, db, editor, setup)
    project, bd = db.get(Project, setup["project"]), Breakdown.model_validate(row.data)
    db.get(LibraryItem, int(nate[5:])).sheet_approved = False
    db.commit()
    done = clip_prompts.with_cast(db, project, _clip(f"screen:{setup['screen']}"), bd)
    assert nate not in [r.id for r in done.references]
    problems = clip_prompts.clip_problems(db, project, bd, done)
    assert "Nate has no approved look yet. Approve one in Assets." in problems
    assert not [p for p in problems if "Mom" in p]


def test_a_locked_look_is_never_read_as_not_approved(app, db, editor, setup):  # noqa: F811
    """Reed's "Mogging BF": a role locked to a look whose newer sheet waits for approval
    uses the sheet it was locked with, in clips and frames."""
    from app import storyboard
    from app.prompts.schemas import Frame

    row, nate, mom = _people(app, db, editor, setup)
    fomo = editor.get("/brands").json()[0]["id"]
    script = editor.post("/scripts", json={"brand_id": fomo, "title": "S", "text": "A: hi"})
    newer = upload(editor)
    project = db.get(Project, setup["project"])
    project.script_draft_id = (
        db.query(ScriptDraft).filter_by(script_id=script.json()["id"]).one().id
    )
    bf = db.get(LibraryItem, int(nate[5:]))
    slot = ScriptCastSlot(script_id=script.json()["id"], role="Mogging BF",
                          library_item_id=bf.id, sheet_file_id=bf.sheet_file_id)  # fmt: skip
    db.add(slot)
    project.cast_ids = [int(mom[5:])]  # the locked look plays the role from the script
    bf.sheet_file_id, bf.sheet_approved = newer, False  # a newer sheet, waiting
    data = row.data
    shots = data["scenes"][0]["shots"]
    db.flush()
    row.data = {**data, "scenes": [{**data["scenes"][0], "shots": [
        {**shots[0], "character_ids": [f"slot:{slot.id}", mom]}, *shots[1:]]}]}  # fmt: skip
    db.commit()
    bd = Breakdown.model_validate(row.data)
    done = clip_prompts.with_cast(db, project, _clip(f"screen:{setup['screen']}"), bd)
    assert f"slot:{slot.id}" in [r.id for r in done.references]
    assert not [p for p in clip_prompts.clip_problems(db, project, bd, done) if "look" in p]
    frame = storyboard.with_cast(db, project, Frame(clip_id="c1", shot_id="1.1", prompt="x",
                                                    reference_ids=[]), bd)  # fmt: skip
    assert f"slot:{slot.id}" in frame.reference_ids
    assert storyboard.frame_problems(db, project, frame, row.id) == []


def test_saved_clips_are_repaired_for_free_once(app, db, editor, setup):  # noqa: F811
    row, nate, mom = _people(app, db, editor, setup)
    screen = f"screen:{setup['screen']}"
    old = _clip(screen)
    clip = ProjectClip(project_id=setup["project"], breakdown_id=row.id, clip_id="c1",
                       seconds=5, prompt=old.prompt, problems=["c1: char:1 isn't attached"],
                       references=[r.model_dump() for r in old.references])  # fmt: skip
    db.add(clip)
    db.commit()
    jobs = db.query(Job).count()
    said = repair_clips(db)  # the deploy step
    assert said.startswith("Gave 1 clips their characters' sheets (checked 1 on 1 videos;")
    db.refresh(clip)
    assert [r["id"] for r in clip.references] == ["frame:c1", mom, nate, screen]
    assert "Shows [Image4]" in clip.prompt
    assert not [p for p in clip.problems if "isn't attached" in p]
    assert repair_clips(db).startswith("Gave 0 clips")  # idempotent
    assert db.query(Job).count() == jobs  # no model call, nothing charged


def test_an_edit_keeps_the_peoples_sheets(app, db, editor, setup):  # noqa: F811
    row, nate, mom = _people(app, db, editor, setup)
    screen = f"screen:{setup['screen']}"
    old = _clip(screen)
    clip = ProjectClip(project_id=setup["project"], breakdown_id=row.id, clip_id="c1",
                       seconds=5, prompt=old.prompt, problems=[],
                       references=[r.model_dump() for r in old.references])  # fmt: skip
    db.add(clip)
    db.commit()
    body = {"prompt": old.prompt, "references": [r.model_dump() for r in old.references]}
    saved = editor.put(f"/projects/{setup['project']}/clips/{clip.id}", json=body)
    assert saved.status_code == 200, saved.text
    assert [r["id"] for r in saved.json()["references"]] == ["frame:c1", mom, nate, screen]


def test_the_ai_answer_is_saved_with_the_sheets(app, db, editor, setup):  # noqa: F811
    row, nate, mom = _people(app, db, editor, setup)
    editor.post(f"/projects/{setup['project']}/clips/prompts")
    answer = {"clips": [_clip(f"screen:{setup['screen']}").model_dump()]}
    _run(app, db, FakeClaude(answer))
    saved = db.query(ProjectClip).filter_by(project_id=setup["project"]).one()
    assert [r["id"] for r in saved.references][1:3] == [mom, nate]
