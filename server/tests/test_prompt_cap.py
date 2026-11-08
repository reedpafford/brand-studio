"""Video 245: Seedance 2.0 takes a prompt of at most 4000 characters (Replicate: a 422,
"input.prompt: String length must be less than or equal to 4000"), and 245's prompts, written
for 2.5, ran 4038–4780. A prompt over its model's limit is never sent: it's rewritten to fit,
free, and the writer is told the limit first; a request refused as invalid is never sent again
unchanged and never counted as spent. Mocked Replicate and Claude: no paid calls."""

import re
from decimal import Decimal

from app import clip_prompts, clip_takes
from app.catalogue import get_model
from app.credits import never_billed
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.worker import _plain
from tests.test_clip_takes import clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

TOO_LONG = ('RuntimeError(\'Replicate 422: {"detail":"- input.prompt: String length must be '
            'less than or equal to 4000","status":422}\')')  # fmt: skip


def _on_two(db, clip) -> ProjectClip:  # noqa: F811
    row = db.get(ProjectClip, clip["id"])
    row.model = {"id": "seedance-2.0", "why": "The director moved it.", "by": "director"}
    db.commit()
    return row


def test_every_video_models_prompt_limit_is_known():
    assert get_model("seedance-2.0").prompt_max == 4000
    for other in ("seedance-2.5", "seedance-1-lite", "gemini-omni-1.2"):
        assert get_model(other).prompt_max == 0, other  # their schemas state none


def test_a_prompt_too_long_for_its_model_is_rewritten_to_fit_never_sent(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    base = f"/projects/{setup['project']}"
    row = _on_two(db, clip)
    row.prompt = f"{row.prompt}\n{'Lush detail. ' * 400}"  # ~5,200 characters, as 245's
    db.commit()
    made = editor.post(f"{base}/clips/{row.id}/generate")
    assert made.status_code == 409, made.text
    assert made.json()["detail"].startswith("The prompt is too long for Seedance 2.0 (")
    assert "rewritten to fit, free" in made.json()["detail"]
    jobs = db.query(Job).filter(Job.project_id == setup["project"]).all()
    assert not [j for j in jobs if j.input.get("step") == "clip_take"]  # never sent
    (fix,) = [j for j in jobs if j.input.get(clip_takes.FIT)]
    assert fix.input["clip_ids"] == [row.clip_id] and fix.credits == 0  # free
    told = fix.input["prompt"]  # its own instruction: shorten all else, keep these lines
    asked = fix.input["fit_max"] - clip_takes._noted("x" * clip_takes.NOTE_MAX) - clip_takes.SLACK
    assert f"under {asked} characters" in told and asked < 3400  # room for any Redo note (271)
    assert "each shot's description in fewer words" in told
    assert '"Shot N | a–b s."' in told and "every spoken or quoted line word for word" in told
    assert "the Keep: line" in told and "Change only the lines" not in told
    again = editor.post(f"{base}/clips/{row.id}/generate")  # while it's being rewritten
    assert again.status_code == 409
    assert len([j for j in db.query(Job) if j.input.get(clip_takes.FIT)]) == 1  # one fix
    fix.status = JobStatus.succeeded
    db.commit()
    editor.post(f"{base}/clips/{row.id}/generate")  # still too long: a second rewrite
    fix2 = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)][-1]
    fix2.status = JobStatus.succeeded
    db.commit()
    stuck = editor.post(f"{base}/clips/{row.id}/generate")
    assert stuck.json()["detail"].startswith("The prompt is still too long for Seedance 2.0")
    row.prompt = row.prompt[:3000]  # rewritten to fit
    db.commit()
    assert editor.post(f"{base}/clips/{row.id}/generate").status_code == 201


def test_the_writer_is_told_each_clips_model_limit(db, setup, clip):  # noqa: F811
    video = db.get(Project, setup["project"])
    row = db.get(ProjectClip, clip["id"])
    assert clip_prompts.prompt_limits(db, video, [row.clip_id]) == ""  # 2.5: no limit
    _on_two(db, clip)
    said = clip_prompts.prompt_limits(db, video, [row.clip_id])
    assert said == (f"<limit>{row.clip_id} is made on Seedance 2.0, which takes a prompt of "
                    "at most 4000 characters: write its prompt in under 3200 "
                    "characters.</limit>")  # fmt: skip
    data = clip_prompts.job_input(db, video, clip_prompts.newest(db, video), [row.clip_id])
    assert said in data["prompt"]


def test_a_request_refused_as_invalid_is_never_sent_again_unchanged_nor_counted(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    base = f"/projects/{setup['project']}"
    row = db.get(ProjectClip, clip["id"])
    take = clip_takes.take_input(db, db.get(Project, setup["project"]), row)
    failed = Job(workspace_id=db.get(Project, setup["project"]).workspace_id,
                 created_by_id=row.project_id and db.get(Project, row.project_id).created_by_id,
                 kind="video", provider="replicate", input=take, project_id=setup["project"],
                 credits=Decimal(5), status=JobStatus.failed, error_detail=TOO_LONG)  # fmt: skip
    db.add(failed)
    db.commit()
    assert clip_takes.why_failed(failed) == "invalid"
    assert never_billed(failed)  # Replicate refused it before running: $0 spent
    assert _plain(failed, TOO_LONG) == (
        "The service refused this request as invalid, so nothing was charged: input.prompt: "
        "String length must be less than or equal to 4000.")  # fmt: skip
    clip_takes.retry(db, failed)  # never retried on its own as it is
    assert not db.query(Job).filter(Job.retry_of_id == failed.id).count()
    same = editor.post(f"{base}/clips/{row.id}/generate")  # the director's "try again"
    assert same.status_code == 409 and "would be refused again" in same.json()["detail"]
    row.prompt = f"{row.prompt} Calmer."  # changed: it may go
    db.commit()
    assert editor.post(f"{base}/clips/{row.id}/generate").status_code == 201


def test_the_directors_take_names_the_fix_and_the_rewrite_is_on_its_way(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    from app import director_tools
    from app.models.accounts import User

    row = _on_two(db, clip)
    row.prompt = f"{row.prompt}\n{'Lush detail. ' * 400}"
    db.commit()
    video = db.get(Project, setup["project"])
    said = director_tools.run(db, db.get(User, video.created_by_id), video,
                              {"tool": "make_take", "clip_id": row.clip_id, "note": ""},
                              app.state.storage)  # fmt: skip
    assert said == (f"Refused: The prompt of {row.clip_id} is too long for its model, so "
                    "it's being rewritten to fit (free); make its take once it's "
                    "rewritten.")  # fmt: skip
    assert [j for j in db.query(Job) if j.input.get(clip_takes.FIT)]  # the fix is on its way
    assert not [j for j in db.query(Job) if j.input.get("step") == "clip_take"]


def test_a_redo_note_that_takes_it_past_the_limit_is_fitted_with_room_for_the_note(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    """Video 271 (Seedance 2.0): a prompt that fit alone went over with the director's Redo
    note; its fit came back 3,441 characters, under the 4,000 it was held to but still over
    with the note, so the take was refused again, twice, and never made. The fit now leaves
    room for any Redo note, and the take with that note is made once it lands."""
    base = f"/projects/{setup['project']}"
    row = _on_two(db, clip)
    short = row.prompt.splitlines()

    def padded(n: int) -> str:
        return "\n".join(f"{x[:16]}{PAD * n}{x[16:]}" if x.startswith("Shot ") else x
                         for x in short)  # fmt: skip

    note = "Two softgels slide out of the pile toward camera and hold a beat. " * 7  # ~460
    row.prompt = next(padded(n) for n in range(60) if len(padded(n)) > 3500)
    db.commit()
    alone = clip_takes.take_input(db, db.get(Project, setup["project"]), row, check=False)
    assert len(alone["input"]["prompt"]) <= 4000  # it fits alone: its first take went
    made = editor.post(f"{base}/clips/{row.id}/generate", json={"note": note})
    assert made.status_code == 409 and "rewritten to fit, free" in made.json()["detail"]
    (fix,) = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)]
    fit = fix.input["fit_max"]
    _land(
        db,
        fix,
        row.clip_id,
        next(padded(n) for n in range(60, 0, -1) if len(padded(n)) < fit + 300),
        row.references,
    )  # 271's
    db.refresh(row)
    assert len(row.prompt) > 3500 and row.change["status"] == "failed"  # never saved
    editor.post(f"{base}/clips/{row.id}/generate", json={"note": note})  # its second fit
    fix2 = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)][-1]
    asked = int(re.search(r"under (\d+) characters", fix2.input["prompt"])[1])
    _land(
        db,
        fix2,
        row.clip_id,
        next(padded(n) for n in range(60, 0, -1) if len(padded(n)) <= asked),
        row.references,
    )  # as asked
    db.refresh(row)
    assert len(row.prompt) <= fit and (row.change or {}).get("status") != "failed"
    again = editor.post(f"{base}/clips/{row.id}/generate", json={"note": note})
    assert again.status_code == 201, again.text  # the take follows the fit, with its note
    take = [j for j in db.query(Job) if j.input.get("step") == "clip_take"][-1]
    assert note.strip() in take.input["input"]["prompt"]
    assert len(take.input["input"]["prompt"]) <= 4000
    longest = clip_takes._noted("x" * clip_takes.NOTE_MAX) - clip_takes._noted(note)
    assert len(take.input["input"]["prompt"]) + longest <= 4000  # any other note fits too


def test_a_fit_saved_for_one_take_never_spends_a_try_when_a_later_note_is_too_long(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    """QA on #1453: a fit saved for a first take (no note) can be too long once a remake adds
    its note. That asks for a new rewrite, free, never "still too long": only rewrites that
    weren't saved count toward the two."""
    base = f"/projects/{setup['project']}"
    row = _on_two(db, clip)
    short = row.prompt.splitlines()

    def padded(n: int) -> str:
        return "\n".join(f"{x[:16]}{PAD * n}{x[16:]}" if x.startswith("Shot ") else x
                         for x in short)  # fmt: skip

    row.prompt = padded(60)
    db.commit()
    editor.post(f"{base}/clips/{row.id}/generate")
    (fix,) = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)]
    dropped = "\n".join(x for x in short if not x.startswith("Shot 2 "))
    _land(db, fix, row.clip_id, dropped, row.references)  # a shot dropped: not saved
    db.refresh(row)
    assert row.change["status"] == "failed"
    editor.post(f"{base}/clips/{row.id}/generate")  # a second rewrite: one failed so far
    fix2 = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)][-1]
    _land(
        db,
        fix2,
        row.clip_id,
        next(padded(n) for n in range(60, 0, -1) if len(padded(n)) <= fix2.input["fit_max"]),
        row.references,
    )
    assert editor.post(f"{base}/clips/{row.id}/generate").status_code == 201  # its first take
    for made in db.query(Job).filter(Job.kind == "video"):
        made.status = JobStatus.succeeded  # made: a remake may be asked for
    db.commit()
    note = "Slower push in on the bowl, and hold the last beat. " * 9  # a remake's note
    later = editor.post(f"{base}/clips/{row.id}/generate", json={"note": note})
    assert later.status_code == 409, later.text  # too long with the note
    assert "rewritten to fit, free" in later.json()["detail"]  # again, free: not "still"
    assert clip_takes.failed_fits(db, row) == 1  # the saved one never counted


def test_a_fit_that_rewrote_its_keep_line_gets_it_back_and_the_take_goes(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    """Video 268's c3 (Seedance 2.0): both fits came back short enough (3,114 and 3,296
    characters) but rewrote the Keep: line, so neither was saved and the take was refused
    three times; the director then moved the clip to Seedance 2.5 (dearer) by itself. The Keep
    line is put back as it was and the fit is saved; a move for the length is refused."""
    from app import model_map

    base = f"/projects/{setup['project']}"
    row = _on_two(db, clip)
    short = row.prompt.splitlines()
    assert any(x.startswith("Keep: ") for x in short)
    row.prompt = "\n".join(f"{x[:16]}{PAD * 25}{x[16:]}" if x.startswith("Shot ") else x
                           for x in short)  # fmt: skip
    db.commit()
    video = db.get(Project, setup["project"])
    moved = model_map.choose(db, video, row, "seedance-2.5", "Its prompt is too long for 2.0.")
    assert moved.startswith("Refused: clip") and "never to get past that" in moved
    assert row.model["id"] == "seedance-2.0"  # it stays
    editor.post(f"{base}/clips/{row.id}/generate")
    (fix,) = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)]
    keep = next(x for x in short if x.startswith("Keep: "))
    fit = [f"{x[:16]}{PAD * 2}{x[16:]}" if x.startswith("Shot ") else x for x in short]
    _land(db, fix, row.clip_id, "\n".join("Keep: as the sheets." if x == keep else x
                                          for x in fit), row.references)  # fmt: skip
    db.refresh(row)
    assert (row.change or {}).get("status") != "failed" and keep in row.prompt.splitlines()
    assert editor.post(f"{base}/clips/{row.id}/generate").status_code == 201
    said = model_map.choose(db, video, row, "seedance-2.5", "Note 1: the owner asked for 2.5.")
    assert not said.startswith("Refused")  # a person's note may move it


def test_a_move_for_length_measures_the_prompt_as_sent_and_says_ask_once_rewrites_are_used(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
    monkeypatch,
):
    """QA on #1453: the length is the prompt a take sends, its people said in words too; and
    once both rewrites failed, the refusal says to ask the owner, not that it's rewritten."""
    from app import model_map

    row, video = _on_two(db, clip), db.get(Project, setup["project"])
    assert len(row.prompt) < 4000
    sent = clip_takes.take_input(db, video, row, check=False)
    words = {**sent, "input": {**sent["input"], "prompt": "Gran, said in words. " * 200}}
    monkeypatch.setattr(clip_takes, "take_input", lambda *a, **k: words)  # as a take sends it
    said = model_map.choose(db, video, row, "seedance-2.5", "It won't fit.")
    assert said.startswith("Refused: clip") and "rewritten to fit, free" in said
    for _ in range(2):  # both rewrites done and never saved
        db.add(Job(workspace_id=video.workspace_id, kind="write-claude", provider="claude",
                   project_id=video.id, status=JobStatus.succeeded,
                   input={clip_takes.FIT: True, "clip_ids": [row.clip_id]}))  # fmt: skip
    db.commit()
    said = model_map.choose(db, video, row, "seedance-2.5", "It won't fit.")
    assert "ask the owner" in said and "rewritten to fit" not in said


def _land(db, fix, clip_id, prompt, references):
    """The fix's answer saved, as the worker saves it."""
    fix.output = {"clips": [{"clip_id": clip_id, "seconds": 5, "references": references,
                             "prompt": prompt}]}  # fmt: skip
    fix.status = JobStatus.succeeded
    clip_prompts.save_clip_prompts(db, fix)
    db.commit()


PAD = "Warm window light, steam off the mug, the fridge hums, her keys lie on the counter. "


def _curly(line: str) -> str:
    return re.sub(r'"([^"]*)"', r"“\1”", line)


def test_a_fit_that_shortens_the_shot_descriptions_is_saved_one_that_drops_a_shot_is_not(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    """QA on #1430: 245's prompts ran 4,780 characters, mostly long shot descriptions, so a fit
    must be free to say those shorter. It keeps each shot's start ("Shot N | a–b s.") in order,
    every quoted line word for word (straight or curly quotes alike) and the Keep: line; one
    that drops a shot (on the stand-ins a 4,780-character prompt came back at 293) is never
    saved, the clip says so, and it counts as one of its two tries."""
    base = f"/projects/{setup['project']}"
    row = _on_two(db, clip)
    short = row.prompt.splitlines()
    long = "\n".join(f"{x[:16]}{PAD * 23}{x[16:]}" if x.startswith("Shot ") else x for x in short)
    assert 4700 < len(long) < 4800, len(long)  # as 245's
    row.prompt = long
    db.commit()
    editor.post(f"{base}/clips/{row.id}/generate")
    (fix,) = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)]
    refs = row.references
    one_shot = "\n".join(x for x in short if not x.startswith("Shot 2 "))
    _land(db, fix, row.clip_id, one_shot, refs)
    db.refresh(row)
    assert row.prompt == long  # never saved
    assert (row.change["note"], row.change["status"]) == (clip_prompts.FIT_NOTE, "failed")
    assert "dropped or changed" in row.change["error"] and "stays as it was" in row.change["error"]
    editor.post(f"{base}/clips/{row.id}/generate")  # one try used: a second fit is asked
    fix2 = [j for j in db.query(Job) if j.input.get(clip_takes.FIT)][-1]
    assert fix2.id != fix.id
    fit = [f"{x[:16]}{PAD * 2}{x[16:]}" if x.startswith("Shot ") else x for x in short]
    fit = [_curly(x) if x.startswith("Shot ") else x for x in fit]  # curly quotes, same words
    _land(db, fix2, row.clip_id, "\n".join(fit), refs)
    db.refresh(row)
    assert len(row.prompt) < 3400 and row.prompt != long  # it fits
    assert (row.change or {}).get("status") != "failed"
    assert "“Nate, where is all your money?”" in row.prompt


def test_a_fit_keeps_every_shot_and_quoted_line_and_stays_under_the_limit():
    before = ("Shot 1 | 0–2 s. A long, slow push in on the kitchen. Theo says \"Yes.\"\n"
              "Shot 2 | 2-5 s. Wide. Mom: “Go to your room.” The \"SALE\" sign blinks.\n"
              "Keep: Mom as in [Image1].")  # fmt: skip
    job = Job(input={clip_takes.FIT: True, "before": before, "fit_max": 200})
    fits = clip_prompts.fit_lost
    shorter = (
        "Shot 1 | 0–2 s. Push in. Theo says “Yes.”\n"
        'Shot 2 | 2–5 s. Mom: "Go to your room." "SALE" blinks.\nKeep: Mom as in [Image1].'
    )
    assert fits(job, shorter) == ""  # descriptions shorter, straight and curly quotes alike
    lost = "The shortened prompt dropped"
    assert fits(job, shorter.replace(" Theo says “Yes.”", " Theo nods.")).startswith(lost)
    assert fits(job, shorter.replace('"SALE" blinks.', "")).startswith(lost)  # a quote
    assert fits(job, shorter.replace("Go to your room.", "Go.")).startswith(lost)  # changed
    assert fits(job, shorter.split("\nShot 2")[0] + "\nKeep: Mom as in [Image1].").startswith(
        lost
    )  # a shot dropped
    assert fits(job, shorter.replace("2–5 s.", "2–6 s.")).startswith(lost)  # its times
    assert fits(job, shorter.replace("\nKeep: Mom as in [Image1].", "")).startswith(lost)
    assert fits(Job(input={**job.input, "fit_max": 20}), shorter).startswith(
        "The shortened prompt is still"
    )
    assert fits(Job(input={}), "") == ""  # not a fit: nothing to check


def test_two_presses_at_once_queue_one_fit_and_a_full_rewrite_comes_first(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    import pytest
    from fastapi import HTTPException

    video = db.get(Project, setup["project"])
    row = _on_two(db, clip)
    row.prompt = f"{row.prompt}\n{'Lush detail. ' * 400}"
    db.commit()
    model, sent = get_model("seedance-2.0"), row.prompt
    for _ in range(2):  # two presses: the second sees the first's fix under the lock
        with pytest.raises(HTTPException):
            clip_takes.fits_prompt(db, video, row, model, sent)
    assert len([j for j in db.query(Job) if j.input.get(clip_takes.FIT)]) == 1
    db.query(Job).filter(Job.project_id == video.id).delete()
    db.add(Job(workspace_id=video.workspace_id, created_by_id=video.created_by_id,
               kind="write-claude", provider="claude", input={"step": "clip_prompts"},
               project_id=video.id, credits=0, status=JobStatus.queued))  # fmt: skip
    db.commit()
    with pytest.raises(HTTPException) as no:  # every clip is being written: after that
        clip_takes.fits_prompt(db, video, row, model, sent)
    assert "once the clip prompts being written now are done" in no.value.detail
    assert not [j for j in db.query(Job) if j.input.get(clip_takes.FIT)]


def test_an_invalid_take_may_go_again_once_its_pictures_change(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
):
    import pytest
    from fastapi import HTTPException

    video = db.get(Project, setup["project"])
    row = db.get(ProjectClip, clip["id"])
    take = clip_takes.take_input(db, video, row)
    failed = Job(workspace_id=video.workspace_id, created_by_id=video.created_by_id,
                 kind="video", provider="replicate", input=take, project_id=video.id,
                 credits=Decimal(5), status=JobStatus.failed, error_detail=TOO_LONG)  # fmt: skip
    db.add(failed)
    db.commit()
    with pytest.raises(HTTPException):  # the same request, pictures and all: refused
        clip_takes.not_again(db, row, take["model"], take["input"], take["files"])
    other = {**take["files"], "reference_images": [999999]}  # a picture changed
    clip_takes.not_again(db, row, take["model"], take["input"], other)  # it may go
