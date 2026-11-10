"""Reed, 6 Nov (his test site) and 9 Nov (every site; BS_OWNER_UNCAPPED): the owner's own
work has no monetary hold, every price before a press is what it will probably cost ("About $X
(estimate)"), and what's spent is the providers' own (Usage.cost_usd). Editors' holds are
exactly as before, and with the setting off nothing changes."""

import json
from decimal import Decimal

import pytest

from app import asks, credits, director, ideas
from app.models.accounts import User
from app.models.asks import Ask
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
    _run(app, db, ticks=12, start=False)
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


def test_an_answered_start_card_keeps_what_was_approved(app, db, owner, editor, on, monkeypatch):
    """MAIN's Claymation run: after the plan grew, the answered card re-read "Make it? About
    $14.78 (estimate). Approved" though $13.17 was approved. It keeps the approved figure and
    says the run's new estimate apart."""
    from app.routes import asks as routes

    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db, ticks=12, start=False)
    card = next(c for c in owner.get(f"/projects/{pid}/asks").json() if c["kind"] == "start")
    said = card["question"]
    assert owner.post(f"/asks/{card['id']}/answer", json={"how": "make_it"}).status_code == 200
    grown = routes._expected
    monkeypatch.setattr(routes, "_expected", lambda db, p: grown(db, p) + Decimal(50))
    after = next(c for c in owner.get(f"/projects/{pid}/asks").json() if c["id"] == card["id"])
    assert after["state"] == "answered" and after["question"] == said
    assert after["money"]["since"].startswith("This run's estimate has since grown to about $")


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


def test_the_note_says_what_the_run_really_cost_and_keeps_no_dollars(app, db, owner, editor, on):
    """QA on #1396: the note is kept on the delivery job, which any teammate can read
    (GET /jobs): it keeps only its run's times; the owner's dollars are read when he reads it."""
    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _run(app, db)
    note = next(m for m in owner.get(f"/projects/{pid}/director").json()["thread"]
                if m.get("note"))["note"]  # fmt: skip
    assert note["cost"].startswith("$") and " spent on this run" in note["cost"]
    assert "up to" not in note["cost"]
    theirs = next(m for m in editor.get(f"/projects/{pid}/director").json()["thread"]
                  if m.get("note"))["note"]  # fmt: skip
    assert "credits used of up to" in theirs["cost"] and theirs["spent_usd"] is None
    for job in editor.get("/jobs", params={"project_id": pid}).json():  # what an editor can read
        kept = json.dumps(job)
        assert "actual_usd" not in kept and "listed" not in kept and "cost_usd" not in kept
    kept = next(j for j in db.query(Job).filter(Job.project_id == pid)
                if j.input.get("result") == "Delivered.")  # the deliver turn  # fmt: skip
    assert (
        set(kept.output["note"]) >= {"since", "until"} and "actual_usd" not in kept.output["note"]
    )


def test_spend_counts_list_prices_and_sent_jobs_and_says_so(app, db, owner, editor):
    """QA on #1396: estimated Usage rows (a provider with no reported figure) count, at list
    price, and are said; a job sent with no Usage row (a dropped connection) counts at its
    price; only a job still running is "not reported yet"."""
    pid, _ = _video(app, owner, editor, db)
    base = {"workspace_id": 1, "created_by_id": 1, "project_id": pid, "input": {}}
    told = Job(**base, kind="speech", provider="replicate", credits=Decimal(30),
               status=JobStatus.succeeded, provider_ref="p1")  # fmt: skip
    listed = Job(**base, kind="speech", provider="replicate", credits=Decimal(30),
                 status=JobStatus.succeeded, provider_ref="p2")  # fmt: skip
    dropped = Job(**base, kind="video", provider="replicate", credits=Decimal(10),
                  status=JobStatus.failed, provider_ref="p3")  # fmt: skip
    db.add_all([told, listed, dropped])
    db.flush()
    use = {"workspace_id": 1, "provider": "replicate", "kind": "speech", "units": Decimal(1),
           "unit": "call"}  # fmt: skip
    db.add_all(
        [
            Usage(**use, job_id=told.id, cost_usd=Decimal("1.00"), estimated=False),
            Usage(**use, job_id=listed.id, cost_usd=Decimal("3.00"), estimated=True),
        ]
    )
    db.commit()
    got = credits.actual_usd(db, pid)
    rate = credits.USD_PER_CREDIT
    assert got.usd == (Decimal("4.00") + 10 * rate).quantize(Decimal("0.01")) and not got.pending
    assert got.listed == (Decimal("3.00") + 10 * rate).quantize(Decimal("0.01"))
    assert got.words("on this video").endswith(f"${got.listed:.2f} of it at list price")
    going = Job(**base, kind="video", provider="replicate", credits=Decimal(10),
                status=JobStatus.running, provider_ref="p4")  # fmt: skip
    db.add(going)
    db.commit()
    assert credits.actual_usd(db, pid).pending  # only a running job is not reported yet
    assert credits.actual_usd(db, pid).words("on this video").endswith(", more not reported yet")


def test_the_owner_carries_on_the_same_run_whatever_it_used(app, db, owner, editor, on):
    """QA on #1396: once a run had used its approved price, Carry on started a new run with a
    start card, and the press said "Carry on · up to $5.99 more". Uncapped, it's the same run."""
    from tests.test_carry_on import _stop, _until

    pid, _ = _video(app, owner, editor, db)
    owner.post(f"/projects/{pid}/director")
    _until(app, db, pid)
    _stop(owner, db, app, pid)
    project = db.get(Project, pid)
    card = db.query(Job).filter(Job.project_id == pid, Job.input[asks.START].as_boolean()
                                ).order_by(Job.id.desc()).first()  # fmt: skip
    card.input = {**card.input, "price": "0"}  # the run used all of its approved price
    db.commit()
    stopped = owner.get(f"/projects/{pid}/director/progress").json()["stopped"]
    assert stopped["free"] is True and stopped["carry_on"] == ""  # just "Carry on"
    before = director.turns(db, project)[-1].input[director.RUN]["id"]
    starts = db.query(Ask).filter(Ask.project_id == pid, Ask.kind == "start").count()
    assert owner.post(f"/projects/{pid}/director/carry-on").status_code == 201
    db.expire_all()
    assert director.turns(db, project)[-1].input[director.RUN]["id"] == before  # the same run
    assert db.query(Ask).filter(Ask.project_id == pid, Ask.kind == "start").count() == starts


def test_make_it_again_and_the_list_card_read_the_estimate_and_the_spend(app, db, owner, editor,
                                                                         on):  # fmt: skip
    pid, _ = _video(app, owner, editor, db)
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["run_expected_usd"] > 0  # "Make it again · about $X", in dollars
    assert editor.get(f"/projects/{pid}/director").json()["run_expected_usd"] is None
    reed, _ = _people(db)
    project = db.get(Project, pid)
    known = ideas.facts(db, [project])
    status = ideas.statuses(db, reed, [project], known)[pid]
    cost = ideas._cost(db, reed, project, status, known)
    assert cost.kind == "so_far" and cost.about_usd and cost.usd == 0  # the header's figures


def test_on_by_default_on_every_site_the_live_one_too(monkeypatch):
    """Reed, 9 Nov: no budget per video, on every site ("It is just me working")."""
    from app.settings import check_production

    monkeypatch.delenv("BS_OWNER_UNCAPPED")  # the tests' own holds (conftest) off
    live = Settings(env="production", setup_token="", database_url="sqlite://")
    assert live.owner_uncapped
    check_production(live)  # starts


def test_an_editors_run_is_held_as_theirs_whoever_stops_or_carries_it_on(app, db, owner, editor,
                                                                         on):  # fmt: skip
    """QA on #1396: uncapped was read from the presser or the viewer, so the owner saw a plain
    "Carry on" on an editor's run whose price was used up, and its next step was then held. It's
    the run's starter's: an editor's run carries on only inside its price, else a new run."""
    from tests.test_carry_on import _stop, _until

    pid, _ = _video(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _until(app, db, pid)
    _stop(owner, db, app, pid)
    card = db.query(Job).filter(Job.project_id == pid, Job.input[asks.START].as_boolean()
                                ).order_by(Job.id.desc()).first()  # fmt: skip
    card.input = {**card.input, "price": "0"}  # its approved price is used up
    db.commit()
    stopped = owner.get(f"/projects/{pid}/director/progress").json()["stopped"]
    assert stopped["free"] is False and stopped["carry_on"]  # a new run's price, not "Carry on"
    project = db.get(Project, pid)
    before = director.turns(db, project)[-1].input[director.RUN]["id"]
    assert owner.post(f"/projects/{pid}/director/carry-on").status_code == 201
    db.expire_all()
    assert director.turns(db, project)[-1].input[director.RUN]["id"] != before  # a new run
