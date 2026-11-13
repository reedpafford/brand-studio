"""The one-pass director (app/one_pass.py), end to end on the stand-ins: one plan call, the
clips made straight from it, a free listen of each take, one watch of the cut. Every other
video keeps the step-by-step director."""

import io
import re
import wave
from decimal import Decimal

import pytest

from app import asks, clip_prompts, director, one_pass
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.providers import get_providers
from app.settings import get_settings
from app.worker import run_once
from tests.conftest import upload
from tests.helpers import make_it, ok_when_asked, product, with_sheet

SCRIPT = ("INT. KITCHEN - DAY\nMIA: The market opened at nine.\nLEO: And we were ready.\n"
          "INT. OFFICE - NIGHT\nMIA: Then it closed.\nLEO: We were not ready for that.\n"
          "EXT. STREET - DAY\nMIA: Tomorrow we open again.")  # fmt: skip
BODY = {"type": "dialogue", "look": "house", "shape": "9:16", "text": SCRIPT, "brand_id": 1}


@pytest.fixture(autouse=True)
def _one_pass_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "one_pass", True)


def _run(app, db, ticks=40, start=True):
    app.state.settings.fake_providers = True
    if not hasattr(app.state, "stand_ins"):  # one set a test: a take in flight is still known
        app.state.stand_ins = get_providers(app.state.settings, app.state.storage)
    providers = app.state.stand_ins
    for _ in range(ticks):
        run_once(db, providers, app.state.storage)
        db.expire_all()
        ok_when_asked(db)  # the person approves the cast and places when asked
        if start:  # Make it on each start card, as the owner
            make_it(db)


def _video(db) -> Project:
    return db.query(Project).execution_options(see_hidden=True).order_by(Project.id.desc()).first()


def _jobs(db, step: str) -> list[Job]:
    return db.query(Job).filter(Job.input["step"].as_string() == step).order_by(Job.id).all()


def _turns(db) -> list[tuple]:
    return [((j.output or {}).get("tool"), (j.output or {}).get("clip_id"),
             j.input.get("result")) for j in _jobs(db, "director")]  # fmt: skip


def _delivered(app, owner, db, **change) -> int:
    fs = owner.post("/freestyles", json={**BODY, **change})
    assert fs.status_code == 201, fs.text
    _run(app, db)
    out = owner.get(f"/freestyles/{fs.json()['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]]
    return _video(db).id


def test_a_dialogue_video_is_planned_in_one_call_and_delivered(app, owner, db):
    pid = _delivered(app, owner, db)
    assert db.get(Project, pid).engine == one_pass.ENGINE
    made = [(j.input.get("step") or j.kind, j.provider) for j in db.query(Job).order_by(Job.id)]
    assert [s for s, p in made if p == "claude" and s not in ("look_fit", "watch_cut")] == [
        "one_pass"
    ]  # one writing call: no turn, treatment, breakdown or clip prompts by a model
    assert {s for s, _ in made} & {"clip_prompts", "storyboard", "frame", "take_watch", "plan",
                                   "breakdown", "item_check"} == set()  # fmt: skip
    assert all(j.provider == "server" for j in _jobs(db, "director"))  # its turns: no call
    assert db.query(StoryboardFrame).count() == 0
    assert len(_jobs(db, "watch_cut")) == 1 and len(_jobs(db, "take_words")) == 3
    note = _jobs(db, "director")[-1].output["note"]
    assert note["clips"] == 3 and note["spent"] <= note["up_to"]
    assert "3 clips" in note["made"] and "tell me which clip" in note["needs"]


def test_every_clip_is_made_at_once(app, owner, db):
    _delivered(app, owner, db)
    takes = [(tool, clip, said) for tool, clip, said in _turns(db) if tool == "make_take"]
    assert takes == [("make_take", None, "Making 3 takes.")]  # no pilot clip first


def test_the_tabs_read_what_the_plan_made(app, owner, db):
    pid = _delivered(app, owner, db)
    plan = owner.get(f"/projects/{pid}/plan").json()
    assert plan["status"] == "approved" and len(plan["scenes"]) == 3
    assert [s["place"] for s in plan["scenes"]][0] == "INT. KITCHEN - DAY"
    clips = owner.get(f"/projects/{pid}/clips").json()
    assert [c["clip_id"] for c in clips] == ["c1", "c2", "c3"]
    assert all(not [p for p in c["problems"] if not p.startswith("Advice: ")] for c in clips)
    assert all(c["prompt"].count("Shot ") >= 1 and c["references"] for c in clips)
    cast = owner.get(f"/projects/{pid}/cast").json()
    assert {i["name"] for i in cast["items"]} >= {"Mia", "Leo", "INT. KITCHEN - DAY"}
    assert cast["state"] == "approved"
    thread = owner.get(f"/projects/{pid}/director").json()["thread"]
    assert any(t.get("treatment") and t["treatment"]["hook"] for t in thread)  # the chat's card
    spoken = [x.split(": ", 1)[1] for x in SCRIPT.splitlines() if re.match(r"[A-Z]+: ", x)]
    for line in spoken:  # each spoken line in exactly one clip's prompt, word for word
        assert sum(c["prompt"].count(f'"{line}"') for c in clips) == 1, line


BAR = "INT. BAR - NIGHT\nMIA: You came.\nLEO: I said I would.\nSAM: Nobody asked me."


def test_on_omni_a_third_person_is_in_words_and_two_sheets_are_sent(app, owner, db, monkeypatch):
    from app import guides

    monkeypatch.setitem(guides.style("movie"), "video_model", "gemini-omni-1.2")
    _delivered(app, owner, db, look="movie", text=BAR)
    take = _jobs(db, "clip_take")[0]
    assert take.input["model"] == "gemini-omni-1.2"
    row = db.query(ProjectClip).one()
    people = [r["id"] for r in row.references if r["id"].startswith("char:")]
    assert len(people) == 3  # everyone the clip shows is on the clip
    sent = take.input["files"]["reference_images"]
    assert len(sent) == 3 and len(take.input["unsent"]) == 1  # two people and the place
    assert "Sam" in take.input["input"]["prompt"] and '"Nobody asked me."' in take.input[
        "input"]["prompt"]  # fmt: skip
    assert "The third image is the place" in take.input["input"]["prompt"]  # in words


def test_on_kies_seedance_everyone_is_sent_on_a_sheet_seedream_drew(app, owner, db, monkeypatch):
    """Reed, 12 Nov: Seedance takes a real-looking face only on a sheet Seedream drew from
    words. So a real-looking video's people are drawn by it (wide, with a large portrait) and
    its place by Nano Banana, every person's sheet reaches the clip, and one whose sheet
    Seedream didn't draw (from a photo, or an older one) is said in words instead."""
    from app import guides
    from app.clip_takes import take_input
    from app.models.library import LibraryItem

    monkeypatch.setitem(guides.style("movie"), "video_model", "seedance-2.5-kie")
    pid = _delivered(app, owner, db, look="movie", text=BAR)
    sheets = {db.get(LibraryItem, j.input["library_item_id"]).name: j for j in _jobs(db, "sheet")}
    drawn = {who: (j.input["model"], j.input["input"]["aspect_ratio"]) for who, j in sheets.items()}
    assert drawn == {"INT. BAR - NIGHT": ("nano-banana-pro", "16:9"),
                     **dict.fromkeys(("Mia", "Leo", "Sam"), ("seedream-5.5", "16:9"))}  # fmt: skip
    take = _jobs(db, "clip_take")[0]
    said = take.input["input"]["prompt"].splitlines()
    assert take.input["model"] == "seedance-2.5-kie"
    assert len(take.input["files"]["reference_images"]) == 4 and take.input["unsent"] == ["frame:"]
    assert said[0] == "Scene context: A plain test scene."
    assert said[1:5] == [
        *(f"[Image{n}] is {who}: their face, hair and outfit."
          for n, who in enumerate(("Mia", "Leo", "Sam"), 1)),
        "[Image4] is the place, INT. BAR - NIGHT: use it for the place, its light and colour, "
        "not for framing."]  # fmt: skip
    assert said[5] == ("Shot 1, 0-2 s: Medium shot. Mia says line 2 to the room. Only in frame: "
                       'Mia. Mia says, plainly: "You came."')  # fmt: skip
    assert said[-2].startswith("Look: Photoreal TV-drama footage") and len(said) == 10
    assert said[-1].startswith("Sound: Room tone. Voices: Mia, a plain test voice")
    assert said[-1].endswith("No music, no subtitles.")
    sheets["Sam"].input = {**sheets["Sam"].input, "model": "nano-banana-pro"}
    db.commit()
    again = take_input(db, db.get(Project, pid), db.query(ProjectClip).one(), check=False)
    sam = f"char:{sheets['Sam'].input['library_item_id']}"
    assert len(again["files"]["reference_images"]) == 3 and again["unsent"] == [sam, "frame:"]
    assert "[Image2] is Leo: their face, hair and outfit. Sam (" in again["input"]["prompt"]
    assert "[Image3] is the place, INT. BAR - NIGHT: use it" in again["input"]["prompt"]


def test_a_skipped_line_is_asked_for_again_inside_the_same_job(app, owner, db, monkeypatch):
    from app.providers.fake_local import FakeWriter

    asked, real = [], FakeWriter._one_pass
    monkeypatch.setattr(FakeWriter, "_one_pass", lambda self, p: asked.append(p) or real(self, p))
    pid = _delivered(app, owner, db, text=SCRIPT + "\n[fake:skip-line]")
    assert len(asked) == 2 and "<fix>" in asked[1] and "line 8 is in no shot" in asked[1]
    assert len(_jobs(db, "one_pass")) == 1  # one job, charged once
    clips = owner.get(f"/projects/{pid}/clips").json()
    assert sum(c["prompt"].count('"Tomorrow we open again."') for c in clips) == 1


def test_a_plan_that_still_misses_a_line_shows_nothing_and_says_what_to_do(app, owner, db):
    fs = owner.post("/freestyles", json={**BODY, "text": SCRIPT + "\n[fake:skip-line-twice]"})
    _run(app, db, ticks=8)
    pid = _video(db).id
    plans = _jobs(db, "one_pass")
    assert [j.status for j in plans] == ["failed", "failed"]  # tried once more, then it stops
    assert plans[0].error_detail == f"{one_pass.STILL}line 8 is in no shot"
    assert not _jobs(db, "treatment") and not db.query(ProjectClip).count()
    assert owner.get(f"/projects/{pid}/plan").status_code == 204
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] != "running" and out["ended"] == (
        "It stopped: the plan couldn't be made (twice running its answer had this wrong: line 8 "
        "is in no shot). Start it again to try once more, or change the script first.")  # fmt: skip
    assert fs.json()["id"]


def test_a_take_that_misses_a_line_is_made_once_more_with_the_same_prompt(app, owner, db):
    pid = _delivered(app, owner, db, text=SCRIPT + "\n[fake:drop-line]")
    takes = db.query(ClipTake).join(ProjectClip, ClipTake.clip_id == ProjectClip.id).filter(
        ProjectClip.clip_id == "c1").order_by(ClipTake.number).all()  # fmt: skip
    assert len(takes) == 2 and takes[0].prompt == takes[1].prompt  # once more, the same prompt
    assert db.query(ClipTake).count() == 4  # and never a third: the others made once
    first, again = [j for j in _jobs(db, "clip_take") if j.input["project_clip_id"] ==
                    takes[0].clip_id]  # fmt: skip
    assert first.input["input"] == again.input["input"]
    note = _jobs(db, "director")[-1].output["note"]
    assert any("And we were ready." in x for x in note["open"])  # the second miss: said
    assert "made it once more" in note["made"]
    assert db.get(Project, pid).engine == one_pass.ENGINE


def test_the_one_pass_directors_cut_needs_no_clip_approved(app, owner, db):
    """Reed, 11 Nov (video 370): a real-footage clip's prompt had problems, so it was never
    approved, the director's cut was refused for it, and the run stopped at every Carry on."""
    from app import cut
    from app.routes.jobs import DIRECTOR_TOOL

    project = db.get(Project, _delivered(app, owner, db))
    db.query(ProjectClip).update({"approved": False})
    token = DIRECTOR_TOOL.set(True)
    try:
        cut.ready(db, project, app.state.storage)  # never "Approve every clip"
    finally:
        DIRECTOR_TOOL.reset(token)


def test_a_note_after_delivery_remakes_only_the_clip_it_names(app, owner, db):
    pid = _delivered(app, owner, db)
    before = {r.clip_id: (r.picked_take_id, r.prompt) for r in db.query(ProjectClip)}
    said = owner.post(f"/projects/{pid}/director/messages",
                      json={"text": "Redo clip 3 with a wider shot."})  # fmt: skip
    assert said.status_code == 201, said.text
    _run(app, db)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    after = {r.clip_id: (r.picked_take_id, r.prompt) for r in db.query(ProjectClip)}
    assert after["c1"] == before["c1"] and after["c2"] == before["c2"]  # as they were
    assert after["c3"][0] != before["c3"][0] and "Made again" in after["c3"][1]
    assert db.query(ClipTake).count() == 4 and len(_jobs(db, "one_pass")) == 2
    assert db.query(FinalVideo).order_by(FinalVideo.id.desc()).first().number == 2
    note = _jobs(db, "director")[-1].output["note"]
    assert "clip 3 again" in note["made"] and note["cut"] == 2
    assert all(m["answered"] for m in out["thread"] if m["kind"] == "message")


def test_a_double_tap_on_new_video_makes_one_video(app, owner, db):
    """A one-pass run's opening turn is born succeeded, so the same send again inside ten
    seconds found nothing waiting and made a second video ("Make without asking" ran both)."""
    first, again = (owner.post("/freestyles", json={**BODY, "mode": "auto"}).json() for _ in "ab")
    assert first["id"] == again["id"] and db.query(Project).count() == 1
    assert len(_jobs(db, "one_pass")) == 1  # one plan asked for, not two
    other = owner.post("/freestyles", json={**BODY, "text": SCRIPT + "\nMIA: One more."}).json()
    assert other["id"] != first["id"]  # other words are another video


def test_a_step_that_breaks_ends_the_run_saying_so(app, owner, db, monkeypatch):
    """A turn whose step threw was left succeeded with no result: nothing wakes that, so the
    video showed "working" for good. It ends in plain words, with Carry on to try again."""

    def boom(*a, **k):
        raise KeyError("clips")

    monkeypatch.setattr("app.director_tools.run", boom)  # the first site action: its looks
    owner.post("/freestyles", json=BODY)
    _run(app, db, ticks=12)
    out = owner.get(f"/projects/{_video(db).id}/director").json()
    assert (out["status"], out["ended"]) == ("ended", director.BROKE)
    assert not db.query(ClipTake).count() and out["carry_on"]


def test_one_videos_fault_never_holds_up_the_sweep_for_the_others(app, owner, db, monkeypatch):
    for more in ("", "\nMIA: And again."):
        owner.post("/freestyles", json={**BODY, "text": SCRIPT + more})
    _run(app, db, ticks=2, start=False)
    woken = []

    def wake(db, project):
        woken.append(project.id)
        if len(woken) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(director, "wake", wake)
    director.sweep(db)
    assert len(set(woken)) == 2  # the second video's run still got its look


def test_the_start_card_shows_what_one_run_can_charge_and_the_run_stays_inside_it(app, owner, db):
    fs = owner.post("/freestyles", json={**BODY, "mode": "ask"})
    _run(app, db, ticks=6, start=False)  # its plan and its looks, then its start card
    project = _video(db)
    (card,) = [j for j in _jobs(db, "director") if j.input.get(asks.START)]
    assert card.status == "needs_owner_approval"
    rows = db.query(ProjectClip).all()
    assert len(rows) == 3 and not db.query(ClipTake).count()  # nothing made before Make it
    from app import watch_cut
    from app.clip_takes import takes_price
    from app.credits import estimate

    plan = sum((j.credits for j in _jobs(db, "one_pass")), Decimal(0))
    look = estimate(db, project.workspace_id, watch_cut.KIND, Decimal(1), {})
    watch = look * one_pass._watch_units(project, sum(r.seconds for r in rows), 3)
    assert asks.run_price(db, project) == plan + 2 * takes_price(db, project, rows) + watch
    make_it(db)
    _run(app, db)
    assert owner.get(f"/freestyles/{fs.json()['id']}").json()["status"] == "delivered"
    price, spent = asks.approved_run(db, project)
    assert spent <= price and not db.query(Job).filter(
        Job.status == "needs_owner_approval").count()  # fmt: skip


def test_every_other_video_keeps_the_step_by_step_director(app, owner, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "one_pass", False)  # the switch for new videos
    owner.post("/freestyles", json=BODY)
    _run(app, db, ticks=3, start=False)
    assert _video(db).engine is None and _jobs(db, "treatment")[0].provider == "claude"
    monkeypatch.setattr(get_settings(), "one_pass", True)
    pid = _video(db).id  # a video with earlier turns never changes engine
    owner.post(f"/projects/{pid}/director/stop")
    owner.post(f"/projects/{pid}/director")
    assert _video(db).engine is None and not _jobs(db, "one_pass")
    monkeypatch.setattr(get_settings(), "one_pass_engines", ["dialogue"])  # a format left out
    narrated = owner.post("/freestyles", json={**BODY, "type": "narrated",
                                               "text": "The market opened at nine."})  # fmt: skip
    assert narrated.status_code == 201, narrated.text
    _run(app, db, ticks=3, start=False)
    assert _video(db).engine is None and not _jobs(db, "one_pass")


def test_stop_then_carry_on_makes_no_claude_turn(app, owner, db):
    owner.post("/freestyles", json=BODY)
    _run(app, db, ticks=5)  # past Make it, into the takes
    pid = _video(db).id
    assert owner.post(f"/projects/{pid}/director/stop").json()["ended"] == "Stopped."
    _run(app, db, ticks=4, start=False)
    assert owner.post(f"/projects/{pid}/director/carry-on").status_code == 201
    _run(app, db)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", (out["ended"], _turns(db))
    assert all(j.provider == "server" for j in _jobs(db, "director"))
    assert len(_jobs(db, "one_pass")) == 1 and db.query(ClipTake).count() == 3  # nothing twice
    assert len({j.input[director.RUN]["id"] for j in _jobs(db, "director")}) == 1  # the same run


def test_a_saved_person_plays_only_the_role_they_are_picked_for_and_no_saved_place_is_offered(
        app, owner, db):  # fmt: skip
    """Reed, 13 Nov: a saved person is used only when picked at the script, never matched by
    name, and "Places follow the same rule" (nothing picks a place, so a video's are drawn for
    it; on 11 Nov a brand place nobody had drawn stalled videos 373 and 383)."""
    from app.models.brands import Brand
    from app.models.library import Kind, LibraryItem

    brand = db.get(Brand, 1)
    place, maya, leo = (LibraryItem(workspace_id=1, kind=kind, name=name, brands=[brand],
                                    image_file_ids=[upload(owner)])
                        for kind, name in ((Kind.place, "Kitchen"), (Kind.character, "Maya"),
                                           (Kind.character, "Leo")))  # fmt: skip
    db.add_all([place, maya, leo])
    db.commit()
    for item in (place, maya, leo):
        with_sheet(db, item.id)
    sent = owner.post("/freestyles", json={**BODY, "cast": [{"role": "MIA", "item_id": maya.id}]})
    assert sent.status_code == 201, sent.text
    _run(app, db)
    video = _video(db)
    (plan,) = _jobs(db, "one_pass")
    assert f"place:{place.id}" not in plan.input["assets"]  # though it has a picture
    assert maya.id in video.cast_ids and leo.id not in video.cast_ids
    assert maya.id in video.slot_cast.values() and leo.id not in video.slot_cast.values()
    shots = [s for scene in clip_prompts.newest(db, video).data["scenes"] for s in scene["shots"]]
    said = {s["speaker"]: s["character_ids"] for s in shots if s["speaker"]}
    assert said["Mia"] == [f"char:{maya.id}"]  # Maya plays Mia: picked, whatever her name
    assert f"char:{leo.id}" not in str(said["Leo"])  # a saved Leo nobody picked is not used


def test_the_picked_products_reach_the_plan_call(app, owner, db):
    item = product(db, 1, "Peanut butter bag")
    db.commit()
    sent = owner.post("/freestyles", json={**BODY, "product_ids": [item]})
    assert sent.status_code == 201, sent.text
    _run(app, db, ticks=2, start=False)
    asked = _jobs(db, "one_pass")[0].input
    assert f"prop:{item} | Peanut butter bag" in asked["prompt"] and "<products>" in asked["prompt"]
    assert "Planning for this model" in asked["prompt"]  # the video model's own notes
    assert "## Producer craft" in asked["system"][0] and "## Style: House" in asked["system"][0]


def test_an_editors_send_waits_for_the_owner_with_only_its_plan_made(app, owner, editor, db):
    fs = editor.post("/freestyles", json=BODY)
    assert fs.status_code == 201, fs.text
    _run(app, db, ticks=5, start=False)
    assert editor.get(f"/freestyles/{fs.json()['id']}").json()["status"] == "waiting"
    made = {j.input.get("step") or j.kind for j in db.query(Job).filter(Job.status == "succeeded")}
    assert made == {"director", "one_pass", "treatment"}  # no look, no take before the owner's OK
    (held,) = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    assert owner.post(f"/jobs/{held['id']}/approve").status_code == 200
    _run(app, db)
    out = editor.get(f"/freestyles/{fs.json()['id']}").json()
    assert out["status"] == "delivered", [t["text"] for t in out["thread"]]
    asked = [said for tool, _, said in _turns(db) if tool == "ask_cast_ok"]
    assert len(asked) == 1 and asked[0].startswith("Asked for the cast and places OK")


def test_the_old_planning_presses_say_where_a_one_pass_video_is_changed(app, owner, db):
    pid = _delivered(app, owner, db)
    for press in (owner.post(f"/projects/{pid}/plan"), owner.post(f"/projects/{pid}/breakdown")):
        assert press.status_code == 409 and one_pass.CHAT in press.json()["detail"]
    assert owner.post(f"/projects/{pid}/clips/prompts").status_code == 409  # none to rewrite
    assert not _jobs(db, "plan") and not _jobs(db, "breakdown") and not _jobs(db, "clip_prompts")
    assert owner.get(f"/projects/{pid}").json()["engine"] == "one_pass"
    steps = [s["key"] for s in owner.get(f"/projects/{pid}/director/progress").json()["steps"]]
    assert "stills" not in steps and "prompts" not in steps and steps[-1] == "cut"


def test_a_note_while_the_start_card_waits_changes_the_plan_first(app, owner, db):
    fs = owner.post("/freestyles", json={**BODY, "mode": "ask"})
    _run(app, db, ticks=6, start=False)
    pid = _video(db).id
    (card,) = [j for j in _jobs(db, "director") if j.input.get(asks.START)]
    said = owner.post(f"/projects/{pid}/director/messages", json={"text": "Open clip 2 wider."})
    assert said.status_code == 201, said.text
    _run(app, db, ticks=6, start=False)
    db.refresh(card)
    assert card.status == "cancelled" and len(_jobs(db, "one_pass")) == 2  # planned again
    asked = _jobs(db, "one_pass")[1].input["prompt"]
    assert "<notes>\nNote 1: Open clip 2 wider.\n</notes>" in asked and "<plan>" in asked
    rows = {r.clip_id: r.prompt for r in db.query(ProjectClip)}
    assert "Made again as the note asks." in rows["c2"] and not db.query(ClipTake).count()
    (again,) = [j for j in _jobs(db, "director") if j.input.get(asks.START) and j.id != card.id]
    assert again.status == "needs_owner_approval"  # its start card is back, for the new plan
    make_it(db)
    _run(app, db)
    assert owner.get(f"/freestyles/{fs.json()['id']}").json()["status"] == "delivered"


def test_a_plan_that_cannot_be_saved_leaves_nothing_and_stops_after_one_more_try(
    app, owner, db, monkeypatch
):
    monkeypatch.setattr(one_pass, "to_breakdown", lambda *a: 1 / 0)  # its save breaks half way
    owner.post("/freestyles", json=BODY)
    _run(app, db, ticks=8)
    plans = _jobs(db, "one_pass")
    assert [(j.status, j.error) for j in plans] == [("failed", "Its answer couldn't be saved.")] * 2
    assert not _jobs(db, "treatment") and not db.query(ProjectClip).count()  # none of it kept
    out = owner.get(f"/projects/{_video(db).id}/director").json()
    assert out["ended"].startswith("It stopped: the plan couldn't be made (it was written but")


def test_the_treatment_card_gives_each_beat_its_clips_real_span(app, owner, db):
    pid = _delivered(app, owner, db)
    thread = owner.get(f"/projects/{pid}/director").json()["thread"]
    card = next(t["treatment"] for t in thread if t.get("treatment"))
    rows = db.query(ProjectClip).order_by(ProjectClip.id).all()
    ends = [sum(r.seconds for r in rows[: k + 1]) for k in range(len(rows))]
    spans = list(zip([0, *ends[:-1]], ends, strict=True))  # 0-5, 5-9, 9-16: each clip's own
    assert [(b["start"], b["end"]) for b in card["beats"]] == spans


def test_the_run_card_and_header_never_speak_of_stills_or_ask_for_make_it_once_delivered(
    app, owner, db
):
    owner.post("/freestyles", json={**BODY, "mode": "ask"})
    _run(app, db, ticks=6, start=False)
    pid = _video(db).id
    card = owner.get(f"/projects/{pid}/director/progress").json()
    assert (card["title"], card["sub"]) == ("Ready to make", "No clips yet: press Make it")
    make_it(db)
    _run(app, db)
    done = owner.get(f"/projects/{pid}/director/progress").json()
    assert done["status"] == "delivered" and done["title"].startswith("Made in")
    assert done["sub"] == "3 clips" and done["made"] == 3
    run = owner.get(f"/projects/{pid}/director").json()
    assert run["started"] and run["make_it"] is None and run["status"] == "delivered"
    head = owner.get(f"/projects/{pid}/idea").json()
    assert head["status"]["kind"] == "delivered"
    assert "still" not in str(done).lower() + str(head).lower()


def test_a_line_with_quotes_of_its_own_reaches_the_take_word_for_word(app, owner, db):
    line = 'He said "five minutes" an hour ago.'
    text = f"INT. HALL - DAY\nMOM: {line}\nKID (V.O.): And you waited?"
    pid = _delivered(app, owner, db, text=text)
    (clip,) = owner.get(f"/projects/{pid}/clips").json()
    assert f'Only in frame: Mom. Mom (in English, plainly): "{line}"' in clip["prompt"]
    # a line the script marks (V.O.) is heard, never mouthed, whatever the plan said of it
    assert 'Kid (in English, voice-over, lips closed, plainly): "And you' in clip["prompt"]
    assert not [p for p in clip["problems"] if not p.startswith("Advice: ")]
    shots = owner.get(f"/projects/{pid}/breakdown").json()["breakdown"]["scenes"][0]["shots"]
    assert shots[0]["line"] == line
    (take,) = _jobs(db, "clip_take")
    assert f'"{line}"' in take.input["input"]["prompt"]
    heard = _jobs(db, "take_words")[0].input["lines"]
    assert heard[0]["text"] == line


def test_a_note_while_takes_are_being_made_waits_for_them_then_changes_only_its_clip(
    app, owner, db
):
    fs = owner.post("/freestyles", json=BODY)
    for _ in range(40):  # Make it, then on until the pilot is out and the others are in flight
        _run(app, db, ticks=1)
        if len(_jobs(db, "clip_take")) == 3:
            break
    pid = _video(db).id
    flying = [j.id for j in _jobs(db, "clip_take") if j.status != "succeeded"]
    assert flying, "the note has to land while a take is being made"
    said = owner.post(f"/projects/{pid}/director/messages", json={"text": "Redo clip 2 wider."})
    assert said.status_code == 201 and len(_jobs(db, "one_pass")) == 1  # nothing planned yet
    _run(app, db)
    assert owner.get(f"/freestyles/{fs.json()['id']}").json()["status"] == "delivered"
    first, again = _jobs(db, "one_pass")
    takes = _jobs(db, "clip_take")
    assert again.created_at >= max(j.finished_at for j in takes[:3])  # after what was in flight
    assert all(j.status == "succeeded" for j in takes) and len(takes) == 4  # none thrown away
    made = {r.clip_id: db.query(ClipTake).filter_by(clip_id=r.id).count()
            for r in db.query(ProjectClip)}  # fmt: skip
    assert made == {"c1": 1, "c2": 2, "c3": 1}  # only the clip the note names, made again
    assert db.query(FinalVideo).count() == 1  # one cut, with the new take in it


def test_make_it_again_on_a_delivered_video_buys_nothing(app, owner, db):
    pid = _delivered(app, owner, db)
    assert owner.post(f"/projects/{pid}/director").status_code == 201  # Make it again
    _run(app, db)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered" and "nothing needed making again" in out["ended"].lower()
    assert db.query(ClipTake).count() == 3 and len(_jobs(db, "one_pass")) == 1  # nothing bought
    assert all(j.provider == "server" for j in _jobs(db, "director"))


def test_the_owner_keeping_the_plan_leaves_the_video_as_it_was(app, owner, db, monkeypatch):
    from app.models.asks import Ask

    pid = _delivered(app, owner, db)
    before = {r.clip_id: (r.picked_take_id, r.prompt) for r in db.query(ProjectClip)}
    monkeypatch.setattr(get_settings(), "plan_credits_before_ok", 0.0)  # its re-plan needs an OK
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Redo clip 3 wider."})
    _run(app, db, ticks=4, start=False)
    held = _jobs(db, "one_pass")[-1]
    assert held.status == "needs_owner_approval" and held.input["held"] == asks.PLANNING
    card = next(a for a in db.query(Ask).filter_by(project_id=pid) if held.id in (a.job_ids or []))
    assert owner.post(f"/asks/{card.id}/answer", json={"how": "keep"}).status_code == 200
    _run(app, db)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered" and out["ended"].startswith("The plan stays as it is")
    assert {r.clip_id: (r.picked_take_id, r.prompt) for r in db.query(ProjectClip)} == before
    assert db.query(ClipTake).count() == 3 and db.query(FinalVideo).count() == 1
    assert [j.status for j in _jobs(db, "one_pass")] == ["succeeded", "cancelled"]


def test_a_video_model_its_planned_clips_dont_fit_is_refused_with_the_way_on(app, owner, db):
    long = " ".join(["word"] * 60)  # a 21 s shot: fine on Seedance 2.5, too long for Omni 1.2
    pid = _delivered(app, owner, db, text=f"INT. HALL - DAY\nMOM: {long}\nKID: Fine.")
    no = owner.post(f"/projects/{pid}/settings", json={"video_model": "gemini-omni-1.2"})
    seconds = db.query(ProjectClip).first().seconds
    assert no.status_code == 409 and no.json()["detail"] == one_pass.UNFIT.format(
        n=1, s=seconds, model="Gemini Omni 1.2", low=3, high=15)  # fmt: skip
    assert db.get(Project, pid).video_model is None
    yes = owner.post(f"/projects/{pid}/settings", json={"video_model": "seedance-2.5"})
    assert yes.status_code == 200, yes.text  # a model every planned clip fits: switched


def test_a_screen_the_clip_names_is_attached_whichever_shot_shows_it(app, owner, db, monkeypatch):
    from app.providers.fake_local import FakeWriter, _tag

    real = FakeWriter._one_pass

    def with_screen(self, prompt):
        plan = real(self, prompt)
        screen = re.search(r"^(screen:\d+) \|", _tag(prompt, "assets"), re.M)[1]
        plan["clips"][0]["assets"] = [screen]  # the clip's, though only its last shot shows it
        plan["clips"][0]["shots"][-1]["action"] = "Leo holds the phone up to the lens."
        return plan

    monkeypatch.setattr(FakeWriter, "_one_pass", with_screen)
    added = owner.post("/brands/1/screens", json={"name": "Home", "file_id": upload(owner)})
    assert added.status_code == 201, added.text
    pid = _delivered(app, owner, db)
    clip = owner.get(f"/projects/{pid}/clips").json()[0]
    (screen,) = [r["id"] for r in clip["references"] if r["id"].startswith("screen:")]
    n = [r["id"] for r in clip["references"]].index(screen) + 1
    assert f"[Image{n}] is the " in clip["prompt"] and "screen: keep its UI" in clip["prompt"]
    take = _jobs(db, "clip_take")[0]
    assert len(take.input["files"]["reference_images"]) == len(clip["references"])
    assert take.input["exact_file_ids"]  # sent as given, never lossy (rules 13 and 14)


def test_a_look_that_failed_while_the_picture_service_was_down_is_drawn_after_carry_on(
    app, owner, db
):
    """Reed, 11 Nov (video 379): every sheet failed for an hour (the provider's fault), the run
    stopped, and Carry on never drew them again: "needs a look and couldn't be drawn"."""
    app.state.settings.fake_providers = True
    app.state.stand_ins = providers = get_providers(app.state.settings, app.state.storage)
    real = providers["replicate"].submit

    def down(kind, input):
        if input.get("step") == "sheet":
            raise RuntimeError("the picture service is down")
        return real(kind, input)

    providers["replicate"].submit = down
    fs = owner.post("/freestyles", json=BODY).json()
    _run(app, db)
    pid = _video(db).id
    assert "failed" in owner.get(f"/projects/{pid}/director").json()["ended"]  # it stopped
    assert owner.post(f"/projects/{pid}/director/carry-on").status_code == 201  # still down
    _run(app, db)
    providers["replicate"].submit = real  # the service is back
    assert owner.post(f"/projects/{pid}/director/carry-on").status_code == 201
    _run(app, db)
    out = owner.get(f"/projects/{pid}/director").json()
    assert owner.get(f"/freestyles/{fs['id']}").json()["status"] == "delivered", (
        out["ended"],
        [(t["tool"], t["result"]) for t in out["turns"]],
    )


def test_a_cut_that_is_refused_stops_saying_why(app, owner, db, monkeypatch):
    """Reed, 11 Nov (video 370): the cut was refused ("Approve every clip to make the video")
    and the run stopped saying only "a clip changed since"."""
    from fastapi import HTTPException

    def refuse(**_):
        raise HTTPException(409, "Clip 2 has no take to cut with.")

    monkeypatch.setattr("app.routes.cut.make", refuse)
    owner.post("/freestyles", json=BODY)
    _run(app, db)
    out = owner.get(f"/projects/{_video(db).id}/director").json()
    assert out["ended"] == one_pass.CUT_FAILED.format("Clip 2 has no take to cut with")


def test_a_take_the_service_refuses_stops_the_run_naming_its_clip(app, owner, db, monkeypatch):
    from app.providers import Result
    from app.providers.fake_local import FakeMedia
    from tests.test_clip_takes import E006

    real = FakeMedia.poll

    def poll(self, ref):  # the office clip's take is refused on its content, every time
        job = self._jobs[ref]
        refused = job["kind"] == "video" and "Then it closed." in job.get("prompt", "")
        return Result("failed", error=E006) if refused else real(self, ref)

    monkeypatch.setattr(FakeMedia, "poll", poll)
    owner.post("/freestyles", json=BODY)
    _run(app, db)
    ended = owner.get(f"/projects/{_video(db).id}/director").json()["ended"]
    assert ended.startswith("It stopped: This same prompt for clip 2 was blocked by the service")


def test_two_people_who_share_every_clip_are_never_taken_for_one(app, owner, db):
    """Reed, 11 Nov (videos 377, 379, 383): "These may be the same person" on Paige and the
    man following her, on a young woman and a detective, on a girl and the first man (nobody
    speaks on camera in a song or a narrated video). The flagged one's look was never drawn
    and its clips never made, until a person said so."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.cast_roles import ref, video_slots
    from app.routes.project_assets import _flagged, _newest

    project = db.get(Project, _delivered(app, owner, db))
    mia, leo = video_slots(db, project)
    row, both = _newest(db, project), [ref(db, project, mia), f"slot:{leo.id}"]
    for shot in (x for sc in row.data["scenes"] for x in sc["shots"]):  # Leo: no look yet,
        shot["speaker"] = None  # and only ever seen beside Mia
        shot["character_ids"] = both if shot["character_ids"] else []
    flag_modified(row, "data")
    project.slot_looks = {str(mia.id): project.slot_looks[str(mia.id)]}
    db.commit()
    assert _flagged(db, project) == set()


def test_stop_cancels_the_looks_not_yet_drawn_and_carry_on_draws_them(app, owner, db):
    """Video 391 (11 Nov): Stop while its 17 looks were queued, and 11 were still drawn and
    billed after it. Stop now cancels the video's paid work that hasn't started; Carry on
    makes it."""
    from app.models.jobs import JobStatus

    owner.post("/freestyles", json=BODY)
    app.state.settings.fake_providers = True
    app.state.stand_ins = providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(12):  # the plan, then its looks are queued: stop before the worker takes them
        run_once(db, providers, app.state.storage)
        db.expire_all()
        if queued := db.query(Job).filter(Job.input["step"].as_string() == "sheet",
                                          Job.status == JobStatus.queued).count():  # fmt: skip
            break
    pid = _video(db).id
    assert queued and owner.post(f"/projects/{pid}/director/stop").json()["ended"] == "Stopped."
    db.expire_all()
    left = db.query(Job).filter(Job.project_id == pid, Job.status == JobStatus.queued,
                                Job.credits > 0).count()  # fmt: skip
    assert left == 0
    assert owner.post(f"/projects/{pid}/director/carry-on").status_code == 201
    _run(app, db)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", (out["ended"], _turns(db))


def test_words_a_take_adds_to_the_script_are_silenced_free_before_the_cut(app, owner, db):
    """Video 390 (11 Nov): the presenter finished his line early and made up a sentence ("If
    I have to hear about another detention, then I'm going to change"). The listen found it,
    and it was delivered with a note. Now that stretch is muted, as the Mute button does."""
    from app.providers import fake_local

    app.state.settings.fake_providers = True
    app.state.stand_ins = providers = get_providers(app.state.settings, app.state.storage)
    real, more = providers["local"].hear_take, "Cannot believe it worked."

    def hear(path, job):  # every take says a sentence more, after its lines
        heard = real(path, job)
        at = heard[-1]["end"] + 0.5 if heard else 0.5
        return [*heard, {"start": at, "end": at + 1, "text": more, "speaker": None,
                         "words": fake_local._spread(more, at, at + 1)}]  # fmt: skip

    providers["local"].hear_take = hear
    _delivered(app, owner, db)
    muted = [said for tool, _, said in _turns(db) if tool == "mute"]
    assert muted and all(said.startswith("Muted a stretch") for said in muted), _turns(db)
    assert all((t.made_with or {}).get("mutes") for t in db.query(ClipTake))
    assert db.query(ClipTake).count() == 3  # nothing was made again for it


def test_each_speakers_voice_is_kept_from_one_clip_and_sent_with_their_others(
        app, owner, db, monkeypatch):  # fmt: skip
    """Movie Ad 1 (Reed, 13 Nov): the voices held once later clips were sent a few seconds of
    each person from an earlier one. The clip with each speaker's longest line is made first,
    their voice is cut from its take once it's listened to, and the rest are made with it."""
    from app import clip_prompts, guides, voice_carry
    from app.models.files import StoredFile
    from app.models.library import LibraryItem

    monkeypatch.setitem(guides.style("movie"), "video_model", "seedance-2.5-kie")
    cuts, wav = [], io.BytesIO()
    with wave.open(wav, "wb") as w:  # the stand-in takes have no sound of their own to cut
        w.setparams((1, 2, 44100, 0, "NONE", ""))
        w.writeframes(bytes(88200))
    monkeypatch.setattr(voice_carry, "_cut", lambda v, a, b: cuts.append((a, b)) or wav.getvalue())
    _delivered(app, owner, db, look="movie")
    made = [j.output for j in _jobs(db, "director") if j.output["tool"] == "make_take"]
    assert [m.get("first") for m in made] == [["c1", "c2"], None]  # Mia's and Leo's longest lines
    assert made[0]["why"] == one_pass.VOICES_FIRST
    asked = [j for j in _jobs(db, "director") if j.output["tool"] == "ask_cast_ok"]
    assert not asked  # a kept voice is no change to the cast: its OK isn't asked again (406)
    first, second, last = (j.input for j in _jobs(db, "clip_take"))
    assert "reference_audios" not in first["files"] and "[Audio" not in first["input"]["prompt"]
    assert "reference_audios" not in second["files"]
    mia, leo = (db.query(LibraryItem).filter_by(name=n).one() for n in ("Mia", "Leo"))
    assert db.get(StoredFile, mia.voice_file_id).filename == "Mia voice.wav"
    assert cuts == [(0.4, 2.12), (1.98, 4.0)] and leo.voice_file_id  # each line as it was heard
    assert last["files"]["reference_audios"] == [mia.voice_file_id]  # only Mia speaks in clip 3
    assert last["input"]["prompt"].splitlines()[-1] == (
        "[Audio1] is a recording of Mia's voice: match its tone and accent for Mia only. It is "
        "a sample of the voice; the words said are this clip's quoted lines.")  # fmt: skip
    data = clip_prompts.newest(db, _video(db)).data  # without clip 1 Leo is heard in one clip:
    mia.voice_file_id = leo.voice_file_id = None  # nowhere to carry his voice, so it isn't first
    assert voice_carry.first(db, _video(db), {**data, "clips": data["clips"][1:]}) == ["c3"]


def test_a_voice_that_cannot_be_cut_never_stops_the_run(app, owner, db, monkeypatch, tmp_path):
    """The stand-in takes have no sound to cut: every clip is still made and delivered. A real
    take's piece comes out as a WAV, and a line barely heard gives no sample."""
    import subprocess

    from app import guides, voice_carry
    from app.models.library import LibraryItem

    monkeypatch.setitem(guides.style("movie"), "video_model", "seedance-2.5-kie")
    _delivered(app, owner, db, look="movie")
    assert len(_jobs(db, "clip_take")) == 3
    assert not db.query(LibraryItem).filter(LibraryItem.voice_file_id.is_not(None)).count()
    video = tmp_path / "take.mp4"
    made = ["-f", "lavfi", "-i", "color=s=64x64:d=3", "-f", "lavfi", "-i", "sine=d=3", "-shortest"]
    subprocess.run(["ffmpeg", "-v", "error", *made, str(video)], check=True)  # noqa: S603, S607
    wav = voice_carry._cut(video.read_bytes(), 0.5, 2.0)
    assert wav[:4] == b"RIFF" and 1.4 < (len(wav) - 44) / 88200 < 1.6  # mono, 44.1 kHz, 16 bit
    line = {"text": "We were not ready for that.", "start": 2.0, "end": 5.0}
    heard = [{"word": w, "start": 2.1 + n / 2, "end": 2.5 + n / 2}
             for n, w in enumerate(["We", "were", "not", "ready."])]  # fmt: skip
    assert voice_carry._span(line, heard) == (2.0, 4.15)
    assert voice_carry._span(line, heard[:2]) is None


def test_a_movie_cut_is_captioned_with_the_scripts_words_until_switched_off(
        app, owner, db, monkeypatch):  # fmt: skip
    """Reed, 13 Nov (Movie Ad 1): captions, small, the word being said in yellow. A Movie
    video's cut has them from the first; one edit takes them off; other styles are as before."""
    from types import SimpleNamespace

    from app import cut, cut_captions, cut_render, guides

    monkeypatch.setitem(guides.style("movie"), "video_model", "seedance-2.5-kie")
    video = db.get(Project, _delivered(app, owner, db, look="movie", text=BAR))
    tl, _ = cut.timeline(db, video)
    said = [" ".join(c["words"]) for c in cut_render.recipe(db, video, tl)["captions"]]
    assert said == ["You came.", "I said I would.", "Nobody asked me."]  # as the script has them
    assert db.query(FinalVideo).one().timeline["captions"] is True
    off = owner.post(f"/projects/{video.id}/cut/edits", json={"kind": "captions", "on": False})
    assert off.status_code == 201, off.text
    assert off.json()["timeline"]["captions"] is False and off.json()["changes"] == 1
    assert off.json()["edits"][-1]["said"] == "Captions off"
    assert not cut_captions.usual(SimpleNamespace(look="house"))


def test_a_time_jump_is_a_card_in_the_cut_before_its_clip_or_over_its_opening(
        app, owner, db, monkeypatch):  # fmt: skip
    """Reed, 13 Nov (Movie Ad 1): "if there's a time jump, can we like show it? ... something
    cinematic". The plan names the card; the cut draws it: on black as a piece of its own
    before the clip (the cut grows by it), or over the clip's first seconds."""
    from sqlalchemy.orm.attributes import flag_modified

    from app import clip_prompts, cut, cut_render, guides
    from app.one_pass_assemble import PLAN

    monkeypatch.setitem(guides.style("movie"), "video_model", "seedance-2.5-kie")
    video = db.get(Project, _delivered(app, owner, db, look="movie"))
    was = db.query(FinalVideo).one().seconds
    row = clip_prompts.newest(db, video)
    row.data[PLAN]["clips"][1].update(card="Two days later", card_before=True)
    row.data[PLAN]["clips"][2].update(card="That night", card_before=False)
    flag_modified(row, "data")
    db.commit()
    tl, _ = cut.timeline(db, video)
    assert [p["id"] for p in tl["pieces"]] == ["c1", "c2.card", "c2", "c3"]
    card = tl["pieces"][1]
    assert (card["take_id"], card["card"]) == (None, "Two days later")
    assert round(card["end"] - card["start"], 2) == 2.6 == round(tl["length"] - was, 2)
    assert tl["pieces"][2]["start"] == card["end"]
    made = cut_render.recipe(db, video, tl)
    assert made["titles"] == [{"start": tl["pieces"][3]["start"], "words": "That night"}]
    assert all(c["start"] >= card["end"] for c in made["captions"][2:])  # the words moved with it
    shown = owner.get(f"/projects/{video.id}/cut").json()["timeline"]["pieces"][1]
    assert shown["card"] == "Two days later" and shown["file_id"] is None
    assert owner.post(f"/projects/{video.id}/cut").status_code in (200, 201, 202)
    _run(app, db, ticks=6, start=False)
    cuts = db.query(FinalVideo).order_by(FinalVideo.number).all()
    assert len(cuts) == 2 and abs(cuts[1].seconds - (was + 2.6)) < 0.2  # the card is in the file
    off = owner.post(f"/projects/{video.id}/cut/edits", json={"kind": "cards", "on": False})
    plain = off.json()["timeline"]  # switched off: no card piece, no title, the cut as short
    assert off.json()["edits"][-1]["said"] == "Time cards off" and plain["cards"] is False
    assert [p["id"] for p in plain["pieces"]] == ["c1", "c2", "c3"] and plain["length"] == was
    assert cut_render.recipe(db, video, cut.timeline(db, video)[0])["titles"] == []
