"""Video 345 (79 clips): one new take in half an hour. The brief's "no phone screen" and two
notes about clip 10 held every first take, so the director made them one clip a turn, and
each turn's freshly worded note rewrote clip 13's prompt again (three times). Stand-ins only."""

import pytest
from sqlalchemy import func

from app import clip_prompts, director
from app.db import utcnow
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from tests.test_v6_quality import _delivered, _tool

pytestmark = pytest.mark.xdist_group("tests.test_v6_quality")  # its delivered video, made once

BRIEF = "One scene: she walks her street filming herself. No phone screen or call UI ever shows."


def _first_takes(app, db, owner, editor, notes: list[tuple[str, bool]], clips: int = 6):
    """The delivered video grown to `clips` clips (copies of its clip), none with a take, every
    prompt showing a man and the phone (as the camera), and the run's notes: (text, whether it
    came after the prompts were written); {n} is the first clip's number. Then its clips, and
    the last job before the test's own."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.breakdowns import BreakdownVersion

    project = _delivered(app, owner, editor, db)
    (one,) = db.query(ProjectClip).filter_by(project_id=project.id).all()
    bd = db.get(BreakdownVersion, one.breakdown_id)
    planned = next(c for c in bd.data["clips"] if c["id"] == one.clip_id)
    more = [{**planned, "id": f"c{n}"} for n in range(2, clips + 1)]
    bd.data = {**bd.data, "clips": [*bd.data["clips"], *more]}
    flag_modified(bd, "data")
    db.query(ClipTake).filter_by(clip_id=one.id).delete()
    one.picked_take_id = one.file_id = None
    shown = "Shot 9 | A man walks past; the phone is the camera, never seen."
    one.prompt = one.prompt.replace("Keep:", f"{shown}\nKeep:")
    for n in range(2, clips + 1):
        db.add(ProjectClip(project_id=project.id, breakdown_id=bd.id, job_id=one.job_id,
                           clip_id=f"c{n}", seconds=one.seconds, prompt=one.prompt,
                           references=one.references, approved=True))  # fmt: skip
    db.flush()
    late, early = utcnow().isoformat(), "2000-01-01T00:00:00"
    project.director_chat = [*(project.director_chat or []), *(
        {"text": t.format(n=one.clip_id.removeprefix("c")), "at": late if after else early,
         "run": "r1"} for t, after in notes)]  # fmt: skip
    db.commit()
    rows = db.query(ProjectClip).filter_by(project_id=project.id).order_by(ProjectClip.id).all()
    return project, rows, db.query(func.max(Job.id)).scalar()


def _jobs(db, project, step: str, since: int) -> list[Job]:
    return [j for j in db.query(Job).filter(Job.project_id == project.id, Job.id > since)
            .order_by(Job.id) if j.input.get("step") == step]  # fmt: skip


def _going(monkeypatch):
    """The run "r1" is the going one (whose notes video_state reads)."""
    from types import SimpleNamespace

    going = SimpleNamespace(input={director.RUN: {"id": "r1"}})
    monkeypatch.setattr(director, "active", lambda db, project: going)


def test_a_read_brief_and_a_one_clip_note_hold_only_that_clip(app, db, owner, editor,
                                                              monkeypatch):  # fmt: skip
    """The brief came before the clip prompts call wrote the prompts (it was given the notes):
    it holds none. A later note naming one clip holds that clip alone, whose prompt is
    rewritten (one call, every held clip a part) while every other first take goes out in the
    same turn; once that call has written it, the next make_take makes it, never rewritten
    twice."""
    project, rows, since = _first_takes(app, db, owner, editor, [
        (BRIEF, False), ("Clip {n}: no man anywhere.", True)])  # fmt: skip
    _going(monkeypatch)
    clip = rows[0]
    n = clip.clip_id.removeprefix("c")
    state = {c["clip_id"]: c for c in director.video_state(db, project)["clips"]}
    assert state[clip.clip_id]["against_notes"] == ["Note 2"]
    assert not any("against_notes" in state[r.clip_id] for r in rows[1:])
    said = _tool(app, db, project, tool="make_take", clip_id="", note="")
    assert said == (f"Making {len(rows) - 1} takes. The prompt of clip {n} still shows what a "
                    "note takes away (Note 2): rewriting first, all at once; make_take with no "
                    "clip_id makes the takes once they're written.")  # fmt: skip
    assert len(_jobs(db, project, "clip_take", since)) == len(rows) - 1
    (rewrite,) = _jobs(db, project, "clip_prompts", since)
    assert rewrite.input["clip_ids"] == [clip.clip_id]

    again = _tool(app, db, project, tool="make_take", clip_id="", note="")
    assert again == (f"Refused: The prompt of clip {n} is being rewritten; make_take with no "
                     "clip_id makes the takes once they're written. 5 first takes are being "
                     "made already.")  # fmt: skip

    rewrite.status = "succeeded"  # written, still showing the man: it read the note all the same
    clip.job_id = rewrite.id
    clip_prompts.log_prompt(db, clip, None, rewrite.id)
    db.commit()
    state = {c["clip_id"]: c for c in director.video_state(db, project)["clips"]}
    assert "against_notes" not in state[clip.clip_id]
    assert _tool(app, db, project, tool="make_take", clip_id="", note="") == "Making 1 take."
    assert len(_jobs(db, project, "clip_prompts", since)) == 1  # rewritten once


def test_a_notes_clause_that_names_no_clip_is_about_every_clip_and_rewritten_once(
    app, db, owner, editor
):
    """QA on #1533: "No man anywhere in the video; clip 1 ends on her face." is about every
    clip but for its last clause. A hand edit after the note was never given it, so that
    prompt waits too; and a rewrite that failed is named, never queued every turn."""
    project, rows, since = _first_takes(app, db, owner, editor, [
        ("No man anywhere in the video; clip {n} ends on her face.", False)])  # fmt: skip
    edited = rows[1]  # edited by hand since the note: never given the notes
    edited.prompt += " "
    clip_prompts.log_prompt(db, edited, None)
    db.commit()
    said = _tool(app, db, project, tool="make_take", clip_id="", note="")
    assert said == (f"Making {len(rows) - 1} takes. The prompt of clip "
                    f"{edited.clip_id.removeprefix('c')} still shows what a note takes away "
                    "(Note 1): rewriting first, all at once; make_take with no clip_id makes "
                    "the takes once they're written.")  # fmt: skip
    (rewrite,) = _jobs(db, project, "clip_prompts", since)
    rewrite.status = "failed"
    db.commit()
    again = _tool(app, db, project, tool="make_take", clip_id="", note="")
    assert again.startswith(f"Refused: The prompt of clip {edited.clip_id.removeprefix('c')} "
                            "still shows what a note takes away after one rewrite for it: make "
                            "each of those takes alone")  # fmt: skip
    assert len(_jobs(db, project, "clip_prompts", since)) == 1


def test_a_clause_naming_no_clip_holds_every_prompt_not_written_since(app, db, owner, editor):
    """QA on #1533: the general clause of a note that also names clip 1 holds every clip
    whose prompt was written before it came, all rewritten in one call."""
    project, rows, since = _first_takes(app, db, owner, editor, [
        ("No man anywhere in the video; clip {n} ends on her face.", True)], clips=3)  # fmt: skip
    said = _tool(app, db, project, tool="make_take", clip_id="", note="")
    assert said == ("The prompts of clips 1, 2 and 3 still show what a note takes away (Note "
                    "1): rewriting first, all at once; make_take with no clip_id makes the "
                    "takes once they're written.")  # fmt: skip
    (rewrite,) = _jobs(db, project, "clip_prompts", since)
    assert rewrite.input["clip_ids"] == [r.clip_id for r in rows]


def test_a_first_take_rewritten_for_its_note_is_made_next_whatever_the_wording(
    app, db, owner, editor
):
    """226's clip 4 (A7): a first take named with "no phone" while its prompt shows the phone
    is rewritten first, even when its prompt was written after the run's notes. 345's clip
    13: each turn the director worded that note anew ("No phone screen…", "No phone or call
    screen…") and each rewrote the prompt again; a rewrite that took the phone away is the
    rewrite, so the next turn makes the take."""
    project, (clip,), since = _first_takes(app, db, owner, editor, [(BRIEF, False)], clips=1)
    first = _tool(app, db, project, tool="make_take", clip_id=clip.clip_id,
                  note="No phone: his hands hang empty.")  # fmt: skip
    assert first.startswith(f"Rewriting clip {clip.clip_id.removeprefix('c')}'s prompt")
    (change,) = _jobs(db, project, "change", since)
    change.status = "succeeded"  # its line keeps the phone
    db.commit()
    said = _tool(app, db, project, tool="make_take", clip_id=clip.clip_id,
                 note="No phone or call screen; heavy and quiet, never smiling.")  # fmt: skip
    assert said.startswith("Making 1 take.")
    assert len(_jobs(db, project, "change", since)) == 1
