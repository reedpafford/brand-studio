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


def test_a_read_brief_and_a_one_clip_note_hold_only_that_clip(app, db, owner, editor):
    """The brief came before the prompts were written (their writer read it): it holds none.
    A later note naming one clip holds that clip alone, whose prompt is rewritten (one call,
    every held clip a part) while every other first take goes out in the same turn; once
    rewritten it has read the note, so the next make_take makes it, never a second rewrite."""
    project, rows, since = _first_takes(app, db, owner, editor, [
        (BRIEF, False), ("Clip {n}: no man anywhere.", True)])  # fmt: skip
    clip = rows[0]
    n = clip.clip_id.removeprefix("c")
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
    clip_prompts.log_prompt(db, clip, None)
    db.commit()
    state = {c["clip_id"]: c for c in director.video_state(db, project)["clips"]}
    assert "against_notes" not in state[clip.clip_id]
    assert _tool(app, db, project, tool="make_take", clip_id="", note="") == "Making 1 take."
    assert len(_jobs(db, project, "clip_prompts", since)) == 1  # rewritten once


def test_a_first_take_rewritten_for_its_note_is_made_next_whatever_the_wording(
    app, db, owner, editor
):
    """345's clip 13: each turn the director worded its note anew ("No phone screen…", "No
    phone or call screen…"), and each rewrote the prompt again. One rewrite since the run's
    newest note is the rewrite: the next turn makes the take."""
    project, (clip,), since = _first_takes(app, db, owner, editor, [(BRIEF, True)], clips=1)
    first = _tool(app, db, project, tool="make_take", clip_id=clip.clip_id,
                  note="No phone screen ever shows; she keeps walking.")  # fmt: skip
    assert first.startswith(f"Rewriting clip {clip.clip_id.removeprefix('c')}'s prompt")
    (change,) = _jobs(db, project, "change", since)
    change.status = "succeeded"
    db.commit()
    said = _tool(app, db, project, tool="make_take", clip_id=clip.clip_id,
                 note="No phone or call screen; heavy and quiet, never smiling.")  # fmt: skip
    assert said.startswith("Making 1 take.")
    assert len(_jobs(db, project, "change", since)) == 1
