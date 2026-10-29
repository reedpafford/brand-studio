"""Cost log (flows OR4): what each project cost (owner, dollars), the brand's videos by project,
and an editor's own videos and quick clips in credits only. Free."""

from app.models.accounts import Role, User
from app.models.jobs import Job
from app.models.projects import Project
from app.routes.jobs import enqueue
from tests.test_usage import _charge, _setup


def _file(client, kind, item_id, folder_id):
    return client.post("/folders/file", json={"kind": kind, "id": item_id, "folder_id": folder_id})


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
    _file(owner, "script", script, words)  # in another project than its video
    _file(owner, "video", video.id, fid)
    # A video's job that names its script counts once, with the video, never with the script
    _charge(db, enqueue(db, me, "video-480p", {"script_id": script}, project=video), "2.00")
    writing = enqueue(db, me, "write-claude", {"script_id": script, "brand_id": fomo})
    _charge(db, writing, "0.30")  # the script's own writing
    quick = enqueue(db, me, "video-480p", {"brand_id": fomo})
    _charge(db, quick, "1.00")
    _file(owner, "clip", quick.id, fid)
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
