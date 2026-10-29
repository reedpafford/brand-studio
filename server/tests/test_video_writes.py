"""Every change to a video is for whoever made it, or the owner (Producer, after QA-4 on #957);
other editors can still open and read it. Driven from the routes themselves, so a new write
press on a video is covered without editing this test."""

import re

from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_script_produce import _second_editor

# Writes on a video with their own rule, said here so each stays deliberate:
OWN_RULE = {
    ("post", "/projects/{project_id}/release"): "the owner, or whoever is making its version",
    ("post", "/projects/{project_id}/approve"): "owner only (Approvals)",
    ("post", "/projects/{project_id}/settings/preview"): "a read: what a switch would cost",
}


def _writes(app) -> list[tuple[str, str]]:
    paths = app.openapi()["paths"]
    return [(m, p) for p, ops in paths.items() if "{project_id}" in p
            for m in ops if m in ("post", "put", "patch", "delete")
            and (m, p) not in OWN_RULE]  # fmt: skip


def test_a_second_editor_can_read_a_video_but_never_change_it(app, db, owner, editor, setup):  # noqa: F811
    pid = setup["project"]
    two, _ = _second_editor(app, owner, db)
    writes = _writes(app)
    assert len(writes) > 60  # storyboard, clips, review, final cut, cast, settings, plan, …
    for method, path in writes:
        url = re.sub(r"\{(\w+)\}", lambda m: str(pid) if m[1] == "project_id" else "1", path)
        said = two.request(method.upper(), url, json={})
        assert said.status_code == 403, f"{method.upper()} {path}: {said.status_code}"
    assert two.get(f"/projects/{pid}").status_code == 200  # reads stay open
    assert two.get(f"/projects/{pid}/script").status_code == 200

    for who in (editor, owner):  # whoever made it, and the owner, get through
        assert who.patch(f"/projects/{pid}", json={"name": "Dip again"}).status_code == 200


def test_a_videos_own_look_and_its_jobs_are_the_makers(app, db, owner, editor, setup):  # noqa: F811
    pid = setup["project"]
    two, _ = _second_editor(app, owner, db)
    project_look = LibraryItem(workspace_id=1, kind="character", name="Nate",
                               owner_project_id=pid)  # fmt: skip
    db.add(project_look)
    job = Job(workspace_id=1, kind="image", provider="fake", project_id=pid, input={},
              status=JobStatus.queued, created_by_id=None)  # fmt: skip
    db.add(job)
    db.commit()
    look = f"/library/character/{project_look.id}"
    assert two.patch(look, json={"name": "Nate 2"}).status_code == 403
    assert two.post(f"{look}/sheet/approve").status_code == 403
    assert editor.patch(look, json={"name": "Nate 2"}).status_code == 200
    assert two.post(f"/jobs/{job.id}/cancel").status_code == 403
    assert editor.post(f"/jobs/{job.id}/cancel").status_code == 200  # whoever made the video
