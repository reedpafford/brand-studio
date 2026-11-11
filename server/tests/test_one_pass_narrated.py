"""The one-pass director on a narrated video (app/one_pass.py, app/one_pass_timed.py): the
narration is made and timed first, the plan puts each shot on a measured start, every clip is
silent B-roll, and the cut lays the narration over them. On the stand-ins."""

import copy
from decimal import Decimal

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app import asks, one_pass, one_pass_timed
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.songs import SongTake
from app.providers import get_providers
from app.settings import get_settings
from app.worker import run_once
from tests.helpers import make_it, ok_when_asked

NARRATION = ("Every morning starts the same. You pour the coffee and open the app. "
             "The numbers are up again.\nSo you tell a friend.\nGet fomo today.")  # fmt: skip
BODY = {"type": "narrated", "look": "house", "shape": "9:16", "text": NARRATION, "brand_id": 1}


@pytest.fixture(autouse=True)
def _one_pass_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "one_pass", True)
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)  # as on the stand-ins


def _run(app, db, ticks=60, start=True):
    app.state.settings.fake_providers = True
    if not hasattr(app.state, "stand_ins"):
        app.state.stand_ins = get_providers(app.state.settings, app.state.storage)
    for _ in range(ticks):
        run_once(db, app.state.stand_ins, app.state.storage)
        db.expire_all()
        ok_when_asked(db)
        if start:
            make_it(db)


def _video(db) -> Project:
    return db.query(Project).execution_options(see_hidden=True).order_by(Project.id.desc()).first()


def _jobs(db, step: str) -> list[Job]:
    return db.query(Job).filter(Job.input["step"].as_string() == step).order_by(Job.id).all()


def _delivered(app, owner, db, **change) -> int:
    fs = owner.post("/freestyles", json={**BODY, **change})
    assert fs.status_code == 201, fs.text
    _run(app, db)
    out = owner.get(f"/freestyles/{fs.json()['id']}").json()
    turns = [((j.output or {}).get("tool"), j.input.get("result")) for j in _jobs(db, "director")]
    assert out["status"] == "delivered", ([t["text"] for t in out["thread"]], turns)
    return _video(db).id


def test_the_narration_is_made_and_timed_before_the_one_plan_call(app, owner, db):
    pid = _delivered(app, owner, db)
    assert db.get(Project, pid).engine == one_pass.ENGINE
    (plan,) = _jobs(db, "one_pass")
    (voice,) = _jobs(db, "song_take")
    take = db.query(SongTake).one()
    assert voice.finished_at <= plan.created_at and take.timing and plan.input["audio"]
    assert "<song seconds=" in plan.input["prompt"] and "This script is narrated" in plan.input[
        "system"][0]  # fmt: skip
    assert "**Voices**" not in plan.input["system"][0]  # the part for lines spoken on camera
    made = [(j.input.get("step") or j.kind, j.provider) for j in db.query(Job).order_by(Job.id)]
    assert [
        s
        for s, p in made
        if p == "claude" and s not in ("look_fit", "watch_cut", "narration_music")
    ] == ["one_pass"]
    assert all(j.provider == "server" for j in _jobs(db, "director"))


def test_every_shot_sits_on_a_measured_time_and_carries_the_lines_heard_under_it(app, owner, db):
    pid = _delivered(app, owner, db)
    take = db.query(SongTake).one()
    row = db.query(BreakdownVersion).order_by(BreakdownVersion.id.desc()).first()
    timed = row.data["song"]["shots"]
    starts = {0.0, *(x["start"] for x in take.timing["lines"])}
    assert row.data["song"]["take_id"] == take.id and {t["start"] for t in timed.values()} <= starts
    edges = [(t["start"], t["end"]) for t in timed.values()]
    assert edges[0][0] == 0 and all(a[1] == b[0] for a, b in zip(edges, edges[1:], strict=False))
    assert edges[-1][1] == round(take.seconds + 1.5, 2)  # the last picture holds past the words
    shots = [s for scene in row.data["scenes"] for s in scene["shots"]]
    assert [s["script_lines"] for s in shots] == [[1], [1], [1], [2], [3]]  # line 1: 3 sentences
    assert all(s["line"] is None and s["seconds"] == round(b - a, 2)
               for s, (a, b) in zip(shots, edges, strict=True))  # fmt: skip
    (clip,) = db.query(ProjectClip).all()
    assert clip.song_slice == {"start": 0.0, "end": edges[-1][1], "sung_shots": []}
    assert (
        clip.seconds == 11
        and "Shot 1 | 0-2 s." in clip.prompt
        and "Shot 5 | 8-11 s." in (clip.prompt)
    )  # whole seconds, each edge rounded where it falls
    assert not [p for p in (row.problems or []) + (clip.problems or [])
                if not p.startswith("Advice: ")]  # fmt: skip
    card = next(t["treatment"] for t in owner.get(f"/projects/{pid}/director").json()["thread"]
                if t.get("treatment"))  # fmt: skip
    assert card["beats"][0]["lines"] == [1, 2, 3] and card["beats"][0]["end"] == 10


def test_b_roll_is_silent_and_never_made_twice(app, owner, db):
    _delivered(app, owner, db)
    (clip,) = db.query(ProjectClip).all()
    assert clip.prompt.startswith("Audio: no one speaks") and clip.prompt.count(
        "No one speaks.") == 5 and '"' not in clip.prompt  # fmt: skip
    (listen,) = _jobs(db, "take_words")
    assert listen.input["silent"] and listen.input["lines"] == []  # any voice in it is a fault
    assert db.query(ClipTake).count() == 1 and len(_jobs(db, "clip_take")) == 1
    note = _jobs(db, "director")[-1].output["note"]
    assert "read in the Sarah voice (take 1). Music is added in post." in note["made"]
    assert note["spent"] <= note["up_to"]


def test_another_take_keeps_the_plan_and_remakes_only_a_clip_whose_piece_grew(app, owner, db):
    pid = _delivered(app, owner, db)
    was = one_pass.shooting_plan(db, db.get(Project, pid))
    assert owner.post(f"/projects/{pid}/songs").status_code == 201
    _run(app, db, ticks=4, start=False)
    new = db.query(SongTake).order_by(SongTake.id.desc()).first()
    slow = copy.deepcopy(new.timing)  # the same words, read slower: everything half as late again
    for x in [*slow["lines"], *slow["words"]]:
        x["start"], x["end"] = round(x["start"] * 1.5, 2), round(x["end"] * 1.5, 2)
    slow["seconds"] = new.seconds = round(new.seconds * 1.5, 2)
    new.timing = slow
    flag_modified(new, "timing")
    db.commit()
    used = owner.put(f"/projects/{pid}/song", json={"take_id": new.id})
    assert used.status_code == 200, used.text
    db.expire_all()
    row = db.query(BreakdownVersion).order_by(BreakdownVersion.id.desc()).first()
    plan = row.data[one_pass.PLAN]
    ats = [s["at"] for c in plan["clips"] for s in c["shots"]]
    assert ats == [t["start"] for t in row.data["song"]["shots"].values()] and ats[1] == 2.7
    assert [c["id"] for c in plan["clips"]] == [c["id"] for c in was["clips"]]  # the same plan
    (clip,) = db.query(ProjectClip).all()
    assert clip.breakdown_id == row.id and clip.picked_take_id is None and clip.seconds == 15
    assert owner.post(f"/projects/{pid}/director").status_code == 201  # Make it again
    _run(app, db)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert len(_jobs(db, "one_pass")) == 1 and db.query(ClipTake).count() == 2  # never replanned
    assert db.query(FinalVideo).order_by(FinalVideo.id.desc()).first().number == 2


def test_the_narration_is_on_the_planning_allowance_and_the_run_stays_inside_its_price(
    app, owner, db
):
    fs = owner.post("/freestyles", json={**BODY, "mode": "ask"})
    _run(app, db, ticks=8, start=False)  # its narration, its plan and its looks, then its card
    project = _video(db)
    (voice,) = _jobs(db, "song_take")
    assert voice.input[asks.BEFORE] and voice.status == "succeeded"
    (card,) = [j for j in _jobs(db, "director") if j.input.get(asks.START)]
    assert card.status == "needs_owner_approval" and not db.query(ClipTake).count()
    from app import watch_cut
    from app.clip_takes import takes_price
    from app.credits import estimate

    rows = db.query(ProjectClip).all()
    plan = sum((j.credits for j in _jobs(db, "one_pass")), Decimal(0))
    look = estimate(db, project.workspace_id, watch_cut.KIND, Decimal(1), {})
    watch = look * one_pass._watch_units(project, sum(r.seconds for r in rows), len(rows))
    assert asks.run_price(db, project) == plan + takes_price(db, project, rows) + watch  # once
    said = next(a for a in owner.get(f"/projects/{project.id}/asks").json() if a["kind"] == "start")
    assert "every clip once, and one watch of the cut" in said["why"]
    assert "Its narration is already made and timed" in said["why"]
    make_it(db)
    _run(app, db)
    assert owner.get(f"/freestyles/{fs.json()['id']}").json()["status"] == "delivered"
    price, spent = asks.approved_run(db, project)
    assert spent <= price and not db.query(Job).filter(
        Job.status == "needs_owner_approval").count()  # fmt: skip
    done = owner.get(f"/projects/{project.id}/director/progress").json()
    assert done["up_to"] >= float(price + voice.credits)  # the narration is in the video's total


def test_a_shot_that_starts_too_soon_is_left_out_and_the_plan_is_never_asked_again(
    app, owner, db, monkeypatch
):
    from app.providers.fake_local import FakeWriter

    asked, real = [], FakeWriter._one_pass
    monkeypatch.setattr(FakeWriter, "_one_pass", lambda self, p: asked.append(p) or real(self, p))
    pid = _delivered(app, owner, db, text=NARRATION + "\n[fake:bad-at]")
    assert len(asked) == 1 and len(_jobs(db, "one_pass")) == 1  # no second answer to pay for
    ats = [s["at"] for c in one_pass.shooting_plan(db, db.get(Project, pid))["clips"]
           for s in c["shots"]]  # fmt: skip
    assert ats[0] == 0 and all(b - a >= 1 for a, b in zip(ats, ats[1:], strict=False))


def test_a_zack_d_video_is_planned_the_same_way_with_its_formats_guide(app, owner, db):
    pid = _delivered(app, owner, db, type="zack-d")
    assert db.get(Project, pid).engine == one_pass.ENGINE
    (plan,) = _jobs(db, "one_pass")
    assert "## Format: Zack D" in plan.input["system"][0] and plan.input["audio"]
    assert "This script is narrated" in plan.input["system"][0]


def test_a_library_scripts_video_starts_unplanned_so_the_director_plans_it(app, owner, db):
    from tests.test_breakdown import BREAKDOWN
    from tests.test_script_library import _make

    made = _make(owner, text=NARRATION, kind="narrated")
    assert owner.put(f"/scripts/{made['id']}/drafts/0/breakdown", json=BREAKDOWN).status_code == 200
    r = owner.post("/freestyles", json={"shape": "9:16", "script_id": made["id"], "slot": 0})
    assert r.status_code == 201, r.text
    _run(app, db)
    assert owner.get(f"/freestyles/{r.json()['id']}").json()["status"] == "delivered"
    video = _video(db)
    assert video.engine == one_pass.ENGINE and len(_jobs(db, "one_pass")) == 1
    assert not db.query(BreakdownVersion).filter_by(source="library").count()  # its own plan


# --- The track's clock, with no database (app/one_pass_timed.py) ---

SCRIPT = ("INT. KITCHEN - DAY\nNARRATOR: It starts small. Then it grows. Nobody notices.\n"
          "[Camera] slow push in\nNARRATOR: Until today.")  # fmt: skip
LINES = [{"text": t, "start": a, "end": b, "heard": 1}
         for t, a, b in (("It starts small.", 0.1, 1.2), ("Then it grows.", 1.4, 2.6),
                         ("Nobody notices.", 2.8, 4.0), ("Until today.", 4.3, 5.2))]  # fmt: skip
TRACK = {"take_id": 7, "seconds": 5.4, "narrated": True, "hold": 1.5,
         "starts": [0.0, 0.1, 1.4, 2.8, 4.3],
         "lines": {"2": [0.1, 4.0], "4": [4.3, 5.2]}}  # fmt: skip


def _plan(ats: list[float], people=(), kind="broll") -> dict:
    shot = {"seconds": 1, "camera": "Wide", "action": "It happens.", "people": list(people),
            "extras": "", "line": None, "how": ""}  # fmt: skip
    clip = {"id": "c1", "name": "One", "purpose": "hook", "summary": "It happens.", "place": "",
            "setting": "", "assets": [], "sound": "", "kind": kind, "footage": "",
            "footage_at": 0, "shots": [{**shot, "at": at} for at in ats]}  # fmt: skip
    return {"treatment": {"hook": "h", "logline": "l", "why_it_holds": "w", "ending": "e"},
            "voices": [{"who": "Narrator", "sounds": "warm"}], "roles": [], "places": [],
            "clips": [clip]}  # fmt: skip


def test_a_script_line_of_several_sentences_is_one_line_on_the_clock():
    assert one_pass_timed.sentence_lines(SCRIPT) == [2, 2, 2, 4]
    assert one_pass_timed.clock(SCRIPT, {"lines": LINES}, True) == {2: (0.1, 4.0), 4: (4.3, 5.2)}
    assert one_pass_timed.heard(TRACK, 1.4, 2.8) == [2] and one_pass_timed.heard(
        TRACK, 4.3, 6.9) == [4]  # fmt: skip
    lyrics = "[Verse]\nUp we go [Lip-sync]\n\n[Chorus]\nAll the way"
    sung = [{"start": 1.0, "end": 2.0}, {"start": 3.0, "end": 4.0}]
    assert one_pass_timed.clock(lyrics, {"lines": sung}, False) == {2: (1.0, 2.0), 5: (3.0, 4.0)}


def test_an_at_lands_on_the_nearest_measured_start_and_the_first_on_zero():
    asked = {"script": SCRIPT, "cast": [], "assets": [], "timing": {"fast": 4.8, "pause": 0.2},
             "limits": {"min": 4, "max": 15, "people": 6}, "audio": TRACK}  # fmt: skip
    plan, fixes = one_pass.checked(asked, _plan([0.3, 1.5, 2.7, 4.2]))
    assert fixes == [] and plan["voices"] == []
    assert [s["at"] for s in plan["clips"][0]["shots"]] == [0.0, 1.4, 2.8, 4.3]
    assert plan["clips"][0]["kind"] == "broll"
    plan, fixes = one_pass.checked(asked, _plan([0.0, 0.2, 2.8, 2.9]))  # two start too soon
    assert fixes == [] and [s["at"] for s in plan["clips"][0]["shots"]] == [0.0, 2.8]


def test_a_clip_the_model_cannot_make_in_one_go_is_cut_where_a_shot_starts():
    asked = {"script": SCRIPT, "cast": ["Mia"], "assets": [], "timing": {"fast": 4.8, "pause": 0.2},
             "limits": {"min": 2, "max": 3, "people": 6}, "audio": TRACK}  # fmt: skip
    plan, fixes = one_pass.checked(asked, _plan([0.0, 1.4, 2.8, 4.3], people=["Mia"]))
    assert fixes == [] and [c["id"] for c in plan["clips"]] == ["c1", "c2", "c3"]
    assert [[s["at"] for s in c["shots"]] for c in plan["clips"]] == [[0.0, 1.4], [2.8], [4.3]]
    _, fixes = one_pass.checked(asked, _plan([0.0, 4.3]))  # one shot longer than a clip can be
    assert fixes == ["clip c1 shot 1 runs 4.3 s, and this video model makes 3 s a clip at most: "
                     "start another shot inside it, on a word's start from <song>"]  # fmt: skip


def test_a_narration_heard_saying_a_word_more_is_still_used(app, owner, db, monkeypatch):
    """Reed, 11 Nov (video 379): "In" was heard before the first line, the take was refused
    twice ("make it again") and the run stopped: a one-pass run has nobody to remake it."""
    from app.providers import fake_local

    heard = fake_local.hear_voice
    monkeypatch.setattr(fake_local, "hear_voice", lambda path, text: [
        {"word": "Quickly", "start": 0.0, "end": 0.1}, *heard(path, text)])  # fmt: skip
    pid = _delivered(app, owner, db)
    assert db.get(Project, pid).song_take_id


def test_a_narration_longer_than_its_voice_reads_at_once_is_read_in_parts_and_joined(
    app, owner, db, monkeypatch
):
    """Reed, 11 Nov: a 9,900-character script was refused by the default voice ("Request text
    length (9901) exceeds the maximum text length of 5000 characters") and the run stopped."""
    from app import narration
    from app.models.files import StoredFile

    monkeypatch.setitem(narration.MOST, narration.MODEL, 80)  # the stand-in refuses past it too
    pid = _delivered(app, owner, db)
    (voice,) = _jobs(db, "song_take")
    parts = voice.input["parts"]
    assert len(parts) == 2 and all(len(p) <= 80 for p in parts)
    assert " ".join(parts).split() == NARRATION.split()  # every word once, cut between sentences
    assert voice.input["input"]["voice"] == narration.VOICE  # the same voice, never another
    take = db.query(SongTake).one()
    assert take.id == db.get(Project, pid).song_take_id and take.file_id not in voice.output[
        "file_ids"]  # fmt: skip  # the joined track, not one part of it
    assert [x["text"] for x in take.timing["lines"]] == narration.sentences(NARRATION)
    assert db.get(StoredFile, take.file_id).size > 0 and all(x["heard"] for x in take.timing[
        "lines"])  # fmt: skip


def test_a_v3_note_opens_every_part_and_short_words_stay_one_request():
    from app import narration

    short = narration.job(NARRATION, note="clearly")
    assert narration.in_parts(short) == short and "parts" not in short
    long = narration.in_parts(narration.job("One two three. " * 400, note="clearly"))
    assert len(long["parts"]) == 2 and all(
        p.startswith("[clearly] One") and p.endswith("three.") and len(p) <= 5000
        for p in long["parts"])  # fmt: skip
    assert narration.characters(long) == len(long["input"]["prompt"])  # priced once, whole


def test_carry_on_after_a_failed_narration_reads_in_the_videos_own_voice(app, owner, db):
    """Reed, 11 Nov: after the stop he set the video's voice, and Carry on made the narration
    in the default voice again."""
    fs = owner.post("/freestyles", json={**BODY, "text": NARRATION + " fake:fail"})
    _run(app, db, ticks=8)
    pid = _video(db).id
    out = owner.get(f"/freestyles/{fs.json()['id']}").json()
    assert out["status"] == "stopped" and "narration didn't come out" in out["thread"][-1]["text"]
    assert {j.input["input"]["voice"] for j in _jobs(db, "song_take")} == {"Sarah"}
    set_voice = owner.post(f"/projects/{pid}/settings", json={"voice": "stock:Austin"})
    assert set_voice.status_code == 200, set_voice.text
    assert owner.post(f"/projects/{pid}/director/carry-on").status_code == 201
    _run(app, db, ticks=4)
    assert _jobs(db, "song_take")[-1].input["input"]["voice"] == "Austin"
