"""Usage, the brand tracker: spend, finished videos and cost per finished video per brand."""

from datetime import timedelta
from decimal import Decimal

from app.credits import week_start
from app.db import utcnow
from app.models.accounts import Role, User
from app.models.jobs import Usage
from app.models.projects import Project
from app.routes.jobs import enqueue

ENDPOINTS = ["/usage/summary", "/usage/brands", "/usage/brands/1"]


def _charge(db, job, dollars, when=None, estimated=False):
    db.add(
        Usage(
            workspace_id=job.workspace_id,
            job_id=job.id,
            provider="fake",
            kind=job.kind,
            units=Decimal(1),
            unit="second",
            cost_usd=Decimal(str(dollars)),
            estimated=estimated,
            created_at=when or utcnow(),
        )
    )
    db.commit()


def _setup(owner, db):
    me = db.query(User).filter_by(role=Role.owner).one()
    fomo = owner.get("/brands").json()[0]["id"]
    made = owner.post("/projects", json={"brand_id": fomo, "name": "Launch"}).json()
    return me, fomo, db.get(Project, made["id"])


def test_spend_finished_and_cost_per_finished_video(owner, db):
    me, fomo, project = _setup(owner, db)
    first = enqueue(db, me, "video-480p", {}, project=project)
    _charge(db, first, "4.00", when=utcnow() - timedelta(days=400))  # long before: lifetime only
    _charge(db, enqueue(db, me, "video-480p", {}, project=project), "6.50", estimated=True)
    _charge(db, enqueue(db, me, "video-480p", {"brand_id": fomo}), "1.25")  # a Quick clip
    _charge(db, enqueue(db, me, "write-claude", {}), "0.20")  # not tied to one brand
    project.finished_at = utcnow()
    db.commit()

    week = owner.get("/usage/summary").json()
    assert (week["spend_usd"], week["unassigned_spend_usd"], week["spend_estimated"]) == (
        7.95,
        0.2,
        True,
    )
    assert (week["finished"], week["cost_per_finished_usd"], week["in_progress"]) == (1, 10.5, 0)
    assert week["previous"] == {"spend_usd": 0.0, "finished": 0, "cost_per_finished_usd": None}
    assert owner.get("/usage/summary", params={"period": "all"}).json()["spend_usd"] == 11.95

    row = next(r for r in owner.get("/usage/brands").json()["items"] if r["brand_id"] == fomo)
    assert (row["spend_usd"], row["finished"], row["cost_per_finished_usd"]) == (7.75, 1, 10.5)
    assert row["last_activity_at"] is not None
    one = owner.get(f"/usage/brands/{fomo}").json()
    assert one["spend_usd"] == 7.75 and one["editors_active"] == 1


def test_week_and_month_boundaries_and_the_period_before(owner, db):
    me, fomo, project = _setup(owner, db)
    start = week_start()
    _charge(db, enqueue(db, me, "video-480p", {}, project=project), "3", when=start)
    _charge(db, enqueue(db, me, "video-480p", {}, project=project), "2", when=start - timedelta(1))
    week = owner.get("/usage/summary").json()
    assert week["spend_usd"] == 3.0 and week["previous"]["spend_usd"] == 2.0
    month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month = owner.get("/usage/summary", params={"period": "month"}).json()
    in_month = sum(x for x, at in ((3, start), (2, start - timedelta(1))) if at >= month_start)
    assert month["spend_usd"] == in_month
    assert owner.get("/usage/summary", params={"period": "all"}).json()["previous"] is None


def test_every_brand_is_listed_once_new_ones_with_zeros(owner, db):
    made = owner.post("/brands", json={"name": "Night Owl"})
    assert made.status_code == 201, made.text
    rows = owner.get("/usage/brands", params={"sort": "name"}).json()
    owl = next(r for r in rows["items"] if r["name"] == "Night Owl")
    assert (owl["spend_usd"], owl["finished"], owl["cost_per_finished_usd"]) == (0.0, 0, None)
    assert owl["last_activity_at"] is None and owl["scripts"] == 0
    seen, cursor = [], None
    while True:
        params = {"limit": 1, **({"cursor": cursor} if cursor else {})}
        page = owner.get("/usage/brands", params=params).json()
        seen += [r["brand_id"] for r in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert (
        sorted(seen) == sorted(r["brand_id"] for r in rows["items"]) and len(seen) == rows["total"]
    )
    found = owner.get("/usage/brands", params={"q": "night"}).json()
    assert [r["name"] for r in found["items"]] == ["Night Owl"] and found["total"] == 1


def test_editors_and_other_workspaces_never_see_usage(owner, editor, outsider):
    for url in ENDPOINTS:
        assert editor.get(url).status_code == 404
    fomo = owner.get("/brands").json()[0]["id"]
    assert outsider.get(f"/usage/brands/{fomo}").status_code == 404
    assert fomo not in [r["brand_id"] for r in outsider.get("/usage/brands").json()["items"]]


def test_a_brands_videos_scripts_and_every_charge(owner, editor, db):
    from tests.test_breakdown import BREAKDOWN
    from tests.test_script_library import SCRIPT, _make

    me, fomo, older = _setup(owner, db)
    made = _make(owner, title="Bo tries salmon", text=SCRIPT)
    base = f"/scripts/{made['id']}"
    owner.put(f"{base}/drafts/0/breakdown", json=BREAKDOWN)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    video = db.get(Project, pid)
    ed = db.query(User).filter_by(role=Role.editor).one()
    _charge(db, enqueue(db, ed, "video-480p", {}, project=video), "5.00")
    _charge(db, enqueue(db, me, "write-claude", {"script_id": made["id"]}), "0.30")
    failed = enqueue(db, me, "video-480p", {}, project=older)
    failed.status = "failed"
    video.finished_at = utcnow()
    db.commit()

    videos = owner.get(f"/usage/brands/{fomo}/videos").json()
    rows = {v["title"]: v for v in videos["items"]}
    salmon = rows["Bo tries salmon · A"]
    assert (salmon["status"], salmon["spend_usd"], salmon["legacy"]) == ("done", 5.0, False)
    assert salmon["person"]["name"] == "Ed" and salmon["version_letter"] == "A"
    assert rows["Launch"]["status"] == "failed" and rows["Launch"]["legacy"] is True
    assert {p["name"] for p in videos["people"]} == {"Ed", "Reed"}
    done = owner.get(f"/usage/brands/{fomo}/videos", params={"status": "done"}).json()
    assert [v["title"] for v in done["items"]] == ["Bo tries salmon · A"]
    mine = owner.get(f"/usage/brands/{fomo}/videos", params={"person_id": ed.id}).json()
    assert mine["total"] == 1

    scripts = owner.get(f"/usage/brands/{fomo}/scripts").json()
    (row,) = scripts["items"]
    assert row["spend_usd"] == 5.3 and row["status"] == "done"  # writing plus its video
    assert [a["name"] for a in scripts["authors"]] == ["Reed"]

    first = owner.get("/usage/charges", params={"limit": 1}).json()
    assert len(first["items"]) == 1 and first["next_cursor"]
    rest = owner.get("/usage/charges", params={"cursor": first["next_cursor"]}).json()
    whats = [c["what"] for c in first["items"] + rest["items"]]
    assert "Script · Bo tries salmon" in whats and "Video · Bo tries salmon · A" in whats
    assert rest["next_cursor"] is None
    other = owner.get("/usage/charges", params={"brand_id": fomo + 999}).json()
    assert other["items"] == []
    for url in (f"/usage/brands/{fomo}/videos", f"/usage/brands/{fomo}/scripts", "/usage/charges"):
        assert editor.get(url).status_code == 404
