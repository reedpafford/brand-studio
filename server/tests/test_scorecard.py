"""Spend you can forecast: credits per second by (format, look), the forecast's basis, and
the owner's score on a finished video."""

from decimal import Decimal

from app import scorecard
from app.db import utcnow
from app.models.accounts import Role, User
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft


def _draft(db, me, brand_id, kind="story", look="house", target=10):
    script = Script(workspace_id=me.workspace_id, brand_id=brand_id, title="S", kind=kind,
                    look=look, created_by_id=me.id)  # fmt: skip
    db.add(script)
    db.flush()
    draft = ScriptDraft(script_id=script.id, slot=0, text="Hi.", status="approved",
                        target_seconds=target)  # fmt: skip
    db.add(draft)
    db.flush()
    return draft


def _finished(db, me, brand_id, seconds, credits, takes, kind="story", look="house",
              score=None, director=0):  # fmt: skip
    """A finished video of one clip with `takes` takes, charged `credits` (`director` of them
    the director's own turns)."""
    draft = _draft(db, me, brand_id, kind, look, seconds)
    video = Project(workspace_id=me.workspace_id, brand_id=brand_id, name="V", look=look,
                    script_draft_id=draft.id, finished_at=utcnow(), score=score)  # fmt: skip
    db.add(video)
    db.flush()
    clip = ProjectClip(project_id=video.id, breakdown_id=1, clip_id="c1", seconds=seconds,
                       prompt="p")  # fmt: skip
    db.add(clip)
    db.flush()
    made = [ClipTake(clip_id=clip.id, number=n + 1, job_id=1, file_id=1) for n in range(takes)]
    db.add_all(made)
    db.flush()
    clip.picked_take_id = made[-1].id
    for own, amount in ((None, credits - director), ({"id": "r1"}, director)):
        if amount:
            db.add(Job(workspace_id=me.workspace_id, kind="video-480p", provider="fake",
                       input={"director_run": own} if own else {}, status="succeeded",
                       project_id=video.id, credits=Decimal(amount)))  # fmt: skip
    db.commit()
    return video


def _me(db):
    return db.query(User).filter_by(role=Role.owner).one()


def _fomo(owner):
    return owner.get("/brands").json()[0]["id"]


def test_credits_per_second_redo_rate_and_average_score(owner, db):
    me, fomo = _me(db), _fomo(owner)
    _finished(db, me, fomo, 10, 20, takes=2, score=4, director=5)
    _finished(db, me, fomo, 10, 40, takes=1, score=5)
    _finished(db, me, fomo, 10, 9, takes=1, kind="song")  # another pair, kept apart
    rows = {(r["format"], r["look"]): r for r in owner.get("/usage/by-format-and-style").json()}
    row = rows[("dialogue", "house")]
    assert (row["videos"], row["seconds"], row["credits"]) == (2, 20, 60)
    assert row["credits_per_second"] == 3 and row["redo_rate"] == 1.5  # 3 takes over 2 clips
    assert row["director_credits"] == 5 and row["average_score"] == 4.5
    assert rows[("song", "house")]["average_score"] is None


def test_forecast_uses_the_pairs_rate_from_three_finished_videos(owner, db):
    me, fomo = _me(db), _fomo(owner)
    draft = _draft(db, me, fomo, target=20)
    for _ in range(2):
        _finished(db, me, fomo, 10, 30, takes=1)
    asked = scorecard.forecast(db, draft)
    assert asked["basis"] == "estimate" and asked["credits"] > 0  # two is too few
    _finished(db, me, fomo, 10, 30, takes=1)  # three videos at 3 credits a second
    assert scorecard.forecast(db, draft) == {"credits": 60.0, "basis": "3 finished videos"}
    other = _draft(db, me, fomo, kind="song", target=20)  # a song has no history of its own
    assert scorecard.forecast(db, other)["basis"] == "estimate"


def test_only_the_owner_sets_the_score(owner, editor, db):
    me, fomo = _me(db), _fomo(owner)
    done = _finished(db, me, fomo, 10, 20, takes=1)
    body = {"score": 4, "note": "Good pace"}
    assert editor.put(f"/projects/{done.id}/score", json=body).status_code == 404
    assert owner.put(f"/projects/{done.id}/score", json={"score": 6}).status_code == 422
    assert owner.put(f"/projects/{done.id}/score", json=body).json()["score"] == 4
    assert owner.get(f"/projects/{done.id}/scorecard").json()["note"] == "Good pace"
    assert editor.get(f"/projects/{done.id}/scorecard").json()["score"] is None  # not theirs
    open_ = db.get(Project, done.id)
    open_.finished_at = None
    db.commit()
    assert owner.put(f"/projects/{open_.id}/score", json=body).status_code == 409


def test_an_editor_sees_credits_never_dollars(owner, editor, db):
    me, fomo = _me(db), _fomo(owner)
    done = _finished(db, me, fomo, 10, 20, takes=1)
    done.forecast_credits, done.forecast_basis = Decimal(25), "estimate"
    db.commit()
    got = editor.get(f"/projects/{done.id}/scorecard")
    assert got.status_code == 200
    assert got.json()["actual_credits"] == 20 and got.json()["within_forecast"] is True
    assert not any("usd" in key or "dollar" in key for key in got.json())
    assert editor.get("/usage/by-format-and-style").status_code == 404
