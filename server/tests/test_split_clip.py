"""S3-11: a clip too long for its video model is split into clips it can make, between its
shots and at its sentence breaks, the words unchanged. Free; the stuck run's card offers it
with what the new clips then need, and the director does it itself (split_clip). All on the
stand-ins."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified

from app import breakdown_fix, director, director_tools
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.prompts import check
from app.prompts.schemas import Breakdown
from tests.test_breakdown import _shot
from tests.test_run_progress import _done, _progress

NIGHT = ("SCENE 1 — INT. BEDROOM — NIGHT\n"
         "NARRATOR: At 3 AM your gut wakes up. It churns the day's beer. The bloat climbs. "
         "Water helps. So does the capsule.\n"
         "NARRATOR: Link in my bio.")  # fmt: skip
SAID = "At 3 AM your gut wakes up. It churns the day's beer. The bloat climbs. Water helps. "
LONG = {"hook": "3 AM.", "scenes": [{"id": 1, "heading": "INT. BEDROOM — NIGHT", "look": "Dark.",
        "shots": [_shot("1.1", [2], "NARRATOR", SAID + "So does the capsule.", 30),
                  _shot("1.2", [3], "NARRATOR", "Link in my bio.", 2)]}],
        "clips": [{"id": "c1", "shot_ids": ["1.1"], "seconds": 30, "seam": "cut"},
                  {"id": "c2", "shot_ids": ["1.2"], "seconds": 4, "seam": "end"}]}  # fmt: skip
TOO_LONG = "clip c1: 30 s is outside 4–12 s"


def test_one_long_shot_is_cut_at_its_sentence_breaks_and_the_words_stay():
    assert check.breakdown(NIGHT, Breakdown.model_validate(LONG), {}, 4, 12).count(TOO_LONG) == 1
    assert breakdown_fix.fixes([TOO_LONG], LONG, NIGHT) == [
        {"problem": TOO_LONG, "kind": "split_clip", "label": "Split the clip"}]  # fmt: skip
    assert breakdown_fix.split_into(LONG, NIGHT, "c1", 4, 12) == 3
    fixed, done = breakdown_fix.repair(NIGHT, Breakdown.model_validate(LONG), [TOO_LONG], 4, 12)
    assert done == ["Split clip 1 so the video model can make it."]
    shots = fixed.scenes[0].shots
    assert [s.id for s in shots] == ["1.1.1", "1.1.2", "1.1.3", "1.2"]
    assert " ".join(s.line for s in shots[:3]) == SAID + "So does the capsule."  # word for word
    assert all(s.script_lines == [2] and s.action == "They argue." for s in shots[:3])
    assert [c.id for c in fixed.clips] == ["c1", "c2", "c3", "c4"]  # numbered again
    assert fixed.clips[-1].shot_ids == ["1.2"] and all(c.seconds <= 12 for c in fixed.clips)
    assert round(sum(s.seconds for s in shots[:3])) == 30  # each as long as its words
    left = check.breakdown(NIGHT, fixed, {}, 4, 12)
    assert not [p for p in left if "outside" in p or "differs" in p or "no shot" in p], left


def test_one_sentence_too_long_is_never_offered_a_split():
    one = {**LONG, "scenes": [{**LONG["scenes"][0], "shots": [
        _shot("1.1", [3], "NARRATOR", "Link in my bio.", 30),
        _shot("1.2", [2], "NARRATOR", SAID, 2)]}]}  # fmt: skip
    assert breakdown_fix.split_into(one, NIGHT, "c1", 4, 12) == 1
    assert breakdown_fix.fixes([TOO_LONG], one, NIGHT) == []  # shorten it, or another model


def _stuck(app, db, owner, editor) -> tuple[int, BreakdownVersion]:
    """A delivered video whose clip 1 became 20 s on Seedance 1 Lite (12 s at most), its run
    stopped on it: one shot over both script lines, two sentences."""
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    project.video_model = "seedance-1-lite"
    row = db.scalars(select(BreakdownVersion).where(BreakdownVersion.project_id == pid)
                     .order_by(BreakdownVersion.id.desc())).first()  # fmt: skip
    data = dict(row.data)
    shot = {**data["scenes"][0]["shots"][0], "script_lines": [2, 3], "speaker": None,
            "line": None, "seconds": 20}  # fmt: skip
    data["scenes"] = [{**data["scenes"][0], "shots": [shot]}]
    data["clips"] = [{**data["clips"][0], "shot_ids": [shot["id"]], "seconds": 20}]
    row.data, row.problems = data, ["clip c1: 20 s is outside 4–12 s"]
    flag_modified(row, "data")
    clip = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    clip.seconds, clip.picked_take_id = 20, None
    last = director.turns(db, project)[-1]
    last.input = {**last.input, "result": "Stopped.", "ended": "It stopped: This clip is 20 s, "
                  "but Seedance 1 Lite makes at most 12 s a clip."}  # fmt: skip
    db.commit()
    return pid, row


def test_the_stuck_run_offers_the_split_free_with_what_it_then_needs(app, db, owner, editor):
    pid, _ = _stuck(app, db, owner, editor)
    p = _progress(owner, pid)
    (c,) = p["scenes"][0]["clips"]
    assert (c["state"], c["note"]) == ("too_long", "Seedance 1 Lite makes at most 12 s a clip")
    assert (p["status"], p["title"]) == ("needs_fix", "Stopped at clip 1")
    failed = p["failed"]
    assert failed["title"] == "Clip 1 couldn’t be made"
    assert failed["why"] == ("Clip 1 runs 20 s, but Seedance 1 Lite makes at most 12 s a clip. "
                             "Nothing was charged.")  # fmt: skip
    assert failed["offer"] == ("I can split it into 2 clips at the sentence breaks. The words "
                               "don’t change, and the split itself is free.")  # fmt: skip
    split, model = failed["fixes"]
    assert (split["kind"], split["label"], split["price"]) == ("split", "Split it into 2 clips",
                                                               "free")  # fmt: skip
    assert split["problem"] == "clip c1: 20 s is outside 4–12 s"
    assert split["then"].startswith("$") and split["then"] != "$0.00"  # stills, prompts, takes
    assert _progress(editor, pid)["failed"]["fixes"][0]["then"].endswith("credits")
    assert (model["kind"], model["label"]) == ("model", "Use a model that makes longer clips…")

    spent = db.scalar(select(func.coalesce(func.sum(Job.credits), 0)))
    done = editor.post(f"/projects/{pid}/breakdown/fix", json={"problems": [split["problem"]]})
    assert done.status_code == 200, done.text  # the press the card makes
    assert done.json()["fixed"] == ["Split clip 1 so the video model can make it."]
    assert [c["seconds"] for c in done.json()["breakdown"]["clips"]] == [12, 8]
    assert not [x for x in done.json()["problems"] if "outside" in x]
    assert db.scalar(select(func.coalesce(func.sum(Job.credits), 0))) == spent  # free


def test_the_director_splits_a_clip_too_long_for_its_model(app, db, owner, editor):
    pid, _ = _stuck(app, db, owner, editor)
    project = db.get(Project, pid)
    state = {**director.video_state(db, project), "treatment": "written"}
    assert state["too_long"] == ["c1"]
    move = director.choose(state)  # the stand-in: before its stills, the split
    assert (move["tool"], move["clip_id"]) == ("split_clip", "c1")
    user = db.query(User).filter_by(email="ed@example.com").one()
    said = director_tools.run(db, user, project, move, None)
    assert said == "Split clip 1 into 2 clips at its sentence breaks."
    again = director_tools.run(db, user, db.get(Project, pid), move, None)
    assert again == "Refused: clip 1 isn't longer than the video model makes."
    assert Decimal(0) == db.scalar(select(func.coalesce(func.sum(Job.credits), 0)).where(
        Job.created_at > director.turns(db, project)[-1].created_at))  # fmt: skip


def test_carrying_on_the_director_splits_it_and_delivers(app, db, owner, editor):
    """End to end on the stand-ins: Carry on, and the run splits the clip, draws, writes and
    makes the new clips, cuts, watches and delivers."""
    from tests.test_director import _run

    pid, _ = _stuck(app, db, owner, editor)
    assert editor.post(f"/projects/{pid}/director").status_code == 201
    _run(app, db, ticks=120)
    out = editor.get(f"/projects/{pid}/director").json()
    tools = [t["tool"] for t in out["turns"]]
    assert out["status"] == "delivered", (out["ended"], [(t["tool"], t["result"])
                                                         for t in out["turns"]])  # fmt: skip
    assert tools[:3].count("split_clip") == 1 and tools[-1] == "deliver", tools
    split = next(t for t in out["turns"] if t["tool"] == "split_clip")
    assert split["result"] == "Split clip 1 into 2 clips at its sentence breaks."
    assert "storyboard" not in tools  # the cut shots open on the still they were cut from
    from app.models.storyboards import StoryboardFrame

    bd = db.scalars(select(BreakdownVersion).where(BreakdownVersion.project_id == pid)
                    .order_by(BreakdownVersion.id.desc())).first()  # fmt: skip
    frames = db.query(StoryboardFrame).filter_by(breakdown_id=bd.id).all()
    assert sorted(f.shot_id for f in frames) == ["1.1.1", "1.1.2"]
    assert all(f.file_id for f in frames)
    clips = db.query(ProjectClip).filter_by(project_id=pid, breakdown_id=bd.id).all()
    assert sorted(c.seconds for c in clips if c.picked_take_id) == [8, 12]  # both made
    p = _progress(owner, pid)
    assert p["status"] == "delivered" and [c["state"] for c in p["scenes"][0]["clips"]] != []


def test_a_camera_line_in_the_cut_shot_stays_in_a_shot():
    script = NIGHT.replace("\nNARRATOR: Link in my bio.", "\n[Camera] Slow push in.\nNARRATOR: "
                           "Link in my bio.")  # fmt: skip
    data = {**LONG, "scenes": [{**LONG["scenes"][0], "shots": [
        {**LONG["scenes"][0]["shots"][0], "script_lines": [2, 3]},
        {**LONG["scenes"][0]["shots"][1], "script_lines": [4]}]}]}  # fmt: skip
    fixed, _ = breakdown_fix.repair(script, Breakdown.model_validate(data), [TOO_LONG], 4, 12)
    assert 3 in fixed.scenes[0].shots[0].script_lines  # with the first piece
    assert not [p for p in check.breakdown(script, fixed, {}, 4, 12) if "no shot" in p]


def test_a_sentence_still_too_long_is_never_split_or_sent_short():
    words = " ".join(["word"] * 70)
    one = {**LONG, "scenes": [{**LONG["scenes"][0], "shots": [
        _shot("1.1", [2], "NARRATOR", f"{words}. Short one.", 30),
        _shot("1.2", [3], "NARRATOR", "Link in my bio.", 2)]}]}  # fmt: skip
    script = NIGHT.replace(SAID + "So does the capsule.", f"{words}. Short one.")
    assert breakdown_fix.split_into(one, script, "c1", 4, 12) == 1
    assert breakdown_fix.fixes([TOO_LONG], one, script) == []


def test_a_cut_never_falls_inside_a_name():
    assert breakdown_fix._sentences("Trust Dr. Pickle today. It works! J. Smith said so.") == [
        "Trust Dr. Pickle today.", "It works!", "J. Smith said so."]  # fmt: skip


def test_fix_all_splits_every_clip_too_long():
    two = {**LONG, "scenes": [{**LONG["scenes"][0], "shots": [
        _shot("1.1", [2], "NARRATOR", SAID + "So does the capsule.", 30),
        _shot("1.2", [2], "NARRATOR", SAID + "So does the capsule.", 30)]}],
        "clips": [{"id": "c1", "shot_ids": ["1.1"], "seconds": 30, "seam": "cut"},
                  {"id": "c2", "shot_ids": ["1.2"], "seconds": 30, "seam": "end"}]}  # fmt: skip
    asked = [TOO_LONG, "clip c2: 30 s is outside 4–12 s"]
    fixed, done = breakdown_fix.repair(NIGHT, Breakdown.model_validate(two), asked, 4, 12)
    assert len(done) == 2 and len(fixed.clips) == 6 and all(c.seconds <= 12 for c in fixed.clips)


def test_a_cut_shot_shares_its_time_in_the_song_and_the_next_shot_stays():
    from app.song_breakdown import cut_spans

    known = {"3.1": {"start": 0, "end": 4}, "4.1": {"start": 4, "end": 40, "sung": True},
             "5.1": {"start": 40, "end": 44}}  # fmt: skip
    order = ["3.1", "4.1.1", "4.1.2", "5.1"]
    got = cut_spans(known, order, {"4.1.1": 9, "4.1.2": 27})
    assert got == {"4.1.1": {"start": 4, "end": 13.0, "sung": True},
                   "4.1.2": {"start": 13.0, "end": 40, "sung": True}}  # fmt: skip


def test_a_run_stopped_for_something_else_isnt_blamed_on_a_long_clip(app, db, owner, editor):
    pid, _ = _stuck(app, db, owner, editor)
    last = director.turns(db, db.get(Project, pid))[-1]
    last.input = {**last.input, "ended": "It stopped: the looks kept being refused."}
    db.commit()
    p = _progress(owner, pid)
    assert (p["title"], p["failed"]["title"]) == ("Stopped", "The director stopped")
    assert p["failed"]["why"] == "It stopped: the looks kept being refused."


def test_a_clip_of_several_shots_with_one_sentence_too_long_isnt_offered_split():
    """QA on #1332: Split is offered only when it works (rule 22: never a button that fails)."""
    words = " ".join(["word"] * 70)
    script = NIGHT.replace(SAID + "So does the capsule.", f"{words}.")
    data = {**LONG, "scenes": [{**LONG["scenes"][0], "shots": [
        _shot("1.1", [2], "NARRATOR", f"{words}.", 20),
        _shot("1.2", [3], "NARRATOR", "Link in my bio.", 2)]}],
        "clips": [{"id": "c1", "shot_ids": ["1.1", "1.2"], "seconds": 22,
                   "seam": "end"}]}  # fmt: skip
    said = "clip c1: 22 s is outside 4–12 s"
    assert breakdown_fix.split_into(data, script, "c1", 4, 12) == 1
    assert breakdown_fix.fixes([said], data, script) == []


def test_each_piece_names_its_own_line_in_order():
    script = ("SCENE 1 — INT. BEDROOM — NIGHT\n[Camera] Water helps. Slow push in. "
              + " ".join(["more"] * 10) + ".\nNARRATOR: Water helps.")  # fmt: skip
    shot = _shot("1.1", [2, 3], None, None, 20)
    data = {**LONG, "scenes": [{**LONG["scenes"][0], "shots": [shot]}],
            "clips": [{"id": "c1", "shot_ids": ["1.1"], "seconds": 20, "seam": "end"}]}  # fmt: skip
    asked = ["clip c1: 20 s is outside 4–12 s"]
    fixed, done = breakdown_fix.repair(script, Breakdown.model_validate(data), asked, 4, 12)
    pieces = fixed.scenes[0].shots
    assert done and len(pieces) == 3
    assert [p.script_lines for p in pieces] == [[2], [2], [3]]  # the 2nd "Water helps." is 3's
