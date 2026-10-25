"""Download every clip at once: the picked takes, or every take."""

import io
import zipfile

from app.models.clips import ProjectClip
from app.models.files import StoredFile
from app.models.projects import Project
from tests.helpers import assert_hidden
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


def _names(response) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return {n: archive.read(n) for n in archive.namelist()}


def test_zip_of_picked_takes_or_every_take(app, db, editor, outsider, setup, clip):  # noqa: F811
    base = f"/projects/{setup['project']}"
    assert editor.get(f"{base}/clips.zip").status_code == 409  # no takes yet
    red, blue = _mp4("red"), _mp4("blue")
    fake = FakeSeedance([red, blue])
    for _ in range(2):
        editor.post(f"{base}/clips/{clip['id']}/generate")
        _work(app, db, fake)
    takes = editor.get(f"{base}/clips").json()[0]["takes"]
    editor.post(f"{base}/clips/{clip['id']}/takes/{takes[0]['id']}/pick")
    first = db.get(ProjectClip, clip["id"])
    second = ProjectClip(  # QA #245: a clip with no picked take yet
        project_id=first.project_id, breakdown_id=first.breakdown_id, clip_id="c2", seconds=5,
        prompt="x",
    )  # fmt: skip
    db.add(second)
    db.commit()
    editor.get(f"{base}/clips.zip")
    assert db.get(Project, setup["project"]).finished_at is None  # 1 of 2: not the whole video
    db.delete(second)
    db.commit()

    picked = editor.get(f"{base}/clips.zip")
    assert picked.status_code == 200 and picked.headers["content-type"] == "application/zip"
    assert "attachment" in picked.headers["content-disposition"]
    assert _names(picked) == {"c1-take1.mp4": red}
    project = db.get(Project, setup["project"])
    db.refresh(project)
    first = project.finished_at
    assert first is not None  # the picked takes, sent in full: the video is done
    every = _names(editor.get(f"{base}/clips.zip", params={"all_takes": True}))
    assert every == {"c1/take1.mp4": red, "c1/take2.mp4": blue}
    editor.get(f"{base}/clips.zip")
    db.refresh(project)
    assert project.finished_at == first  # set once
    assert_hidden(outsider, [("GET", f"{base}/clips.zip")])
    key = db.get(StoredFile, takes[1]["file_id"]).key
    app.state.storage.delete(key)  # take 2's video went missing
    gone = editor.get(f"{base}/clips.zip", params={"all_takes": True})
    assert gone.status_code == 409 and gone.json()["detail"].startswith("c1/take2.mp4")


def test_a_version_is_done_once_its_video_is_stitched(owner, editor, db):
    from app.db import utcnow
    from app.models.clips import FinalVideo
    from tests.conftest import upload
    from tests.test_breakdown import BREAKDOWN
    from tests.test_script_library import SCRIPT, _make

    made = _make(owner, text=SCRIPT)
    base = f"/scripts/{made['id']}"
    owner.put(f"{base}/drafts/0/breakdown", json=BREAKDOWN)
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    assert owner.get(base).json()["status"] == "in_production"
    db.add(FinalVideo(project_id=pid, file_id=upload(editor), take_ids=[]))
    db.get(Project, pid).finished_at = utcnow()  # as stitching does
    db.commit()
    script = owner.get(base).json()
    assert (script["versions"][0]["status"], script["status"]) == ("done", "done")
