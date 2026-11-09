"""F15 (Skeleton 261, 9 Nov): a one-clip note on a finished video got a start card with the
whole video's estimate ($10.42) and a progress card with every step after the cast still to
do; the revision itself cost $2.81. A revision whose story stands is priced, and shown, as
only what it makes again. Stand-ins only."""

from decimal import Decimal

from app import clip_takes, credits, director, watch_cut
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.routes import estimate
from app.settings import get_settings
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


def test_a_one_clip_revision_is_priced_as_that_clip(app, db, owner, editor, monkeypatch):
    monkeypatch.setattr(get_settings(), "owner_uncapped", True)  # Reed's "About $X" card
    pid = _delivered(app, db, owner, editor)
    whole, whole_up_to, _ = _prices(db, pid)
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Make clip 1 brighter."})
    _run(app, db, ticks=4, start=False)  # its take waits for Make it
    video = db.get(Project, pid)
    clips, looks = estimate.revision(db, video)
    assert [c.clip_id for c in clips] == ["c1"] and looks == 0
    about, up_to, work = _prices(db, pid)
    shots = estimate._shots(db, video, clips)
    still = estimate._still(db, video.workspace_id, video)
    assert work == clip_takes.takes_price(db, video, clips) + shots * still  # that clip alone
    assert about < whole / 2 and up_to < whole_up_to
    card = next(a for a in owner.get(f"/projects/{pid}/asks").json()
                if a["kind"] == "start" and a["state"] == "open")  # fmt: skip
    assert abs(card["money"]["up_to"]["credits"] - float(about)) <= 1  # rounded up, in dollars
    steps = _steps(owner, pid)
    assert steps["stills"] == "done" and steps["takes"] == "wait" and steps["cut"] == "todo"


def test_a_new_videos_estimate_is_the_whole_video(app, db, owner, editor):
    from tests.test_director import _made

    pid = _made(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=4, start=False)  # its first start card
    video = db.get(Project, pid)
    assert estimate.revision(db, video) is None
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
    assert estimate.revision(db, db.get(Project, pid)) == ([], 0)
    assert _prices(db, pid)[2] == 0
    steps = _steps(owner, pid)
    assert {k for k, s in steps.items() if s == "todo"} == {"cut"}, steps  # it reads the note now
