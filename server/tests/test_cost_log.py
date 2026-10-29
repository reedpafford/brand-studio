"""Cost log (flows OR4): what each project cost (owner, dollars), the brand's videos by project,
and an editor's own videos and quick clips in credits only. Free."""

from app.models.accounts import Role, User
from app.models.jobs import Job
from app.models.projects import Project
from app.routes.jobs import enqueue
from tests.conftest import file_into
from tests.test_usage import _charge, _setup


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def test_each_project_costs_its_videos_scripts_and_quick_clips_once(owner, editor, db):
    me, fomo, video = _setup(owner, db)
    fid = owner.post(f"/brands/{fomo}/folders", json={"name": "Launch"}).json()["id"]
    script = owner.post("/scripts", json={"brand_id": fomo, "title": "Gut"}).json()["id"]
    words = owner.post(f"/brands/{fomo}/folders", json={"name": "Words"}).json()["id"]
    file_into(owner, "script", script, words)  # in another project than its video
    file_into(owner, "video", video.id, fid)
    # A video's job that names its script counts once, with the video, never with the script
    _charge(db, enqueue(db, me, "video-480p", {"script_id": script}, project=video), "2.00")
    writing = enqueue(db, me, "write-claude", {"script_id": script, "brand_id": fomo})
    _charge(db, writing, "0.30")  # the script's own writing
    quick = enqueue(db, me, "video-480p", {"brand_id": fomo})
    _charge(db, quick, "1.00")
    file_into(owner, "clip", quick.id, fid)
    _charge(db, enqueue(db, me, "video-480p", {"brand_id": fomo}), "0.50")  # not filed
    video.finished_at = video.created_at
    db.commit()

    rows = owner.get(f"/usage/brands/{fomo}/projects").json()["items"]
    assert [(r["name"], r["spend_usd"], r["videos"], r["finished"]) for r in rows] == [
        ("Launch", 3.0, 1, 1), ("Words", 0.3, 0, 0), ("No project", 0.5, 0, 0)]  # fmt: skip
    assert rows[0]["cost_per_finished_usd"] == 2.0 and rows[0]["credits"] > 0
    listed = owner.get(f"/usage/brands/{fomo}/videos", params={"folder": fid}).json()["items"]
    assert [(v["project_id"], v["folder_id"]) for v in listed] == [(video.id, fid)]
    loose = owner.get(f"/usage/brands/{fomo}/videos", params={"folder": "none"}).json()
    assert loose["items"] == []
    owner.delete(f"/folders/{fid}")  # spend follows where items are filed now
    rows = owner.get(f"/usage/brands/{fomo}/projects").json()["items"]
    assert [(r["name"], r["spend_usd"]) for r in rows] == [("Words", 0.3), ("No project", 3.5)]
    assert editor.get(f"/usage/brands/{fomo}/projects").status_code == 404


def test_an_editor_sees_their_own_videos_and_quick_clips_in_credits_only(owner, editor, db):
    me, fomo, theirs = _setup(owner, db)  # the owner's video
    _charge(db, enqueue(db, me, "video-480p", {}, project=theirs), "5.00")
    made = editor.post("/projects", json={"brand_id": fomo, "name": "Mine"}).json()["id"]
    them = db.query(User).filter_by(role=Role.editor).one()
    mine = db.get(Project, made)
    _charge(db, enqueue(db, them, "video-480p", {}, project=mine), "1.00")
    clip = enqueue(db, them, "video-480p", {"brand_id": fomo})
    _charge(db, clip, "0.40")

    out = editor.get("/usage/mine", params={"brand_id": fomo}).json()
    assert [v["project_id"] for v in out["videos"]] == [made]  # never the owner's video
    assert not any("usd" in k or "dollar" in k for k in _keys(out))  # no dollars, anywhere
    step = float(db.get(Job, clip.id).credits)
    assert out["quick_clip_credits"] == step > 0
    assert out["credits"] == out["videos"][0]["credits"] + step
    assert out["projects"] == [{"folder_id": None, "name": "No project", "videos": 1,
                                "credits": out["videos"][0]["credits"]}]  # fmt: skip
    assert editor.get("/usage/mine", params={"brand_id": fomo, "folder": "x"}).status_code == 422


def test_an_editors_own_script_writing_shows_on_their_week_and_no_one_elses(owner, editor, db):
    me, fomo, _ = _setup(owner, db)
    them = db.query(User).filter_by(role=Role.editor).one()
    script = editor.post("/scripts", json={"brand_id": fomo, "title": "Gut"}).json()["id"]
    mine = enqueue(db, them, "write-claude", {"script_id": script, "step": "script_draft"})
    enqueue(db, me, "write-claude", {"script_id": script, "step": "enhance"})  # the owner's

    out = editor.get("/usage/mine", params={"brand_id": fomo}).json()
    step = float(db.get(Job, mine.id).credits)
    assert out["scripts"] == [{"script_id": script, "title": "Gut", "credits": step}]
    assert out["script_credits"] == out["credits"] == step > 0
    assert not any("usd" in k or "dollar" in k for k in _keys(out))
    assert owner.get("/usage/mine", params={"brand_id": fomo}).json()["script_credits"] == float(
        db.query(Job).filter(Job.created_by_id == me.id).one().credits)  # fmt: skip


def test_an_editors_week_lists_every_charge_its_allowance_counts(owner, editor, db):
    """QA-3: Mine's week adds up to the week's used, built from the allowance's own query:
    their video (from a script they wrote), a quick clip, a script's writing and a look made
    in Cast & places with no video ("A look"), never the owner's."""
    from app.credits import quick_clip_used
    from app.models.script_library import ScriptDraft

    me, fomo, _ = _setup(owner, db)
    them = db.query(User).filter_by(role=Role.editor).one()
    script = editor.post("/scripts", json={"brand_id": fomo, "title": "Gut"}).json()["id"]
    draft = db.query(ScriptDraft).filter_by(script_id=script).one()
    video = Project(workspace_id=them.workspace_id, brand_id=fomo, name="Gut",
                    created_by_id=them.id, script_draft_id=draft.id)  # fmt: skip
    db.add(video)
    db.commit()
    enqueue(db, them, "video-480p", {}, project=video)
    enqueue(db, them, "video-480p", {"brand_id": fomo})  # a quick clip
    enqueue(db, them, "write-claude", {"script_id": script, "step": "script_draft"})
    enqueue(db, them, "image", {"step": "sheet", "library_item_id": 1, "brand_id": fomo})
    enqueue(db, me, "video-480p", {"brand_id": fomo})  # the owner's: never on the editor's

    week = editor.get("/usage/mine", params={"brand_id": fomo}).json()["week"]
    assert week["used"] == float(quick_clip_used(db, them)) > 0
    assert round(sum(line["credits"] for line in week["lines"]), 3) == round(week["used"], 3)
    assert {line["label"] for line in week["lines"]} == {"Videos", "Quick clips", "Scripts",
                                                         "A look"}  # fmt: skip
    assert week["allowance"] is not None
    assert not any("usd" in k or "dollar" in k for k in _keys(week))
    assert owner.get("/usage/mine", params={"brand_id": fomo}).json()["week"]["allowance"] is None
