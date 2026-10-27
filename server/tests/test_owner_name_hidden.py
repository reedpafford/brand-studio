"""Current rules 4: editors never see Reed's name. A name the server sends as data (who made a
script, a video or a job, who planned or is making a version, the team list) reads "the
owner" to an editor; the owner still sees his own name."""

import re

from tests.test_script_produce import _published


def test_no_editor_visible_response_names_the_owner(app, owner, editor, db):
    base, _ = _published(owner, db, target=40)  # planned and published by Reed
    made = owner.post(f"{base}/drafts/0/produce").json()  # his video, his breakdown job
    pid, sid = made["project_id"], base.rsplit("/", 1)[1]
    ids = {"project_id": pid, "script_id": sid, "id": sid}
    paths = [f"/projects/{pid}", f"/projects/{pid}/jobs"]
    for path, ops in app.openapi()["paths"].items():  # every list an editor opens, and this
        names = set(re.findall(r"{(\w+)}", path))  # video's and script's pages
        if "get" in ops and names <= ids.keys():
            paths.append(path.format(**{k: ids[k] for k in names}))
    seen = {p: editor.get(p) for p in dict.fromkeys(paths)}
    read = {p: r.text for p, r in seen.items() if r.status_code == 200}
    assert {f"/scripts/{sid}", "/jobs", "/team/members"} <= read.keys()
    assert [p for p, text in read.items() if "Reed" in text] == []
    assert "the owner" in read[f"/scripts/{sid}"] and "the owner" in read["/jobs"]
    assert "Reed" in owner.get(f"/scripts/{sid}").text  # the owner sees his own name
