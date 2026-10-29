"""The main character's sheet always goes first (Reed, 2026-10-27, faces): in every frame and
clip they're in, whoever speaks, and a trim to the image model's people limit keeps them.
Main is the script's Main role, else whoever is in the most shots. Saved frames and clips
are renumbered for free on deploy."""

from app import clip_prompts, storyboard
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot, ScriptDraft
from app.prompts.schemas import Breakdown, Frame, Reference
from tests.test_clip_sheets import _clip, _prompt
from tests.test_enhance import setup  # noqa: F401, F811 - fixture
from tests.test_frame_sheets import _people


def _nate_leads(app, db, editor, setup):  # noqa: F811
    """Mom speaks first and is named first in shot 1.1; Nate is in both shots."""
    row, nate, mom = _people(app, db, editor, setup)
    data = row.data
    one, two = data["scenes"][0]["shots"][:2]
    one = {**one, "character_ids": [mom, nate], "action": "Mom waves the wallet at Nate."}
    row.data = {**data, "scenes": [{**data["scenes"][0], "shots": [
        one, {**two, "character_ids": [nate]}]}]}  # fmt: skip
    db.commit()
    return db.get(Project, setup["project"]), Breakdown.model_validate(row.data), row, nate, mom


def test_the_main_character_is_first_in_frames_and_kept_by_the_people_limit(
    app,
    db,
    editor,
    setup,  # noqa: F811
    monkeypatch,
):
    project, bd, _, nate, mom = _nate_leads(app, db, editor, setup)
    frame = Frame(clip_id="c1", shot_id="1.1", prompt="Mom in image 1.", reference_ids=[mom])
    done = storyboard.with_cast(db, project, frame, bd)
    assert done.reference_ids == [nate, mom]
    assert done.prompt.startswith("Mom in image 2.")  # each "image N" follows its picture
    one = storyboard.image_model().model_copy(update={"max_character_images": 1})
    monkeypatch.setattr(storyboard, "image_model", lambda project=None: one)
    assert storyboard.with_cast(db, project, frame, bd).reference_ids == [nate]


def test_the_scripts_main_role_leads_over_the_most_shots(app, db, editor, setup):  # noqa: F811
    project, bd, _, nate, mom = _nate_leads(app, db, editor, setup)
    script = editor.post("/scripts", json={"brand_id": editor.get("/brands").json()[0]["id"],
                                           "title": "S", "text": "MOM: hi"}).json()  # fmt: skip
    project.script_draft_id = db.query(ScriptDraft).filter_by(script_id=script["id"]).one().id
    db.add(ScriptCastSlot(script_id=script["id"], role="Mom", kind="Main",
                          library_item_id=int(mom[5:])))  # fmt: skip
    db.commit()
    assert storyboard.hero(db, project, bd, storyboard.assets(db, project)) == mom


def test_a_clip_leads_with_the_main_character_and_saved_clips_are_renumbered(
    app,
    db,
    editor,
    setup,  # noqa: F811
):
    project, bd, row, nate, mom = _nate_leads(app, db, editor, setup)
    screen = f"screen:{setup['screen']}"
    assert [r.id for r in clip_prompts.with_cast(db, project, _clip(screen), bd).references] == [
        "frame:c1", nate, mom, screen]  # fmt: skip
    # A clip saved before, with Mom's sheet ahead of Nate's.
    frame, shown = _clip(screen).references
    refs = [frame, Reference(kind="image", id=mom, role="Mom"),
            Reference(kind="image", id=nate, role="Nate"), shown]  # fmt: skip
    prompt = _prompt(
        "[Image1] is the first frame. [Image2] is Mom. [Image3] is Nate."
        " [Image4] is the fomo screen.",
        "the screen as [Image4].",
    ).replace("Shows [Image2]", "Shows [Image4]")
    old = _clip(screen).model_copy(update={"references": refs, "prompt": prompt})
    saved = [r.model_dump() for r in old.references]
    clip = ProjectClip(project_id=project.id, breakdown_id=row.id, clip_id="c1", seconds=5,
                       prompt=old.prompt, references=saved)  # fmt: skip
    db.add(clip)
    db.commit()
    jobs = db.query(Job).count()
    assert clip_prompts.repair(db, project) == 1  # as when Clips opens
    db.commit()
    db.refresh(clip)
    assert [r["id"] for r in clip.references] == ["frame:c1", nate, mom, screen]
    assert "[Image3] is Mom. [Image2] is Nate." in clip.prompt  # each tag follows its picture
    assert "Shows [Image4]" in clip.prompt
    assert clip_prompts.repair(db, project) == 0  # idempotent
    assert db.query(Job).count() == jobs  # free: no model call
