"""The director watches and listens to every take as it lands (rule 11, app/take_watch), and
remakes what's weak within the video's budget: on the free stand-ins, real ffmpeg."""

import pytest

from app import director, take_watch, watch_report
from app.credits import credits_used
from app.models.brands import Brand, BrandScreen
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.providers.fake_local import FakeWriter, hear_take
from app.providers.local import LocalProvider
from app.worker import run_once
from tests.conftest import make_cut, run_writer
from tests.helpers import shot
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


@pytest.fixture(autouse=True)
def watches_on(monkeypatch):
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins


def _listen(app, db):
    run_once(db, {"local": LocalProvider(app.state.storage, hear_take=hear_take)},
             app.state.storage, only={"local"})  # fmt: skip


def _land(app, db, editor, setup, clip, action=None, press=True):  # noqa: F811
    """A take made (pressed, unless a remake is already queued), heard, measured and
    watched; the clip as the page shows it."""
    if action:
        shot(db, action=action)
    clips = f"/projects/{setup['project']}/clips"
    if press:
        editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    _listen(app, db)
    run_writer(app, db)
    db.expire_all()
    return editor.get(clips).json()[0]


def test_a_take_is_watched_and_heard_then_kept_and_approves_itself(app, db, editor, setup, clip):  # noqa: F811
    clips = f"/projects/{setup['project']}/clips"
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    (take,) = editor.get(clips).json()[0]["takes"]
    assert take["watch"] == {**take["watch"], "state": "watching"} and take["verdict"] == "checking"
    listen = db.query(Job).filter(Job.kind == "take_listen").one()
    assert listen.input["watch"]["take_id"] == take["id"] and listen.credits == 0  # free
    _listen(app, db)
    look = db.query(Job).filter(Job.kind == "check-claude").one()
    said, pictures = look.input["prompt"], look.input["files"]["reference_images"]
    assert look.input["step"] == "take_watch" and look.status == JobStatus.queued
    assert len(pictures) == 4  # a strip, every frame round its first word, the sound, Mom
    assert "[Image1] 0.0–0.9 s: sampled frames over the whole (" in said
    assert "[Image2] 0.1–0.8 s: sampled frames round a key moment (10 a second)" in said
    assert "[Image3] 0.0–1.1 s: the sound as a spectrogram" in said
    assert '<sheet image="4" id="char:' in said and "<remakes_left>2</remakes_left>" in said
    assert "<heard>" in said and "Loudness" in said and "Seedance" in said
    assert "Watch a take" in "\n".join(look.input["system"])  # with the style's guide
    run_writer(app, db)
    (shown,) = editor.get(clips).json()
    watch = shown["takes"][0]["watch"]
    assert (watch["state"], watch["action"], watch["did"]) == ("done", "keep", "Kept it.")
    assert watch["found"].startswith("It plays as the shot says") and watch["credits"] > 0
    assert shown["approved"] is True and shown["takes"][0]["approved_by"] == "check"


def test_a_weak_take_is_remade_with_its_prompt_rewritten_and_said(app, db, editor, setup, clip):  # noqa: F811
    first = _land(app, db, editor, setup, clip, action="Mom waves. fake:redo")
    one = first["takes"][0]
    w = one["watch"]
    assert (w["action"], w["note"]) == ("redo", "no face on the organs")
    assert w["did"] == ("Remade it on Seedance 2.5 with “no face on the organs” in the prompt.")
    assert w["faults"] == [{"kind": "action", "at": 0.4, "verified": True,
                            "says": "Cartoon eyes landed on the stomach"}]  # fmt: skip
    assert w["remake_credits"] >= 5 and one["verdict"] == "flagged"  # dropped, never approved
    assert first["approved"] is False and len(first["versions"]) == 2  # the old one kept
    assert "Show no face on the organs." in first["prompt"]
    project = db.get(Project, setup["project"])
    (said,) = [m for m in director.thread(db, project) if m["id"] == f"w-c1-{one['id']}"]
    assert said["text"] == ("Clip 1, take 1: Cartoon eyes landed on the stomach at 0:00.4. "
                            "Remade it on Seedance 2.5 with “no face on the "
                            "organs” in the prompt.") and said["status"] == "done"  # fmt: skip
    assert director._redos(db, project, {"redos": {"c1": 1}}) == {
        "c1": 2
    }  # its own and the watch's
    remake = db.query(Job).filter(Job.kind == "video").order_by(Job.id.desc()).first()
    assert remake.status == JobStatus.queued and remake.input["watch_redo"] == one["id"]
    assert "Show no face on the organs." in remake.input["input"]["prompt"]
    second = _land(app, db, editor, setup, clip, action="Mom waves.", press=False)
    assert [t["number"] for t in second["takes"]] == [1, 2]
    two = second["takes"][1]
    assert two["watch"]["action"] == "keep" and second["approved"] is True  # clean: in the cut
    assert db.get(ClipTake, two["id"]).made_with["remade_from"] == 1
    assert make_cut(app, db, editor, f"/projects/{setup['project']}").status_code == 200
    seen = editor.get(f"/projects/{setup['project']}/checks/watch").json()
    assert {k: seen["takes"][k] for k in ("watched", "redone", "held", "flagged")} == {
        "watched": 2, "redone": 1, "held": 0, "flagged": 0}  # fmt: skip
    assert seen["takes"]["latest"]["clip_id"] == "c1" and seen["takes"]["latest"]["take"] == 1
    (redid,) = seen["redid"]  # the delivery note's "What I watched and redid", with its time
    assert (redid["at"], redid["clip_id"], redid["take"], redid["action"]) == (0.4, "c1", 1, "redo")
    assert seen["cut"]["state"] == "none"


def test_never_more_than_two_remakes_a_clip_then_the_owner_sees_it(app, db, editor, setup, clip):  # noqa: F811
    _land(app, db, editor, setup, clip, action="Mom waves. fake:text")
    _land(app, db, editor, setup, clip, press=False)
    third = _land(app, db, editor, setup, clip, press=False)
    assert [t["watch"]["action"] for t in third["takes"]] == ["redo", "redo", "flagged"]
    assert third["takes"][2]["watch"]["did"].startswith("Flagged for you: clip 1 was remade 2")
    assert third["takes"][2]["verdict"] == "flagged" and third["approved"] is False
    assert db.query(Job).filter(Job.kind == "video").count() == 3  # no fourth take
    assert take_watch.remakes(db, db.get(ProjectClip, third["id"])) == 2


def test_past_the_budget_the_remake_waits_for_the_owner(app, db, editor, setup, clip):  # noqa: F811
    shot(db, action="Mom waves. fake:redo")
    clips = f"/projects/{setup['project']}/clips"
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    _listen(app, db)
    project = db.get(Project, setup["project"])
    left = project.budget_credits - credits_used(db, project) - 2  # room for no remake
    db.add(Job(workspace_id=project.workspace_id, kind="video", provider="fake", input={},
               project_id=project.id, credits=left, status="succeeded"))  # fmt: skip
    db.commit()
    run_writer(app, db)
    (shown,) = editor.get(clips).json()
    w = shown["takes"][0]["watch"]
    assert w["action"] == "held" and w["waiting"] is True
    assert w["did"].startswith("Asked the owner: remaking it on Seedance 2.5")
    held = db.query(Job).filter(Job.status == JobStatus.needs_owner_approval).one()
    assert held.input["held"] == ("Waiting for the owner's OK: remaking clip 1 goes past the "
                                  "video's budget.")  # fmt: skip
    assert held.input["watch_redo"] == shown["takes"][0]["id"]
    seen = editor.get(f"/projects/{setup['project']}/checks/watch").json()["takes"]
    assert seen["held"] == 1 and seen["latest"]["waiting"] is True


def test_skipped_at_the_budget_and_a_failed_look_is_free(app, db, editor, setup, clip):  # noqa: F811
    clips = f"/projects/{setup['project']}/clips"
    project = db.get(Project, setup["project"])
    editor.post(f"{clips}/{clip['id']}/generate")
    # after this take, 1 credit is left: not enough for its watch and one more take
    spent = project.budget_credits - credits_used(db, project) - 1
    db.add(Job(workspace_id=project.workspace_id, kind="video", provider="fake", input={},
               project_id=project.id, credits=spent, status="succeeded"))  # fmt: skip
    db.commit()
    _work(app, db, FakeSeedance([_mp4("red")]))
    take = editor.get(clips).json()[0]["takes"][0]
    assert (take["watch"]["state"], take["watch"]["did"]) == ("skipped", take_watch.SKIPPED)
    assert take["check"]["status"] == "skipped"
    assert editor.get(f"/projects/{setup['project']}/checks").json()["paused"] is True
    _listen(app, db)  # its words are still heard, free
    assert not db.query(Job).filter(Job.kind == "check-claude").count()

    db.query(Job).filter(Job.credits == spent, Job.provider == "fake").delete()
    db.commit()
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red"), _mp4("blue")]))
    _listen(app, db)
    before = credits_used(db, project)

    class Broken(FakeWriter):
        def run(self, kind, input):
            raise RuntimeError("no answer")

    run_once(db, {"claude": Broken()}, app.state.storage, only={"claude"})
    newest = editor.get(clips).json()[0]["takes"][-1]
    assert newest["check"]["status"] == "failed" and newest["watch"]["state"] == "failed"
    held = db.query(Job).filter(Job.kind == "check-claude").one().credits
    assert held and credits_used(db, project) == before - held  # nothing charged
    assert db.query(ItemCheck).filter_by(target="take").count() == 2


def test_a_take_watch_costs_its_up_to_in_every_take_price(app, db, editor, setup, clip):  # noqa: F811
    project = db.get(Project, setup["project"])
    watch = take_watch.per_take(db, project.workspace_id)
    assert watch == take_watch.LOOKS * take_watch.estimate(
        db, project.workspace_id, take_watch.KIND, 1, {}
    )  # 6 looks at 0.2: 1.2 credits
    row = db.get(ProjectClip, clip["id"])
    assert take_watch.rides(db, project, row) == watch
    review = editor.get(f"/projects/{setup['project']}/checks").json()
    assert review["credits_per_check"] == 2 and review["check_credits_per_video"] == 2


def test_a_fault_only_the_sound_suggests_is_told_never_remade(app, db, editor, setup, clip):  # noqa: F811
    shown = _land(app, db, editor, setup, clip, action="Mom waves. fake:music")
    w = shown["takes"][0]["watch"]
    assert w["action"] == "unsure" and w["remake_take"] is None
    assert w["did"] == ("Not remade: Music may run under the voice (not confirmed). Listen "
                        "before you use it.")  # fmt: skip
    assert w["faults"][0]["verified"] is False and shown["approved"] is False  # the owner's
    assert db.query(Job).filter(Job.kind == "video").count() == 1  # no paid remake
    seen = editor.get(f"/projects/{setup['project']}/checks/watch").json()["takes"]
    assert (seen["unsure"], seen["redone"]) == (1, 0)
    assert watch_report.doubts(db, db.get(Project, setup["project"])) == (
        "Clip 1: Music may run under the voice (not confirmed)."
    )  # in the delivery note


def test_the_directors_own_remakes_count_toward_the_two(app, db, editor, setup, clip):  # noqa: F811
    from app.director import RUN
    from app.director import STEP as TURN

    project = db.get(Project, setup["project"])
    db.add(Job(workspace_id=project.workspace_id, kind="check-claude", provider="fake",
               project_id=project.id, status="succeeded", credits=0,
               input={"step": TURN, RUN: {"id": "r1", "redos": {"c1": 2}}}))  # fmt: skip
    db.commit()
    shown = _land(app, db, editor, setup, clip, action="Mom waves. fake:redo")
    w = shown["takes"][0]["watch"]
    assert w["action"] == "flagged" and w["did"].startswith("Flagged for you: clip 1 was remade 2")
    assert take_watch.directors(db, project, "c1") == 2


def test_only_frames_or_clipped_samples_confirm_a_fault():
    """Reed, 4 Nov: never pay on a transcript, a silence or a picture-change jump alone."""
    from app.watch_report import confirmed, facts

    clipped = facts({"sound": {"clipped_samples": 12, "peak_db": 0.0, "silences": [[1, 2]]}})
    assert clipped == {"clipped": True}
    assert facts({"sound": {"clipped_samples": 12, "peak_db": -0.5}}) == {"clipped": False}
    assert facts({"sound": {"clipped_samples": 3, "peak_db": 0.0}}) == {"clipped": False}
    assert confirmed("motion", "picture", clipped) and confirmed("text", "picture", {})
    assert confirmed("clipping", "measured", clipped)  # clipped samples: unambiguous
    assert not confirmed("clipping", "measured", {"clipped": False})
    assert not confirmed("sound", "measured", clipped)  # a silence or a dropout: a pause?
    assert not confirmed("timing", "picture", clipped)  # word times come from the transcript
    assert not confirmed("motion", "measured", clipped)  # a jump: a glitch or a fast move?
    assert not confirmed("sound", "words", clipped)  # the transcript can mishear
    assert not confirmed("sound", "sound", clipped) and not confirmed("sound", "picture", {})
    for kind in ("lipsync", "voice"):
        assert not confirmed(kind, "picture", clipped)


def test_a_narrated_video_keeps_its_narration_throughout(app, db, editor, setup, clip, monkeypatch):  # noqa: F811, E501
    """Reed, 4 Nov: in a narrated video nobody on screen speaks; dialogue speaks as written."""
    project, row = db.get(Project, setup["project"]), db.get(ProjectClip, clip["id"])
    shots = take_watch._shots(db, row)
    assert take_watch.said(db, project, row, shots) == take_watch.SPEAKS  # Mom's line
    monkeypatch.setattr("app.plans.fmt", lambda db, project: "narrated")
    monkeypatch.setattr("app.narration.video_kind", lambda db, project: "narrated")
    assert "narrator is heard over this clip, which isn't planned to speak" in take_watch.said(
        db, project, row, shots)  # fmt: skip


def test_a_rewrite_never_drops_an_approved_look(app, db, editor, setup, clip):  # noqa: F811
    from app import change

    project, row = db.get(Project, setup["project"]), db.get(ProjectClip, clip["id"])
    fitted, _ = change.fit(db, project, row, row.prompt + "\nShow the hands.", "the hands")
    assert take_watch.keeps_looks(db, project, row, fitted, "the hands")
    bare = fitted.model_copy(update={"references": [r for r in fitted.references
                                                    if not r.id.startswith("char:")]})  # fmt: skip
    assert not take_watch.keeps_looks(db, project, row, bare, "the hands")


def test_unsure_takes_are_never_redone_by_the_director(app, db, editor, setup, clip):  # noqa: F811
    from app.director import choose, video_state

    _land(app, db, editor, setup, clip, action="Mom waves. fake:music")
    project = db.get(Project, setup["project"])
    state = video_state(db, project)
    (take,) = state["clips"][0]["takes"]
    assert (take["verdict"], take["notes"]) == ("unsure", [])
    move = choose({**state, "allowed": {"watches_left": 1}})
    assert move["tool"] != "make_take"  # a doubt goes to the owner, never a paid redo


def test_the_look_gets_the_brands_screen_rules_and_this_videos_outfit(app, db, editor, setup, clip):  # noqa: F811, E501
    project = db.get(Project, setup["project"])
    db.get(Brand, project.brand_id).tone_notes = "Fun.\nThe fomo screen only ever shows wins."
    screen = db.get(BrandScreen, setup["screen"])
    screen.product_id, screen.tags = None, ["app"]  # the brand's app, not a product
    mom = next(r["id"] for r in clip["references"] if r["id"].startswith("char:"))
    project.outfits = {mom: "mustard trench coat"}
    shot(db, screen_ids=[f"screen:{screen.id}"])
    editor.post(f"/projects/{setup['project']}/clips/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    _listen(app, db)
    look = db.query(Job).filter(Job.kind == "check-claude").one()
    said = look.input["prompt"]
    assert f'id="screen:{screen.id}"' in said and "<screens>" in said
    assert "<screen_rules>\nThe fomo screen only ever shows wins.\n</screen_rules>" in said
    assert f"screen:{screen.id}" in look.input["ref_ids"]  # so a screen finding keeps its who
    assert "wears: mustard trench coat (this video)." in said


def _answer(db, take_id, **answer):
    """The look at this take answers again, as given."""
    look = next(j for j in db.query(Job).filter(Job.kind == "check-claude")
                if j.input.get("take_id") == take_id)  # fmt: skip
    look.output = answer
    take_watch.save(db, look)
    db.commit()
    db.expire_all()
    return db.get(ClipTake, take_id).watch


def test_a_transcripts_finding_alone_never_buys_a_redo(app, db, editor, setup, clip):  # noqa: F811
    from app.director import _only_a_doubt, choose, video_state

    shown = _land(app, db, editor, setup, clip)
    take = shown["takes"][0]
    project = db.get(Project, setup["project"])
    words = db.query(ItemCheck).filter_by(target="words", target_id=take["id"]).one()
    words.findings = [{"kind": "missing", "role": "", "text": "Not heard", "change_note": "Say it"}]
    db.commit()
    state = video_state(db, project)
    (seen,) = state["clips"][0]["takes"]
    assert (seen["verdict"], seen["notes"]) == ("unsure", [])
    assert choose({**state, "allowed": {"watches_left": 1}})["tool"] != "make_take"
    assert _only_a_doubt(db, project, "c1", "Say the line again.")  # the real director: refused
    from app.director import READ, RUN
    from app.director import STEP as TURN

    db.add(Job(workspace_id=project.workspace_id, kind="check-claude", provider="fake",
               project_id=project.id, status="succeeded", credits=0,
               input={"step": TURN, RUN: {"id": "r1", "redos": {}}, READ: 1}))  # fmt: skip
    db.commit()
    assert not _only_a_doubt(db, project, "c1", "Note 1: you asked for it.", "r1")  # a person's
    assert _only_a_doubt(db, project, "c1", "Note 2: never sent.", "r1")


def test_a_kept_take_with_a_doubt_is_shown_and_waits_for_a_person(app, db, editor, setup, clip):  # noqa: F811
    take = _land(app, db, editor, setup, clip)["takes"][0]
    db.get(ProjectClip, clip["id"]).approved = False  # as before its look answers
    db.commit()
    w = _answer(db, take["id"], seen="The voice may thin out at 0:03.", verdict="keep", faults=[
        {"kind": "voice", "at": 3.0, "says": "The voice may thin out",
         "evidence": "sound"}])  # fmt: skip
    assert w["action"] == "unsure" and w["did"].startswith("Not remade: The voice may thin out")
    project = db.get(Project, setup["project"])
    assert watch_report.doubts(db, project) == "Clip 1: The voice may thin out (not confirmed)."
    (doubt,) = db.query(ItemCheck).filter_by(target="take", target_id=take["id"]).one().findings
    assert (doubt["verified"], doubt["change_note"]) == (False, "")  # shown, never a redo note
    assert db.get(ProjectClip, clip["id"]).approved is False  # never approved silently
    assert any("may thin out" in m["text"] for m in director.thread(db, project))


def test_confirmed_and_doubted_faults_together_keep_the_doubt_visible(app, db, editor, setup, clip):  # noqa: F811
    take = _land(app, db, editor, setup, clip)["takes"][0]
    w = _answer(db, take["id"], seen="A hand melts; the lips may be late.", verdict="redo",
                note="hands whole and lips on the words", prompt="Rewritten.", faults=[
        {"kind": "motion", "at": 1.0, "says": "A hand melts", "evidence": "picture"},
        {"kind": "lipsync", "at": 2.0, "says": "The lips may be late",
         "evidence": "picture"}])  # fmt: skip
    assert w["action"] == "redo" and w["note"] == "A hand melts"  # the sure one only
    assert "(not confirmed)" in watch_report.doubts(db, db.get(Project, setup["project"]))
    remake = db.get(Job, w["remake_job_id"])
    assert "lips" not in remake.input["input"]["prompt"].split("Change from the last take:")[-1]


def test_a_failed_remake_keeps_the_prompt(app, db, editor, setup, clip, monkeypatch):  # noqa: F811
    from fastapi import HTTPException

    def refused(*args, **kwargs):
        raise HTTPException(409, "The test site's real-AI budget ($5.00) is used up.")

    take = _land(app, db, editor, setup, clip)["takes"][0]
    row = db.get(ProjectClip, clip["id"])
    prompt = row.prompt
    monkeypatch.setattr("app.routes.jobs.enqueue", refused)
    w = _answer(db, take["id"], seen="A hand melts.", verdict="redo", note="hands whole",
                prompt=f"{prompt}\nShow whole hands.", faults=[
        {"kind": "motion", "at": 1.0, "says": "A hand melts", "evidence": "picture"}])  # fmt: skip
    assert w["action"] == "flagged" and "$" not in w["did"]
    assert db.get(ProjectClip, clip["id"]).prompt == prompt


def test_a_director_redo_needs_a_confirmed_reason_or_a_persons_note(app, db, editor, setup, clip):  # noqa: F811
    from app.director import _only_a_doubt

    _land(app, db, editor, setup, clip)  # a clean take: no reason to pay for another
    project = db.get(Project, setup["project"])
    assert _only_a_doubt(db, project, "c1", "The story beat could be stronger.")
    assert _only_a_doubt(db, project, "c1", "Note 7: made up.", "r9")  # no such note: no bypass
    take = db.query(ClipTake).one()
    take.prompt = "an older prompt"  # made from another prompt than the clip's now
    db.commit()
    assert not _only_a_doubt(db, project, "c1", "The prompt changed since.")
