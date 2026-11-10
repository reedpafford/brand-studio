"""Session 35's critique of videos 233 and 226 (v6-quality): the director's prompts, the takes'
own sound, the costume the story calls for, open notes before takes, a switch back to an
earlier take, a speaker with no sheet, and 226's cut that stayed out of date. Stand-ins only."""

import json

import pytest

from app import clip_prompts
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from tests.conftest import saved, upload
from tests.test_change_notes import _frame
from tests.test_enhance import setup  # noqa: F401 - fixture

pytestmark = pytest.mark.xdist_group(__name__)  # its delivered video is made once (saved)


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

    app.state.settings.fake_providers = True  # as _made sets it, for the copies too

    def make():
        pid = _made(app, owner, editor, db)
        editor.post(f"/projects/{pid}/director")
        _run(app, db)
        assert editor.get(f"/projects/{pid}/director").json()["status"] == "delivered"
        return pid

    return db.get(Project, saved(app, db, __name__, make, owner, editor))  # made once, copied


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
    for other in rows[1:]:  # they have their takes: only this one is a first take
        assert other.picked_take_id
    held = _tool(app, db, project, tool="make_take", clip_id="", note="")
    assert held == (f"The prompt of clip {row.clip_id.removeprefix('c')} still shows what a "
                    "note takes away (Note 1): rewriting first, all at once; make_take with no "
                    "clip_id makes the takes once they're written.")  # fmt: skip
    rewrite = db.query(Job).order_by(Job.id.desc()).first()  # its writer reads the notes
    assert rewrite.input["step"] == "clip_prompts" and rewrite.input["clip_ids"] == [row.clip_id]
    rewrite.status = "failed"  # say it never ran: a first take named with a note rewrites it
    db.commit()
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


def test_someone_who_speaks_with_their_sheet_in_no_shot_is_never_made(app, db, owner, editor):
    """Video 233: Maya was in no shot's `character_ids`, so each clip's first frame made its
    own Maya, three faces in 17 s. A clip where one of the video's characters speaks on camera
    while their sheet is in no shot of the breakdown is refused before any charge. QA on #1410:
    a line over an insert (the bowl, a hand, the back of a head) whose speaker is in another
    shot goes ahead, and so does a line the script labels "(O.S.)"."""
    import pytest
    from fastapi import HTTPException

    from app.clip_takes import NO_SHEET, take_input
    from app.models.breakdowns import BreakdownVersion
    from app.routes.scripts import latest

    project = _delivered(app, owner, editor, db)
    row = db.query(ProjectClip).filter_by(project_id=project.id).first()
    bd = db.get(BreakdownVersion, row.breakdown_id)
    was = bd.data
    said = {"Mom": [2], "Nate": [3]}  # each line's own script line: "MOM: …", "NATE: …"

    def shots(keep: bool) -> dict:  # Nate's own line over an insert: his shot lists nobody
        return {**was, "scenes": [{**sc, "shots": [
            {**s, "script_lines": said[s["speaker"]],
             "character_ids": s["character_ids"] if keep and s["speaker"] == "Mom" else []}
            for s in sc["shots"]]} for sc in was["scenes"]]}  # fmt: skip

    bd.data = shots(keep=True)  # Nate is in Mom's shot: his sheet reaches the clip
    db.commit()
    assert take_input(db, project, row)["step"] == "clip_take"
    bd.data = shots(keep=False)  # in no shot at all: 233
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
    assert "a segment of its own" in clip
    for text in (plan, clip):  # a held deadpan or comic button stays the style's (QA on #1410)
        assert "never a frozen frame; a held deadpan or comic button where the style" in text
        assert "never a still hold" not in text and "has to show something new" not in text
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
        "rewritten first, all at once",
    ):
        assert said in director, said


QA_NOTES = ("No music, please.", "No background music.", "no narration",
            "No one else in the kitchen", "No voices over the end", "No subtitles.")  # fmt: skip


def test_a_note_about_the_sound_or_the_fixed_words_never_reads_as_taking_from_the_picture():
    """QA on #1410: every wordless prompt says "no one speaks (no voices, narration or
    dialogue)… No music, background music, BGM, score… No subtitles", so notes like "No music,
    please." matched it. Only the lines that say what's seen count."""
    from app.clip_takes import contradicts

    quiet = ("Audio: no one speaks (no voices, narration or dialogue), only wind. No music, "
             "background music, BGM, score, instrumental, melody, synth effects, ambient pad, "
             "drone, swelling tone or stinger. No subtitles.")  # fmt: skip
    prompt = "\n".join([
        quiet, "References: [Image1] is the first frame. [Image2] is Theo.",
        "Language: every spoken line is in American English.",
        "Summary: Theo stands alone in the kitchen.", "Setting: A dim kitchen at night.",
        "Shot 1 | 0-2 s. Close-up, static. The phone lights up in Theo's hand. No one speaks.",
        "Keep: Theo as in [Image2]; one of each.", quiet])  # fmt: skip
    for note in QA_NOTES:
        assert not contradicts(prompt, note), note
    assert contradicts(prompt, "No phone: his hands hang empty.")  # what the picture shows


def test_qa_notes_hold_no_first_take_and_rewrite_no_redo(app, db, owner, editor, monkeypatch):
    """QA on #1410, both paths: a run's sound notes never hold a batch of first takes, and a
    named take with one is made, never rewritten first (a first take, or #1405's A7 redo)."""
    from types import SimpleNamespace

    from app import director

    project = _delivered(app, owner, editor, db)
    rows = db.query(ProjectClip).filter_by(project_id=project.id).order_by(ProjectClip.id).all()
    project.director_chat = [*(project.director_chat or []),
                             *({"text": n, "run": "r1"} for n in QA_NOTES)]  # fmt: skip
    going = SimpleNamespace(input={director.RUN: {"id": "r1"}})
    monkeypatch.setattr(director, "active", lambda db, project: going)
    db.commit()
    assert all("against_notes" not in c for c in director.video_state(db, project)["clips"])
    redo = _tool(app, db, project, tool="make_take", clip_id=rows[0].clip_id,
                 note="No music, please.")  # fmt: skip
    assert redo.startswith("Making 1 take.") and "rewritten" not in redo  # A7 stays out
    assert not db.query(Job).filter(Job.input["step"].as_string() == "change").count()


def test_an_own_sound_takes_free_words_check_listens_for_any_voice(
    app, db, owner, editor, monkeypatch
):
    """QA on #1410: a dialogue take made with its own sound and no line got no words check, so
    a stray voice went unheard. It's listened to as a silent take is: any voice is a finding,
    offered to the director's `mute`."""
    from app import take_words

    project = _delivered(app, owner, editor, db)
    monkeypatch.setattr(take_words.item_checks, "on", lambda: True)  # the checks, as live
    row = db.query(ProjectClip).filter_by(project_id=project.id).first()
    take = db.get(ClipTake, row.picked_take_id)
    job = db.get(Job, take.job_id)
    job.input = {**job.input, "own_sound": True}
    db.commit()
    listen = take_words.queue(db, job, take.id, take.file_id, [], take.prompt or "")
    assert listen is not None and listen.input["silent"] is True and listen.input["lines"] == []
    heard = [{"text": "Hey, over here!", "start": 1.0, "end": 1.6, "words": []}]
    (found,) = take_words.voices(heard, "dialogue")
    assert found["kind"] == "voiced" and found["change_note"] == take_words.NO_LINE


def test_what_people_read_never_cites_who_decided_it():
    """Live UGC run (video 240): the treatment said "fits Reed's positive-only direction".
    Every step is told to say a choice in its own words. In code, only a decision citation in
    brackets ("(Reed, 6 Nov: …)") comes out, and only of what people read: never a tool's
    arguments, and never when the video's script, brand or a look names a Reed (QA on #1410:
    "Keep the Reed logo sharp", "Reed Diffuser", "Reed beds", a look named Reed, "REED: Hi."
    all come through unchanged)."""
    from app import prompts
    from app.advice import names_reed, uncited

    move = {"tool": "outfit", "look": {"name": "Reed", "description": "Reed Diffuser apron"},
            "note": "Keep the Reed logo sharp.",
            "why": "b2: calm, no music under the reeds (Reed, 6 Nov: positive only).",
            "made": "Reed beds sway behind her."}  # fmt: skip
    said = uncited(move, "move", named=False)
    assert said["why"] == "b2: calm, no music under the reeds."
    assert {k: v for k, v in said.items() if k != "why"} == {
        k: v for k, v in move.items() if k != "why"}  # its arguments, as written  # fmt: skip
    assert uncited(move, "move", named=True) == move  # a Reed in the video: nothing changes
    for text in ("Keep the Reed logo sharp", "Reed Diffuser", "Reed beds", "Reed's turn"):
        assert uncited({"why": text}, "move", named=False) == {"why": text}  # no citation
    beat = {"id": "b1", "purpose": "hook", "picture": "Her face lights up (Reed, 2026-10-27)."}
    assert uncited(beat, "beat", named=False)["picture"] == "Her face lights up."
    assert names_reed("REED: Hi.") and names_reed("", "Reed Diffuser") and names_reed("Reed")
    assert not names_reed("Nate: Hi.", "fomo", "char:3 | character | Mia")
    words = "never who decided it or where it's written"
    assert words in prompts.system("treatment") and words in prompts.system("director")
