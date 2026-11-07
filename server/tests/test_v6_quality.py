"""Session 35's critique of videos 233 and 226 (v6-quality): the director's prompts, the takes'
own sound, the costume the story calls for, open notes before takes, a switch back to an
earlier take, a speaker with no sheet, and 226's cut that stayed out of date. Stand-ins only."""

import json

from app import clip_prompts
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from tests.conftest import upload
from tests.test_change_notes import _frame
from tests.test_enhance import setup  # noqa: F401 - fixture


def _job(db, project: Project, files: list[int], **more) -> Job:
    job = Job(
        workspace_id=project.workspace_id,
        created_by_id=None,
        kind="video-480p",
        provider="fake",
        project_id=project.id,
        input={"files": {"reference_images": files}},
        **{"status": "succeeded", **more},
    )
    db.add(job)
    db.flush()
    return job


def test_a_look_alike_retry_made_without_its_still_never_holds_the_cut_out_of_date(
    app,
    db,
    editor,
    setup,  # noqa: F811
):
    """Video 226: clip 2's first take was refused as a look-alike and made again on its own
    without the still (`_again_without`), as designed. Its take was then read as "made from an
    earlier still", so the cut stayed "out of date" through five remakes and the run stopped
    undelivered. The take was made for the still in use: it's current."""
    _, frame = _frame(app, db, editor, setup)
    project, video = db.get(Project, frame.project_id), upload(editor)
    sheet = video  # stands in for Mom's sheet, sent both times
    asked = _job(db, project, [frame.file_id, sheet], status="failed")  # refused: copyright
    retry = _job(db, project, [sheet], auto=True, retry_of_id=asked.id)  # without the still
    ref = {"kind": "image", "id": f"frame:{frame.clip_id}", "role": ""}
    row = ProjectClip(project_id=project.id, breakdown_id=frame.breakdown_id,
                      clip_id=frame.clip_id, seconds=5, prompt="Mom looks up.",
                      references=[ref], approved=True)  # fmt: skip
    db.add(row)
    db.flush()
    take = ClipTake(clip_id=row.id, number=1, job_id=retry.id, file_id=video)
    db.add(take)
    db.flush()
    row.picked_take_id = take.id
    db.commit()
    known = clip_prompts.assets(db, project)
    assert not clip_prompts.older_still(db, known, row)
    assert clip_prompts.older_take(db, known, row) == []

    retry.auto = False  # a person's take with no current still: an earlier still, as before
    db.commit()
    assert clip_prompts.older_still(db, clip_prompts.assets(db, project), row)


def _delivered(app, owner, editor, db) -> Project:
    """A dialogue video the stand-in director took to delivery: Mom (Mia) and Nate (Kid)."""
    from tests.test_director import _made, _run

    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    assert editor.get(f"/projects/{pid}/director").json()["status"] == "delivered"
    return db.get(Project, pid)


def _ed(db):
    from app.models.accounts import User

    return db.query(User).filter_by(email="ed@example.com").one()


def _tool(app, db, project, **decision) -> str:
    from app import director_tools

    said = director_tools.run(db, _ed(db), project, decision, app.state.storage,
                              {"id": "r1", "turn": 1, "redos": {}})  # fmt: skip
    db.commit()
    return said


def test_the_costume_the_story_calls_for_is_this_videos_outfit(app, db, owner, editor):
    """Video 226: the script put Nate in "a navy wedding suit", no outfit was set, and the clip
    prompts let his sheet's green jacket win. The director's `outfit` sets what the story
    dresses him in for this video: his cast line wears it, so the stills and every Keep line
    do; his sheet still sets the face. A person's outfit stays theirs; a locked cast is kept."""
    from app.enhance import wears

    project = _delivered(app, owner, editor, db)
    kid = project.cast_ids[-1]
    said = _tool(
        app,
        db,
        project,
        tool="outfit",
        look={"name": "Nate", "description": "navy wedding suit, white boutonniere"},
    )
    assert said == ("Nate wears navy wedding suit, white boutonniere in this video; their sheet "
                    "still sets the face.")  # fmt: skip  # Kid plays Nate: either name
    db.refresh(project)
    assert project.outfits == {f"char:{kid}": "navy wedding suit, white boutonniere"}
    assert wears(project, kid) == "wears: navy wedding suit, white boutonniere (this video)"
    again = _tool(app, db, project, tool="outfit", look={"name": "Nate", "description": "a tux"})
    assert again.startswith("Refused: Nate already wears navy wedding suit")  # stays as set
    assert _tool(app, db, project, tool="outfit", look={"name": "Zed", "description": "a tux"}
                 ) == "Refused: there's no Zed with a look in this video yet."  # fmt: skip
    project.locks = {"cast": True}
    db.commit()
    locked = _tool(app, db, project, tool="outfit", look={"name": "Mom", "description": "scrubs"})
    assert locked == "Refused: the cast is locked for this video."


def test_a_wordless_take_with_its_own_sound_is_never_given_sound_effects_too(
    app, db, owner, editor
):
    """Video 226's silent stretch: a wordless story clip is made with its own sound now
    (`own_sound`). The director's add_sound (#1404's MMAudio, paid) leaves that clip alone, so
    one clip never gets both; a trim of it never waits on a words check, since it says no
    line; the director reads `own_sound` on the clip."""
    from app import cut_edits, take_sound
    from app.director import video_state

    project = _delivered(app, owner, editor, db)
    row = db.query(ProjectClip).filter_by(project_id=project.id).first()
    take = db.get(ClipTake, row.picked_take_id)
    job = db.get(Job, take.job_id)
    job.input = {
        **job.input,
        "own_sound": True,
        "input": {**(job.input.get("input") or {}), "generate_audio": True},
    }
    db.commit()
    assert not cut_edits._speaks(db, take)  # no line: a trim never waits on its words
    said = _tool(app, db, project, tool="add_sound", clip_id=row.clip_id, note="House: whooshes")
    assert said == take_sound.OWN.format(row.clip_id.removeprefix("c"))
    assert not db.query(Job).filter(Job.input["step"].as_string() == take_sound.STEP).count()
    clip = next(c for c in video_state(db, project)["clips"] if c["clip_id"] == row.clip_id)
    assert clip["own_sound"] is True


def test_a_runs_notes_reach_the_writing_steps_and_are_checked_before_first_takes(
    app, db, owner, editor, monkeypatch
):
    """Video 226: Reed's note said "no phone", but the director's own clip 4 prompt still asked
    for the phone, and a paid take raised it. The run's notes now go to every step that writes
    the pictures (<notes>), each clip whose prompt shows what a note takes away says so
    (`against_notes`), first takes of every clip hold that one back, and a first take named
    with a note that takes it out rewrites the prompt first (as #1405's A7 does for a redo)."""
    from types import SimpleNamespace

    from app import director
    from app.models.clips import ClipTake as Take

    project = _delivered(app, owner, editor, db)
    rows = db.query(ProjectClip).filter_by(project_id=project.id).order_by(ProjectClip.id).all()
    project.director_chat = [*(project.director_chat or []),
                             {"text": "End on him alone, no phone.", "run": "r1"}]  # fmt: skip
    going = SimpleNamespace(input={director.RUN: {"id": "r1"}})
    monkeypatch.setattr(director, "active", lambda db, project: going)
    row = rows[0]
    row.prompt = row.prompt.replace("Keep:", "Shot 9 | The phone lights up in his hand.\nKeep:")
    db.commit()
    told = director.treatment_block(db, project)
    assert "<notes>\nNote 1: End on him alone, no phone.\n</notes>" in told
    assert "<notes>" not in director.story(db, project)  # the director reads its own <chat>
    clip = next(c for c in director.video_state(db, project)["clips"]
                if c["clip_id"] == row.clip_id)  # fmt: skip
    assert clip["against_notes"] == ["Note 1"]

    for t in db.query(Take).filter_by(clip_id=row.id).all():  # as before its first take
        db.delete(t)
    row.picked_take_id = row.file_id = None
    db.commit()
    before = db.query(Job).count()
    held = _tool(app, db, project, tool="make_take", clip_id="", note="")
    assert held.startswith("Refused: Not made yet, their prompt shows what a note takes away: "
                           f"clip {row.clip_id.removeprefix('c')} (Note 1).")  # fmt: skip
    assert db.query(Job).count() == before  # nothing made, nothing charged
    said = _tool(app, db, project, tool="make_take", clip_id=row.clip_id,
                 note="No phone: his hands hang empty.")  # fmt: skip
    assert said == (f"Rewriting clip {row.clip_id.removeprefix('c')}'s prompt with the note "
                    "first; make its take once it's written.")  # fmt: skip
    change = db.query(Job).order_by(Job.id.desc()).first()
    assert change.input["step"] == "change" and "No phone" in json.dumps(change.input)
    again = _tool(app, db, project, tool="make_take", clip_id=row.clip_id,
                  note="No phone: his hands hang empty.")  # fmt: skip
    assert not again.startswith("Rewriting")  # rewritten once: never again for the same note


def test_going_back_to_an_earlier_take_says_what_a_watch_found_on_it(app, db, owner, editor):
    """Video 233: a paid redo (take 3) fixed a dead hold, then the director went back to take 2
    for the colour of her eyes and the dead hold came back, unmentioned. A take now carries
    what any watch of a cut found while it played (`cut_watch`), and going back to it says so."""
    from app import watch_cut
    from app.director import video_state

    project = _delivered(app, owner, editor, db)
    row = db.query(ProjectClip).filter_by(project_id=project.id).first()
    was = db.get(ClipTake, row.picked_take_id)
    found = "a 5-second wordless hold and a stern frown"
    db.add(
        Job(
            workspace_id=project.workspace_id,
            created_by_id=None,
            kind="check-claude",
            provider="fake",
            project_id=project.id,
            status="succeeded",
            input={"step": watch_cut.STEP, "cut": [{"clip_id": row.clip_id, "take_id": was.id}]},
            output={"checked": [{"clip_id": row.clip_id, "says": found, "fix": "redo"}]},
        )
    )
    newer = ClipTake(clip_id=row.id, number=was.number + 1, job_id=was.job_id,
                     file_id=was.file_id)  # fmt: skip
    db.add(newer)
    db.flush()
    row.picked_take_id = newer.id  # the redo, picked
    db.commit()
    takes = next(c for c in video_state(db, project)["clips"]
                 if c["clip_id"] == row.clip_id)["takes"]  # fmt: skip
    assert found in next(t for t in takes if t["id"] == was.id)["cut_watch"]
    assert "cut_watch" not in next(t for t in takes if t["id"] == newer.id)
    said = _tool(app, db, project, tool="pick_take", clip_id=row.clip_id, take_id=was.id)
    assert (
        said.startswith(
            f"Picked take {was.number} for {row.clip_id}. It comes back with "
            "what a watch of a cut found on it: "
        )
        and f"{found}." in said
    )


def test_an_old_take_holding_the_cut_out_of_date_is_said_and_unlocks_its_redo(
    app, db, owner, editor
):
    """Video 226: the director made the cut five times, it stayed "out of date", and delivery
    was refused with no reason it could act on. The clip whose take holds it says so
    (`old_take`), delivery names it, and its redo is never refused as only a doubt."""
    from app import director
    from app.clip_prompts import OLDER_STILL

    project = _delivered(app, owner, editor, db)
    row = db.query(ProjectClip).filter_by(project_id=project.id).first()
    row.problems = [*(row.problems or []), f"{OLDER_STILL} Make another take to show it."]
    db.commit()
    clip = next(c for c in director.video_state(db, project)["clips"]
                if c["clip_id"] == row.clip_id)  # fmt: skip
    assert clip["old_take"].startswith("Its take was made from an earlier still")
    assert not director._only_a_doubt(db, project, row.clip_id, "b1: the face drifts.")
    n = row.clip_id.removeprefix("c")
    assert director.OLD_TAKE.format(c=n, why=clip["old_take"]).startswith(
        f"Refused: clip {n}'s picked take holds the cut out of date"
    )


def test_someone_who_speaks_with_no_sheet_in_the_clip_is_never_made(app, db, owner, editor):
    """Video 233: Maya's look never reached a shot (`character_ids: []`), so each clip's first
    frame made its own Maya, three faces in 17 s. A clip where one of the video's characters
    speaks on camera, and no sheet reaches it, is refused before any charge; a line the script
    labels "(O.S.)" may be heard over an empty frame and goes ahead."""
    import pytest
    from fastapi import HTTPException

    from app.clip_takes import NO_SHEET, take_input
    from app.models.breakdowns import BreakdownVersion
    from app.routes.scripts import latest

    project = _delivered(app, owner, editor, db)
    row = db.query(ProjectClip).filter_by(project_id=project.id).first()
    bd = db.get(BreakdownVersion, row.breakdown_id)
    said = {"Mom": [2], "Nate": [3]}  # each line's own script line: "MOM: …", "NATE: …"
    scenes = [{**sc, "shots": [{**s, "character_ids": [], "script_lines": said[s["speaker"]]}
                               for s in sc["shots"]]} for sc in bd.data["scenes"]]  # fmt: skip
    bd.data = {**bd.data, "scenes": scenes}
    row.references = [r for r in row.references if not r["id"].startswith("char:")]
    db.commit()
    with pytest.raises(HTTPException) as no:
        take_input(db, project, row)
    assert no.value.status_code == 409
    assert no.value.detail in (NO_SHEET.format(who="Mom"), NO_SHEET.format(who="Nate"))
    words = latest(db, project)
    words.text = words.text.replace("MOM:", "MOM (O.S.):").replace("NATE:", "NATE (O.S.):")
    db.commit()
    assert take_input(db, project, row)["step"] == "clip_take"  # heard, maybe unseen


def test_the_plan_and_the_prompts_fit_actions_to_seconds_and_make_silence_a_choice():
    """Session 35 (233): five actions in one second, eight in two, and the cause (the lamp
    switch) dropped; two wordless seconds before a line and 1.2 s holds left a 3.8 s gap. The
    guidance is judgment, sized by the style's own guide, never a fixed number."""
    from app import prompts

    plan = prompts.system("breakdown")
    assert "**What can read in a shot's seconds.**" in plan
    assert "a cause the story turns on" in plan and "its guide's own rules and pacing win" in plan
    assert "**Silence is a choice.**" in plan and "never to fill a clip to its length" in plan
    assert "as long as the reaction needs and no longer" in plan
    clip = prompts.system("clip_prompts")
    assert "Each segment carries only what its seconds can show" in clip
    assert "a segment of its own" in clip and "never a still hold" in clip
    assert 'write "only silence." where the style\'s guide wants the shot silent' in clip
    assert "its story dresses them for its scenes" in clip
    assert "**A person's notes (<notes>, when given)**" in prompts.system("breakdown")
    director = prompts.system("director")
    for said in (
        "`outfit` (free, `look`)",
        "against_notes",
        "cut_watch",
        "old_take",
        "own_sound",
        "Before a clip's first take, check its prompt against every note",
    ):
        assert said in director, said
