"""Reed, 6 Nov: on his owner-only test site (BS_OWNER_UNCAPPED) the owner's own work has no
monetary hold, every price before a press is what it will probably cost ("About $X
(estimate)"), and what's spent is the providers' own (Usage.cost_usd). Editors' holds are
exactly as before, and with the setting off nothing changes."""

from decimal import Decimal

import pytest

from app import credits, delivery, ideas
from app.models.accounts import User
from app.models.jobs import Job, JobStatus, Usage
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.routes.estimate import expected, run_price
from app.settings import Settings, get_settings
from tests.test_asks import _video
from tests.test_director import _run
from tests.test_freestyle_dialogue import BODY


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(get_settings(), "owner_uncapped", True)


def _people(db):
    return (db.query(User).filter_by(email="reed@example.com").one(),
            db.query(User).filter_by(email="ed@example.com").one())  # fmt: skip


def test_no_budget_or_price_hold_for_the_owner_and_editors_unchanged(app, db, owner, editor, on):
    pid, _ = _video(app, owner, editor, db)
    project, (reed, ed) = db.get(Project, pid), _people(db)
    lots = Decimal(10**6)
    assert credits.fits(db, project, reed, lots) == ""
    assert credits.past_approved(db, project, reed, lots) == ""
    assert not credits.past_price(db, project, reed, lots)
    assert credits.fits(db, project, ed, lots)  # an editor's are as they were


def test_off_the_owner_is_held_as_before(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    reed, _ = _people(db)
    assert not credits.uncapped(reed)
    assert credits.fits(db, db.get(Project, pid), reed, Decimal(10**6))


def test_the_real_budget_never_stops_the_owner_when_it_is_0(db, owner, editor):
    site = Settings(env="next", fake_providers=False, owner_uncapped=True)  # no budget, no start
    assert credits.real_budget_refusal(db, site, "replicate", Decimal(5), owner=True) == ""
    assert credits.real_budget_refusal(db, site, "replicate", Decimal(5), owner=False)  # editor
    capped = Settings(env="next", fake_providers=False, owner_uncapped=True, real_budget_usd=1,
                      real_budget_since="2026-01-01T00:00:00Z")  # fmt: skip
    assert credits.real_budget_refusal(db, capped, "replicate", Decimal(10**4), owner=True)
    off = Settings(env="next", fake_providers=False)
    assert credits.real_budget_refusal(db, off, "replicate", Decimal(5), owner=True)


def test_new_videos_press_says_about_what_it_will_cost(app, db, owner, editor, on):
    est = owner.get("/freestyles/estimate", params={k: v for k, v in BODY.items()}).json()
    assert est["expected"] is True and est["held"] == "" and est["usd"] > 0
    theirs = editor.get("/freestyles/estimate", params={k: v for k, v in BODY.items()}).json()
    assert theirs["expected"] is False  # an editor's is the most, in credits, as before
    assert est["credits"] < theirs["credits"]  # no allowance or remakes bound in it


def test_the_start_card_is_an_estimate_with_no_limit(app, db, owner, editor, on, monkeypatch):
    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=4, start=False)
    card = next(c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "start")
    assert card["question"].startswith("Make it? About $") and card["question"].endswith(
        " (estimate).")  # fmt: skip
    assert "probably cost" in card["why"] and "up to" not in card["why"]
    assert card["money"]["expected"] is True and card["money"]["usual"] is None
    assert card["can"][0] == "make_it" and card["state"] != "held"  # never "has been asked"
    assert "has been asked" not in card["why"]
    project = db.get(Project, pid)
    draft = db.get(ScriptDraft, project.script_draft_id)
    assert expected(db, draft, project) < run_price(db, draft, project)


def test_the_header_reads_the_providers_spend_and_never_a_budget(app, db, owner, editor, on):
    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    reed, _ = _people(db)
    job = db.query(Job).filter(Job.project_id == pid).first()
    db.add(Usage(workspace_id=1, job_id=job.id, provider="claude", kind="write-claude",
                 units=Decimal(1), unit="call", cost_usd=Decimal("16.77"),
                 estimated=False))  # fmt: skip
    db.commit()
    head = owner.get(f"/projects/{pid}/idea").json()
    assert head["budget"] is None and head["up_to"] is None and head["actual"] is True
    assert head["expected"]["usd"] > 0 and head["spent"]["usd"] >= 16.77
    theirs = editor.get(f"/projects/{pid}/idea").json()
    assert theirs["budget"] is not None and theirs["actual"] is False  # an editor's: as before
    progress = owner.get(f"/projects/{pid}/director/progress").json()
    assert progress["actual_usd"] >= 16.77 and progress["expected_usd"] > 0
    assert editor.get(f"/projects/{pid}/director/progress").json()["actual_usd"] is None
    assert ideas.head(db, reed, db.get(Project, pid)).budget is None


def test_the_delivery_note_says_what_the_run_really_cost(app, db, owner, editor, on):
    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    note = next(m for m in owner.get(f"/projects/{pid}/director").json()["thread"]
                if m.get("note"))["note"]  # fmt: skip
    assert note["cost"].endswith("spent on this run (the providers' own charges)") or (
        "not reported yet" in note["cost"])  # fmt: skip
    assert "up to" not in note["cost"]
    theirs = next(m for m in editor.get(f"/projects/{pid}/director").json()["thread"]
                  if m.get("note"))["note"]  # fmt: skip
    assert "credits used of up to" in theirs["cost"]  # never dollars or the actual to an editor
    kept = {**delivery.BLANK, "actual_usd": 1.5, "unreported": True, "spent": 1, "up_to": 2}
    assert delivery.shown(kept, owner=True)["cost"] == (
        "$1.50 spent on this run (the providers' own charges), and some cost not reported yet"
    )


def test_an_unreported_cost_is_said(app, db, owner, editor):
    pid, _ = _video(app, owner, editor, db)
    job = db.query(Job).filter(Job.project_id == pid).first() or Job(
        workspace_id=1, created_by_id=1, kind="video", provider="replicate", input={},
        project_id=pid, credits=Decimal(3), status=JobStatus.running)  # fmt: skip
    job.status = JobStatus.running
    db.add(job)
    db.commit()
    real, pending = credits.actual_usd(db, pid)
    assert pending and real == 0


def test_live_refuses_to_start_uncapped():
    from app.settings import check_production

    live = Settings(env="production", owner_uncapped=True, setup_token="", database_url="sqlite://")
    with pytest.raises(RuntimeError, match="BS_OWNER_UNCAPPED"):
        check_production(live)
    check_production(Settings(env="next", owner_uncapped=True, setup_token="",
                              database_url="sqlite://"))  # the test site may  # fmt: skip
