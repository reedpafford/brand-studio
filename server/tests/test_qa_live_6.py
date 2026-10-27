"""QA-Live 6 (video 16, live): after a cast swap the sheet sets the outfit, every montage shot
shows the hero, a note that reworks a video's own look isn't drowned by the old sheet, and a
new plan saved for the editor keeps what they kept anyway."""

import copy

from app import breakdown, cast_roles
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.prompts.schemas import Breakdown
from tests.test_breakdown import BREAKDOWN
from tests.test_unknown_cast import _look
from tests.test_video_looks import _drawn, _row, _video


def test_a_swap_drops_the_old_outfit_words_but_never_a_delivery(owner, editor, db):
    _, pid, nate = _video(owner, editor, db)
    look = db.get(LibraryItem, _look(owner, db, "Kimchi"))
    look.notes = "white shirt"
    db.commit()
    text = ('Nate (red cap, tee, chain) leans in. Nate (smug): "Nice car." '
            "Keep: Nate (red cap) as in [Image2].")  # fmt: skip
    assert cast_roles._recast(db, text, {f"slot:{nate}": f"char:{look.id}"}) == (
        'Nate leans in. Nate (smug): "Nice car." Keep: Nate as in [Image2].'
    )  # the sheet sets the outfit; the words, and how they're said, never change


def test_every_montage_shot_shows_the_hero(owner, editor, db):
    _, pid, nate = _video(owner, editor, db)
    bd = copy.deepcopy(BREAKDOWN)
    first = bd["scenes"][0]["shots"][1]
    first.update(character_ids=[f"slot:{nate}"], line=None, speaker=None, seconds=0.5)
    quick = [{**first, "id": f"1.{n}", "character_ids": []} for n in (3, 4, 5)]
    bd["scenes"][0]["shots"] += quick  # a run of quick wordless shots with nobody in them
    plan = Breakdown.model_validate(bd)
    added = breakdown.show_roles(db, db.get(Project, pid), plan, "")
    assert {k: v for k, v in added.items() if k != "1.1"} == {s: ["Nate"] for s in
                                                             ("1.3", "1.4", "1.5")}  # fmt: skip
    assert all(f"slot:{nate}" in s.character_ids for s in plan.scenes[0].shots[2:])


def test_a_note_reworking_a_videos_own_look_draws_it_fresh(owner, editor, db):
    _, pid, nate = _video(owner, editor, db)
    editor.post(f"/projects/{pid}/assets/slots/{nate}/make-look")
    look = _row(editor, pid, nate)["own_look_id"]
    _drawn(db, editor, look)
    url = f"/library/character/{look}/sheet"

    def sent(change: str) -> dict:
        assert editor.post(url, json={"change": change}).status_code == 201
        return db.query(Job).order_by(Job.id.desc()).first().input

    older = sent("Make him twenty years older.")
    assert older["files"] == {} and "twenty years older" in older["input"]["prompt"]
    assert "last sheet is attached" not in older["input"]["prompt"]
    _drawn(db, editor, look)
    jacket = sent("A brighter jacket.")  # an outfit change keeps the face from the sheet
    assert len(jacket["files"]["image_input"]) == 1


def test_a_plan_saved_for_the_editor_keeps_what_they_kept_anyway(owner, editor, db):
    """Item 8: a swap or a made look saves the plan again through one path, which keeps it."""
    from app.models.accounts import User
    from app.routes.project_assets import _resave

    _, pid, _ = _video(owner, editor, db)
    row = db.query(BreakdownVersion).filter_by(project_id=pid).one()
    row.problems = [*row.problems, "Advice: shot 1.1: kept"]
    row.kept = ["Advice: shot 1.1: kept"]
    db.commit()
    project, user = db.get(Project, pid), db.get(User, row.created_by_id or 1)
    _resave(db, user, project, row, row.data)
    new = db.query(BreakdownVersion).order_by(BreakdownVersion.id.desc()).first()
    assert new.id != row.id and new.kept == [p for p in row.kept if p in new.problems]
