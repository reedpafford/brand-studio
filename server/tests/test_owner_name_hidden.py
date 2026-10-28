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


def test_every_editor_get_with_its_ids_hides_the_owners_name_and_email(app, owner, editor, db):
    """Builder-Screens-3: created_by_name could still carry Reed's name. Every GET an editor
    can open, with each id filled in (a script's versions and history, a look's versions, a
    job, a video and its parts), never names the owner or shows his email (rule 4)."""
    base, mia = _published(owner, db, target=40)
    sid = int(base.rsplit("/", 1)[1])
    made = owner.post(f"{base}/drafts/0/produce").json()
    pid = made["project_id"]
    job = owner.get("/jobs").json()[0]["id"]
    slot = owner.get(base).json()["cast"][0]["id"]
    fomo = owner.get("/brands").json()[0]["id"]
    ids = {"project_id": pid, "script_id": sid, "slot": 0, "item_id": mia, "kind": "character",
           "job_id": job, "brand_id": fomo, "version": 1, "slot_id": slot}  # fmt: skip
    read = {}
    for path, ops in app.openapi()["paths"].items():
        names = set(re.findall(r"{(\w+)}", path))
        if "get" in ops and names <= ids.keys():
            url = path.format(**{k: ids[k] for k in names})
            if (r := editor.get(url)).status_code == 200:
                read[url] = r.text
    assert len(read) > 30  # the crawl reached the video's, script's and look's pages
    assert [p for p, text in read.items() if "Reed" in text or "reed@example.com" in text] == []
