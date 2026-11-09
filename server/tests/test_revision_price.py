"""F15 (Skeleton 261, 9 Nov): a one-clip note on a finished video got a start card with the
whole video's estimate (about $15.91) and a progress card with every step after the cast still
to do; the revision itself cost $2.81. A revision whose story stands is priced, and shown, as
only what it makes again. Stand-ins only."""

from decimal import Decimal

from app import clip_takes, credits, director, watch_cut
from app.models.jobs import Job, Usage
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.revision import named, revision
from app.routes import estimate
from app.settings import get_settings
from tests.helpers import make_it
from tests.test_director import _run
from tests.test_free_revisions import _delivered


def _prices(db, pid) -> tuple[Decimal, Decimal, Decimal]:
    """The run's estimate, its "up to" and its work alone (no turns, no limit)."""
    db.expire_all()
    video = db.get(Project, pid)
    draft = db.get(ScriptDraft, video.script_draft_id)
    return (estimate.expected(db, draft, video), estimate.run_price(db, draft, video),
            estimate.version_cost(db, draft, video))  # fmt: skip


def _steps(owner, pid) -> dict[str, str]:
    return {s["key"]: s["state"] for s in owner.get(f"/projects/{pid}/director/progress")
            .json()["steps"]}  # fmt: skip


def _card(owner, pid) -> dict:
    return next(a for a in owner.get(f"/projects/{pid}/asks").json()
                if a["kind"] == "start" and a["state"] == "open")  # fmt: skip


def _one_clip(app, db, owner, editor) -> tuple[int, Decimal, Decimal]:
    """A delivered video, its whole estimate and "up to", then "Make clip 1 brighter." up to
    its start card (its take waits for Make it)."""
    pid = _delivered(app, db, owner, editor)
    whole, whole_up_to, _ = _prices(db, pid)
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Make clip 1 brighter."})
    _run(app, db, ticks=4, start=False)
    return pid, whole, whole_up_to


def test_a_one_clip_revision_is_priced_as_that_clip(app, db, owner, editor, monkeypatch):
    monkeypatch.setattr(get_settings(), "owner_uncapped", True)  # Reed's "About $X" card
    pid, whole, whole_up_to = _one_clip(app, db, owner, editor)
    video = db.get(Project, pid)
    clips, looks = revision(db, video)
    assert [c.clip_id for c in clips] == ["c1"] and looks == 0
    about, up_to, work = _prices(db, pid)
    take = clip_takes.takes_price(db, video, clips)
    still = estimate._still(db, video.workspace_id, video)
    assert work == take + estimate._shots(db, video, clips) * still  # that clip alone
    turns = estimate.REVISION_TURNS + estimate.CLIP_TURNS  # 11, as 261's one clip took
    ws = video.workspace_id
    watch = credits.estimate(db, ws, watch_cut.KIND, Decimal(estimate.WATCH_LOOKS), {})
    assert about == work + take + turns * estimate.turn_price(db, ws) + watch  # and a remake
    assert about < whole and up_to < whole_up_to
    assert abs(_card(owner, pid)["money"]["up_to"]["credits"] - float(about)) <= 1
    steps = _steps(owner, pid)
    assert steps["stills"] == "done" and steps["takes"] == "wait" and steps["cut"] == "todo"


def test_a_new_videos_estimate_is_the_whole_video(app, db, owner, editor):
    from tests.test_director import _made

    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=4, start=False)  # its first start card
    video = db.get(Project, pid)
    assert revision(db, video) is None
    about, up_to, work = _prices(db, pid)
    draft = db.get(ScriptDraft, video.script_draft_id)
    assert work == estimate.version_cost(db, draft)  # every clip, still and look
    ws = video.workspace_id
    claude = credits.estimate(db, ws, "write-claude", Decimal(1), {})
    watch = credits.estimate(db, ws, watch_cut.KIND, Decimal(estimate.WATCH_LOOKS), {})
    assert about == work + estimate.TYPICAL_TURNS * claude + watch
    assert up_to > work + director.own_limit()  # with its remakes


def test_a_revision_counts_none_of_the_work_it_keeps(app, db, owner, editor):
    """A pacing note makes nothing again: no clip, still, look or plan is priced, and the
    progress card shows only the cut still to do."""
    pid = _delivered(app, db, owner, editor)
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Tighten it."})
    assert revision(db, db.get(Project, pid)) == ([], 0)
    assert _prices(db, pid)[2] == 0
    steps = _steps(owner, pid)
    assert {k for k, s in steps.items() if s == "todo"} == {"cut"}, steps  # it reads the note


def test_make_it_again_after_a_stopped_revision_is_priced_as_the_run_it_starts(app, db, owner,
                                                                               editor):  # fmt: skip
    """QA on #1481: the button said the stopped revision's price; the run it started (not a
    revision: none follows a delivery) said the whole video's."""
    pid, _, whole_up_to = _one_clip(app, db, owner, editor)
    make_it(db)
    _run(app, db, ticks=2, start=False)
    assert owner.post(f"/projects/{pid}/director/stop").status_code == 200
    url = f"/projects/{pid}/director"
    shown = owner.get(url).json()["run_price"]
    assert abs(shown - float(whole_up_to)) < 0.01
    assert owner.post(url).status_code == 201  # Make it again
    _run(app, db, ticks=4, start=False)
    assert abs(_card(owner, pid)["money"]["up_to"]["credits"] - shown) <= 1


def test_a_revisions_usually_is_its_own_estimate(app, db, owner, editor):
    """QA on #1481: "Usually it's nearer 6 credits" (its work alone) on a run estimated at 23
    that charged 18: its turns and its watch count too."""
    pid, _, _ = _one_clip(app, db, owner, editor)
    about = _prices(db, pid)[0]
    usual = _card(owner, pid)["money"]["usual"]["credits"]
    assert abs(usual - float(about)) <= 1 and usual > _prices(db, pid)[2] + 1


def test_a_note_names_clip_ranges():
    assert named("Remake clips 3, 5 and 6 with Maya's new look") == {"c3", "c5", "c6"}
    assert named("clips 3-5, please") == named("clips 3 to 5") == {"c3", "c4", "c5"}
    assert named("clips 2, 3, and 9; clip 1b") == {"c1b", "c2", "c3", "c9"}
    assert named("the clip is fine") == set()


def test_a_look_change_naming_no_clip_counts_the_clips_that_person_is_in(app, db, owner,
                                                                         editor):  # fmt: skip
    from app.cast_roles import video_slots

    pid = _delivered(app, db, owner, editor)
    video = db.get(Project, pid)
    role = video_slots(db, video)[0].role
    owner.post(f"/projects/{pid}/director/messages", json={"text": f"Give {role} a red coat."})
    turn = director.turns(db, video)[-1]  # its first move: the look, waiting for Make it
    turn.output = {"tool": "change_look", "look": {"name": role}, "note": "a red coat"}
    turn.input = {**turn.input, "result": director.START_FIRST}
    db.commit()
    clips, looks = revision(db, video)
    assert [c.clip_id for c in clips] == ["c1"] and looks == 1  # the clip that shows them


def test_a_revision_turn_is_priced_at_what_real_turns_cost(app, db, owner, editor):
    """294's turns really cost about $0.13 each, against a 3-credit charge cap: a revision's
    turns are priced at the workspace's measured real cost (the stand-ins report none)."""
    pid = _delivered(app, db, owner, editor)
    ws = db.get(Project, pid).workspace_id
    assert estimate.turn_price(db, ws) == credits.estimate(db, ws, "write-claude", Decimal(1))
    turns = db.query(Job).filter(Job.project_id == pid, Job.input["step"].as_string() == "director")
    for turn, usd in zip(turns.order_by(Job.id.desc()).limit(2), ("0.10", "0.20"), strict=True):
        db.add(Usage(workspace_id=ws, job_id=turn.id, provider="claude", kind="write-claude",
                     units=1, unit="call", cost_usd=Decimal(usd)))  # fmt: skip
    db.commit()
    assert estimate.turn_price(db, ws) == credits.usd_to_credits(Decimal("0.15"))
