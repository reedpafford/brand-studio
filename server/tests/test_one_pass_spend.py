"""Per-brand usage of one-pass videos (Reed, 10 Nov: "make sure the api usage is tracked - this
is important - for each brand"): every job a one-pass video makes carries its video's brand,
the brand's usage is the sum of its jobs, by kind, and an idea's writing call counts for its
video. Two videos on two brands, on the stand-ins, each job then charged as a provider would
report it."""

from decimal import Decimal

import pytest

from app import spend, usage
from app.credits import USD_PER_CREDIT
from app.models.accounts import Role, User
from app.models.jobs import Job, Usage
from app.models.projects import Project
from tests.test_one_pass_narrated import NARRATION, _jobs, _run
from tests.test_usage import _charge

IDEA = "A barista proves her regulars wrong about decaf."


@pytest.fixture(autouse=True)
def _one_pass_on(monkeypatch):
    from app.settings import get_settings

    monkeypatch.setattr(get_settings(), "one_pass", True)
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)  # as on the stand-ins


def _brands(owner) -> tuple[int, int]:
    have = [b["id"] for b in owner.get("/brands").json()]
    if len(have) < 2:
        have.append(owner.post("/brands", json={"name": "Second brand"}).json()["id"])
    return have[0], have[1]


def test_every_job_of_a_one_pass_video_is_its_brands_and_the_totals_add_up(app, owner, db):
    a, b = _brands(owner)
    body = {"shape": "9:16", "look": "house"}
    host = owner.post("/freestyles", json={**body, "type": "presenter", "text": NARRATION,
                                           "brand_id": a})  # fmt: skip
    talk = owner.post("/freestyles", json={**body, "type": "dialogue", "text": IDEA, "idea": True,
                                           "brand_id": b})  # fmt: skip
    assert host.status_code == talk.status_code == 201, (host.text, talk.text)
    _run(app, db, ticks=90)
    made = [owner.get(f"/freestyles/{fs.json()['id']}").json() for fs in (host, talk)]
    assert [m["status"] for m in made] == ["delivered", "delivered"], made
    videos = {a: made[0]["project_id"], b: made[1]["project_id"]}
    for brand, pid in videos.items():  # none of a video's jobs is another brand's, or nobody's
        assert db.get(Project, pid).brand_id == brand
        mine = db.query(Job).filter(Job.project_id == pid).all()
        assert mine and {j.brand_id for j in mine} == {brand}, [
            (j.kind, j.input.get("step"), j.brand_id) for j in mine if j.brand_id != brand
        ]
    (idea,) = _jobs(db, "script_draft")  # written before its video existed: both now
    assert (idea.brand_id, idea.project_id) == (b, videos[b])
    steps = {j.input.get("step") for j in db.query(Job).filter(Job.project_id == videos[a])}
    assert steps >= {"one_pass", "song_take", "song_timing", "voice_sample", "host_still",
                     "host_piece", "clip_take", "watch_cut", "sheet"}  # fmt: skip
    for job in db.query(Job).filter(Job.credits > 0).all():  # as each provider reports it
        _charge(db, job, job.credits * USD_PER_CREDIT)
    paid = {u.job_id: u.cost_usd for u in db.query(Usage)}  # what each job was charged
    me = db.query(User).filter_by(role=Role.owner).one()
    figures = usage.figures(db, me.workspace_id, usage.period("all"))
    for brand, pid in videos.items():
        jobs = db.query(Job).filter(Job.brand_id == brand).all()
        whole = sum((paid.get(j.id, 0) for j in jobs), Decimal(0))  # the sum of its jobs
        found = spend.split(spend.charges(db, Job.brand_id == brand)[0])
        assert found.usd == whole == figures.spent([brand]).usd and whole > 0
        by_kind = {}
        for j in jobs:
            kind = spend.kind_name(j.provider, j.kind)
            by_kind[kind] = by_kind.get(kind, Decimal(0)) + paid.get(j.id, 0)
        assert {k: v[0] for k, v in found.kinds.items()} == {k: v for k, v in by_kind.items() if v}
        video = spend.split(spend.charges(db, Job.project_id == pid)[0])
        assert 0 < video.usd <= found.usd  # the video's own, inside its brand's
    kinds = set(spend.split(spend.charges(db, Job.brand_id == a)[0]).kinds)
    assert {spend.THINKING, "Voice", "Takes", "Stills", spend.CHECKS} <= kinds
    assert set(figures.charges) >= {a, b} and not figures.charges.get(None)  # none unfiled
    rows = {r["brand_id"]: r for r in owner.get("/usage/brands").json()["items"]}
    assert rows[a]["spend_usd"] == usage.money(figures.spent([a]).usd)
    assert {p["name"] for p in rows[a]["providers"]} >= {"Claude", "HeyGen", "Replicate"}
