"""v5 audit (D_Usage, D_MyCredits): a month picked on Usage and My credits, spend in credits,
each brand's credits and videos, Freestyle's own row, and My credits across every brand with
each row's status. Free."""

from datetime import datetime

import pytest

from app.models.accounts import Role, User
from app.models.brands import Brand
from app.models.jobs import Job
from app.routes.jobs import enqueue
from tests.test_freestyle_dialogue import BODY
from tests.test_freestyle_dialogue import _run as _run_fakes
from tests.test_usage import _charge, _setup

OCT, NOV = datetime(2026, 10, 15, 12), datetime(2026, 11, 2, 12)


def _job(db, who, dollars, when, **kw):
    job = enqueue(db, who, "video-480p", {}, **kw)
    job.created_at = when
    _charge(db, job, dollars, when=when)
    return job


def test_a_picked_month_counts_only_its_own_charges_in_credits_too(owner, editor, db):
    me, fomo, video = _setup(owner, db)
    october = _job(db, me, "2.00", OCT, project=video)
    _job(db, me, "1.00", NOV, project=video)
    out = owner.get("/usage/summary", params={"month": "2026-10"}).json()
    assert out["period"] == "month" and out["starts_at"].startswith("2026-10-01")
    assert out["spend_usd"] == 2.0 and out["spend_credits"] == float(october.credits) > 0
    assert out["previous"]["spend_usd"] == 0  # September
    (row,) = [r for r in owner.get("/usage/brands", params={"month": "2026-10"}).json()["items"]
              if r["brand_id"] == fomo]  # fmt: skip
    assert row["spend_usd"] == 2.0 and row["credits"] == float(october.credits)
    assert row["videos"] == 1  # being made now
    assert owner.get(f"/usage/brands/{fomo}", params={"month": "2026-10"}).json()["credits"] == (
        row["credits"])  # fmt: skip
    (reed,) = [p for p in owner.get("/usage/people", params={"month": "2026-10"}).json()
               if p["name"] == "Reed"]  # fmt: skip
    assert reed["credits"] == float(october.credits)
    assert owner.get("/usage/summary", params={"month": "2026-13"}).status_code == 422
    assert editor.get("/usage/summary", params={"month": "2026-10"}).status_code == 404


def test_freestyle_with_no_brand_has_its_own_row(app, owner, db):
    clip = {"type": "one_clip", "look": "house", "shape": "9:16", "text": "A cat at dawn."}
    owner.post("/freestyles", json=clip)  # One clip: the only send with no brand
    _run_fakes(app, db)
    out = owner.get("/usage/summary", params={"period": "all"}).json()["freestyle"]
    from app.credits import COUNTED

    hidden = db.query(Brand).execution_options(see_hidden=True).filter_by(hidden=True).one()
    spent = sum(j.credits for j in db.query(Job).filter(Job.brand_id == hidden.id,
                                                         Job.status.in_(COUNTED)))  # fmt: skip
    assert out["credits"] == float(spent) > 0
    assert out["spend_usd"] == owner.get("/usage/summary", params={"period": "all"}).json()[
        "freestyle_spend_usd"]  # fmt: skip


def test_my_credits_across_every_brand_with_each_rows_status(app, owner, editor, db, monkeypatch):
    from app import director

    monkeypatch.setattr(director, "own_limit", lambda: director.OWN_CREDITS * 2)  # its looks
    _, fomo, launch = _setup(owner, db)
    other = next(b["id"] for b in owner.get("/brands").json() if b["id"] != fomo)
    fs = owner.post("/freestyles", json={**BODY, "brand_id": other}).json()  # another brand
    _run_fakes(app, db)
    made = owner.post("/projects", json={"brand_id": fomo, "name": "Mine"}).json()["id"]
    out = owner.get("/usage/mine").json()
    states = {v["project_id"]: v["state"] for v in out["videos"]}
    assert states[fs["project_id"]] == "delivered" and states[made] == "making"
    assert out["videos_and_freestyles"] == len(out["videos"]) == 3
    one = owner.get("/usage/mine", params={"brand_id": fomo}).json()  # one brand, as before
    assert sorted(v["project_id"] for v in one["videos"]) == sorted([made, launch.id])
    assert owner.get("/usage/mine", params={"month": "2020-01"}).json()["videos"] == []
    ed = db.query(User).filter_by(role=Role.editor).one()
    assert all(v["project_id"] not in states for v in editor.get("/usage/mine").json()["videos"])
    assert ed.id  # an editor sees only their own


def test_a_freestyles_video_on_production_says_what_the_oks_cover(app, owner, db):
    """Next-Lead (the Producer's rule 34): production's row has approved_up_to, as My credits."""
    from tests.conftest import first_brand

    fs = owner.post("/freestyles", json={**BODY, "brand_id": first_brand(owner)}).json()
    _run_fakes(app, db, ticks=5)
    rows = owner.get("/production").json()
    mine = [r for r in owner.get("/usage/mine").json()["videos"]
            if r["project_id"] == fs["project_id"]]  # fmt: skip
    row = next((r for r in rows if r["project_id"] == fs["project_id"]), None)
    assert row["approved_up_to"] == mine[0]["approved_up_to"] > 0
    assert all(r["approved_up_to"] is None for r in rows if r["project_id"] != fs["project_id"])


@pytest.mark.parametrize("month", ["0000-01", "9999-12", "1999-12", "2026-00"])
def test_a_month_out_of_range_is_a_422_never_a_500(owner, month):
    for path in ("/usage/summary", "/usage/brands", "/usage/people", "/usage/mine"):
        assert owner.get(path, params={"month": month}).status_code == 422, path


def test_the_credit_rows_add_up_to_the_total(app, owner, db):
    """QA-10: a brandless job (a look, a script's writing with no brand) has its own line."""
    me, fomo, video = _setup(owner, db)
    _job(db, me, "1.00", NOV, project=video)
    owner.post("/freestyles", json=BODY)
    _run_fakes(app, db, ticks=3)
    loose = enqueue(db, me, "write-claude", {"step": "improve"})
    loose.created_at = NOV
    db.commit()
    params = {"month": NOV.strftime("%Y-%m")}
    out = owner.get("/usage/summary", params=params).json()
    rows = owner.get("/usage/brands", params={**params, "archived": True, "limit": 100}).json()
    total = sum(r["credits"] for r in rows["items"]) + out["freestyle"]["credits"]
    assert out["unassigned_credits"] == float(loose.credits) > 0
    assert round(total + out["unassigned_credits"], 2) == round(out["spend_credits"], 2)
