"""Media (flows OR2): every still, sheet, take, song and final video of a brand, newest first,
with who sees what, the filters, a deleted video's media and pages. Free."""

import uuid

from fastapi.testclient import TestClient

from app.db import utcnow
from app.models.brands import Brand
from app.models.clips import FinalVideo, ProjectClip
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.routes import media
from tests.conftest import PASSWORD, upload
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


def _file(db, workspace_id, content_type="image/png") -> int:
    made = StoredFile(workspace_id=workspace_id, key=uuid.uuid4().hex, filename="x",
                      content_type=content_type, size=1, sha256="0" * 64)  # fmt: skip
    db.add(made)
    db.commit()
    return made.id


def _media(client, brand, **params):
    return client.get(f"/brands/{brand}/media", params=params).json()


def test_media_lists_what_was_made_and_who_sees_it(app, db, owner, editor, setup, clip):  # noqa: F811
    base, pid = f"/projects/{setup['project']}", setup["project"]
    project = db.get(Project, pid)
    brand, ws = project.brand_id, project.workspace_id
    assert _media(editor, brand, kind="final") == {"items": [], "next": None}  # nothing yet
    pc = db.get(ProjectClip, clip["id"])
    still = upload(editor)
    mom = db.query(LibraryItem).filter_by(name="Mom").one()
    mom.brands = [db.get(Brand, brand)]  # in the brand's Cast & places
    db.add(StoryboardFrame(project_id=pid, breakdown_id=pc.breakdown_id, clip_id="c1",
                           shot_id="s1", prompt="x", file_id=still))  # fmt: skip
    db.commit()
    editor.post(f"{base}/clips/{clip['id']}/generate")
    job = db.query(Job).filter(Job.input["step"].as_string() == "clip_take").one()
    files = job.input["files"]
    job.input = {**job.input, "files": {**files, "reference_images": [still]}}  # its first frame
    db.commit()
    _work(app, db, FakeSeedance([_mp4("red")]))
    db.add(FinalVideo(project_id=pid, file_id=_file(db, ws, "video/mp4"), take_ids=[],
                      created_by_id=project.created_by_id))  # fmt: skip
    theirs = Job(workspace_id=ws, kind="video", provider="fake", input={}, credits=0,
                 brand_id=brand, status=JobStatus.succeeded, created_by_id=None,
                 output={"file_ids": [_file(db, ws, "video/mp4")]})  # fmt: skip
    db.add(theirs)
    db.commit()

    seen = _media(editor, brand)["items"]
    kinds = {i["kind"] for i in seen}
    assert kinds == {"still", "sheet", "take", "final"}  # not someone else's quick clip
    take = next(i for i in seen if i["kind"] == "take")
    assert (take["poster_file_id"], take["open_step"]) == (still, "clips")
    assert take["video_name"] == "Dip"
    assert take["made_by"]["id"] == project.created_by_id and not take["from_deleted_video"]
    assert [i["made_at"] for i in seen] == sorted((i["made_at"] for i in seen), reverse=True)
    quick = [i for i in _media(owner, brand)["items"] if i["open_step"] == "quick"]
    assert [(i["kind"], i["made_by"], i["project_id"]) for i in quick] == [("take", None, None)]
    assert {i["kind"] for i in _media(owner, brand, kind="take")["items"]} == {"take"}
    assert _media(editor, brand, by=project.created_by_id, kind="sheet")["items"] == []  # no maker

    fid = editor.post(f"/brands/{brand}/folders", json={"name": "Launch"}).json()["id"]
    editor.post("/folders/file", json={"kind": "video", "id": pid, "folder_id": fid})
    filed = _media(editor, brand, folder=fid)["items"]
    assert {i["kind"] for i in filed} == {"still", "take", "final"}  # not the brand's sheets
    assert {i["folder_id"] for i in filed} == {fid}
    assert _media(editor, brand, folder="none")["items"] == []
    loose = _media(owner, brand, folder="none")["items"]
    assert [i["open_step"] for i in loose] == ["quick"]  # the quick clip in No project
    assert owner.get(f"/brands/{brand}/media", params={"folder": "x"}).status_code == 422

    project.archived_at = utcnow()
    db.commit()
    gone = _media(editor, brand, kind="final")["items"]
    assert [i["from_deleted_video"] for i in gone] == [True]
    maker = {"id": project.created_by_id, "name": "Ed"}  # who may restore it, with the owner
    assert [i["deleted_video_by"] for i in gone] == [maker]
    assert [i["deleted_video_released"] for i in gone] == [False]  # deleted, not released
    assert [i["deleted_video_by"] for i in _media(owner, brand, kind="final")["items"]] == [maker]
    everything = _media(owner, brand)["items"]
    assert not [i for i in everything if i["deleted_video_by"] and not i["from_deleted_video"]]
    token = owner.post("/team/invites", json={"email": "sam@example.com"}).json()["token"]
    with TestClient(app) as sam:
        sam.post("/auth/accept-invite", json={"token": token, "name": "Sam", "password": PASSWORD})
        seen = _media(sam, brand)["items"]
        mine = [i for i in seen if i["project_id"] == pid or i["deleted_video_by"]]
        assert seen and not mine  # only the brand's own sheets


def test_pages_walk_the_list_once(app, db, owner, monkeypatch):
    brand = owner.get("/brands").json()[0]["id"]
    ws = owner.get("/auth/me").json()["workspace_id"]
    for _ in range(5):
        db.add(Job(workspace_id=ws, kind="image", provider="fake", input={}, credits=0,
                   brand_id=brand, status=JobStatus.succeeded,
                   output={"file_ids": [_file(db, ws)]}))  # fmt: skip
    db.commit()
    monkeypatch.setattr(media, "PAGE", 2)
    keys, before = [], None
    while True:
        page = _media(owner, brand, **({"before": before} if before else {}))
        keys += [i["key"] for i in page["items"]]
        if not (before := page["next"]):
            break
    assert len(keys) == len(set(keys)) == 5
    bad = owner.get(f"/brands/{brand}/media", params={"before": "nope"})
    assert bad.status_code == 422
