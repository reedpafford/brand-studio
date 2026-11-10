"""Reed, 9 Nov: "Just track API usage per brand (from all api providers), and spend per
video/project": each brand's dollars by provider, and each video's by provider, kind and run.
Owner only. Free."""

from datetime import timedelta

from app import director
from app.db import utcnow
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.test_usage import _charge, _setup


def _job(db, me, kind, provider, dollars=None, model=None, at=None, project=None, **input):
    job = Job(workspace_id=me.workspace_id, created_by_id=me.id, kind=kind, provider=provider,
              input={"model": model, **input} if model else input, status=JobStatus.succeeded,
              project_id=project and project.id, brand_id=project and project.brand_id,
              credits=10, created_at=at or utcnow())  # fmt: skip
    db.add(job)
    db.commit()
    if dollars is not None:
        _charge(db, job, dollars, when=at)
    return job


def _parts(rows):
    return {p["name"]: (p["usd"], p["estimated"]) for p in rows}


def test_each_brand_by_provider_voices_apart_and_list_price_marked(owner, editor, db):
    me, fomo, video = _setup(owner, db)
    _job(db, me, "video", "replicate", "4.00", "seedance-2.5", project=video)
    _job(db, me, "speech", "replicate", "0.50", "minimax-speech-2.8-hd", project=video)
    _job(db, me, "speech", "replicate", "0.25", "elevenlabs-v3", project=video)
    _job(db, me, "write-claude", "claude", "0.30", project=video)
    _job(db, me, "video", "heygen", "2.00", project=video)
    _job(db, me, "music", "suno", "0.40", project=video)
    lost = _job(db, me, "image", "replicate", project=video)  # sent, never reported back
    lost.provider_ref = "abc123"
    _job(db, me, "image", "replicate", project=video).provider_ref = "stand-in-1"  # free
    db.commit()

    row = next(r for r in owner.get("/usage/brands").json()["items"] if r["brand_id"] == fomo)
    assert _parts(row["providers"]) == {
        "Replicate": (5.03, True),  # 4.00 and the lost still at its list price (10 credits)
        "HeyGen": (2.0, False), "MiniMax": (0.5, False), "Suno (KIE)": (0.4, False),
        "Claude": (0.3, False), "ElevenLabs": (0.25, False),
    }  # fmt: skip
    assert [p["name"] for p in row["providers"]][:2] == ["Replicate", "HeyGen"]  # most first
    assert row["spend_usd"] == 8.48 and row["spend_estimated"] is True
    summary = owner.get("/usage/summary", params={"period": "all"}).json()
    assert _parts(summary["providers"]) == _parts(row["providers"])
    assert summary["freestyle"]["spend_usd"] == 0 and summary["unassigned_providers"] == []
    assert editor.get("/usage/summary").status_code == 404


def test_every_video_whole_life_by_kind_sorted_and_owner_only(owner, editor, db):
    me, fomo, launch = _setup(owner, db)
    other = Project(workspace_id=me.workspace_id, brand_id=fomo, name="Teaser",
                    created_by_id=me.id)  # fmt: skip
    old = Project(workspace_id=me.workspace_id, brand_id=fomo, name="Old", created_by_id=me.id)
    db.add_all([other, old])
    db.commit()
    long_ago = utcnow() - timedelta(days=400)
    _job(db, me, "write-claude", "claude", "0.30", project=launch, at=long_ago)
    _job(db, me, "video", "replicate", "3.00", "seedance-2.5", project=launch)
    _job(db, me, "image", "replicate", "0.10", "nano-banana-pro", project=launch)
    _job(db, me, "speech", "replicate", "0.20", "minimax-speech-2.8-hd", project=other)
    _job(db, me, "video", "replicate", "9.00", "seedance-2.5", project=old, at=long_ago)

    month = owner.get("/usage/videos").json()
    assert [(v["title"], v["spend_usd"]) for v in month["items"]] == [
        ("Launch", 3.4),
        ("Teaser", 0.2),
    ]  # whole life, most first; Old had nothing this month
    first = month["items"][0]
    assert [k["name"] for k in first["kinds"]] == ["Claude's thinking", "Stills", "Takes"]
    assert _parts(first["providers"]) == {"Replicate": (3.1, False), "Claude": (0.3, False)}
    assert month["kinds"] == ["Claude's thinking", "Stills", "Takes", "Voice"]
    assert first["brand"] == "fomo"
    every = owner.get("/usage/videos", params={"period": "all", "sort": "title"}).json()
    assert [v["title"] for v in every["items"]] == ["Launch", "Old", "Teaser"]
    assert editor.get("/usage/videos").status_code == 404
    assert editor.get(f"/usage/videos/{launch.id}").status_code == 404


def test_one_video_by_run_first_run_then_revisions(owner, db):
    me, _, video = _setup(owner, db)
    now = utcnow()

    def turn(run, minutes):
        _job(db, me, "write-claude", "claude", "0.05", project=video,
             at=now + timedelta(minutes=minutes), step=director.STEP,
             **{director.RUN: {"id": run}})  # fmt: skip

    _job(db, me, "image", "replicate", "0.20", "nano-banana-pro", project=video, at=now)  # a look
    turn("a", 1)
    _job(db, me, "video", "replicate", "2.00", "seedance-2.5", project=video,
         at=now + timedelta(minutes=2))  # fmt: skip
    turn("a", 3)
    turn("b", 60)  # a revision
    _job(db, me, "video", "replicate", "1.00", "seedance-2.5", project=video,
         at=now + timedelta(minutes=61))  # fmt: skip

    out = owner.get(f"/usage/videos/{video.id}").json()
    assert out["spend_usd"] == 3.35 and out["unreported"] is False
    assert [(r["name"], r["usd"]) for r in out["runs"]] == [
        ("Before the first run", 0.2),
        ("First run", 2.1),
        ("Revision 1", 1.05),
    ]
    assert _parts(out["kinds"]) == {"Claude's thinking": (0.15, False), "Stills": (0.2, False),
                                    "Takes": (3.0, False)}  # fmt: skip
