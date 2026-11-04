"""Folders (flows OR1, v6 S0-01, S1): a brand's free folders, inside each other, of video ideas,
scripts and quick clips. Make (at the top or inside), file one or many (with Undo), filter,
rename, move (never inside itself), delete (with the folders inside; their ideas move to
Unsorted, Undo brings them back), the rail's tree and an open folder's ideas with their status
words, and the owner's and editors' rights. Free."""

from datetime import timedelta

from app import director, folders, ideas
from app.db import utcnow
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.conftest import file_into, first_brand
from tests.test_breakdown import BREAKDOWN
from tests.test_script_produce import _published


def _folder(client, brand, name, parent=None):
    made = client.post(f"/brands/{brand}/folders", json={"name": name, "parent_id": parent})
    assert made.status_code == 201, made.text
    return made.json()["id"]


def _idea(db, brand, by, name, folder=None, **extra) -> int:
    user = db.get(User, by)
    p = Project(workspace_id=user.workspace_id, brand_id=brand, name=name, created_by_id=by,
                folder_id=folder, **extra)  # fmt: skip
    db.add(p)
    db.commit()
    return p.id


def _job(db, pid, status, step="clip_take", credits=4, **data) -> Job:
    p = db.get(Project, pid)
    job = Job(workspace_id=p.workspace_id, created_by_id=p.created_by_id, kind="video",
              provider="fake", input={"step": step, **data}, project_id=pid, brand_id=p.brand_id,
              credits=credits, status=status)  # fmt: skip
    db.add(job)
    db.commit()
    return job


def _ids(db):
    owner = db.query(User).filter_by(role="owner").one().id
    return owner, db.query(User).filter_by(role="editor").one().id


def test_a_script_is_filed_listed_and_undone(owner, editor):
    brand = first_brand(owner)
    made = editor.post(f"/brands/{brand}/folders", json={"name": "November launch"})
    assert made.status_code == 201 and made.json()["can_manage"]
    assert made.json()["parent_id"] is None
    again = owner.post(f"/brands/{brand}/folders", json={"name": "november launch"})
    assert (again.status_code, again.json()["detail"]) == (
        409,
        folders.TAKEN.format("november launch"),
    )
    fid = made.json()["id"]
    script = editor.post("/scripts", json={"brand_id": brand, "title": "Gut"}).json()["id"]
    filed = file_into(editor, "script", script, fid).json()
    assert filed == {"folder_id": fid, "was": [{"id": script, "folder_id": None}]}
    assert [s["id"] for s in editor.get(f"/scripts?folder={fid}").json()] == [script]
    assert script not in [s["id"] for s in editor.get("/scripts?folder=none").json()]
    (row,) = editor.get(f"/brands/{brand}/folders").json()
    assert row["items"] == {"scripts": 1, "videos": 0, "clips": 0}
    back = file_into(editor, "script", script, None).json()["was"]
    assert back == [{"id": script, "folder_id": fid}]  # Undo


def test_folders_go_inside_folders_named_apart_from_their_neighbours_only(owner, editor):
    brand = first_brand(owner)
    rants = _folder(owner, brand, "Dr. Pickle rants")
    hang = _folder(editor, brand, "Hangovers", rants)
    week = _folder(owner, brand, "Week of 3 Nov")
    assert _folder(owner, brand, "Hangovers", week)  # the same name in another folder is fine
    same = owner.post(f"/brands/{brand}/folders", json={"name": "hangovers", "parent_id": rants})
    assert (same.status_code, same.json()["detail"]) == (409, folders.TAKEN.format("hangovers"))
    rows = owner.get(f"/brands/{brand}/folders").json()
    assert {(f["name"], f["parent_id"]) for f in rows if f["id"] == hang} == {("Hangovers", rants)}

    # Script lists filtered by a folder show the folders inside it too (S1-05)
    script = owner.post("/scripts", json={"brand_id": brand, "title": "Deep"}).json()["id"]
    file_into(owner, "script", script, hang)
    assert [s["id"] for s in owner.get(f"/scripts?folder={rants}").json()] == [script]


def test_moving_a_folder_never_puts_it_inside_itself_or_another_brand(owner, editor):
    brand = first_brand(owner)
    other = owner.get("/brands").json()[1]["id"]  # Iron Paws
    top = _folder(owner, brand, "Top")
    mid = _folder(owner, brand, "Mid", top)
    low = _folder(owner, brand, "Low", mid)
    theirs = _folder(owner, other, "Theirs")
    for into in (top, low):
        no = owner.patch(f"/folders/{top}", json={"parent_id": into})
        assert (no.status_code, no.json()["detail"]) == (409, folders.INSIDE_ITSELF)
    no = owner.patch(f"/folders/{mid}", json={"parent_id": theirs})
    assert (no.status_code, no.json()["detail"]) == (409, folders.OTHER_BRAND)
    assert editor.patch(f"/folders/{mid}", json={"parent_id": None}).status_code == 403
    moved = owner.patch(f"/folders/{low}", json={"parent_id": None}).json()
    assert (moved["parent_id"], moved["name"]) == (None, "Low")
    renamed = owner.patch(f"/folders/{low}", json={"name": "Lower"}).json()
    assert (renamed["parent_id"], renamed["name"]) == (None, "Lower")  # a rename stays put
    _folder(owner, brand, "Mid")
    clash = owner.patch(f"/folders/{mid}", json={"parent_id": None})
    assert (clash.status_code, clash.json()["detail"]) == (409, folders.TAKEN.format("Mid"))


def test_deleting_a_folder_takes_the_folders_inside_and_undo_brings_them_back(owner, editor, db):
    brand = first_brand(owner)
    me, _ = _ids(db)
    friday = _folder(owner, brand, "Black Friday")
    deals = _folder(owner, brand, "Deals", friday)
    keep = _folder(owner, brand, "Keep")
    ideas_in = [
        _idea(db, brand, me, n, f)
        for n, f in (("Last-minute gift", friday), ("Cyber Monday gut", deals), ("Deal", deals))
    ]
    _idea(db, brand, me, "Elsewhere", keep)
    script = owner.post("/scripts", json={"brand_id": brand, "title": "S"}).json()["id"]
    file_into(owner, "script", script, deals)
    assert editor.delete(f"/folders/{friday}").status_code == 403  # the owner's folder
    mine = _folder(editor, brand, "Mine")
    _folder(owner, brand, "Reed's, inside", mine)
    no = editor.delete(f"/folders/{mine}")  # never someone else's folder inside it
    assert (no.status_code, no.json()["detail"]) == (403, folders.OTHERS_INSIDE)
    assert owner.delete(f"/folders/{mine}").json() == {"moved": 0, "ideas": 0}
    assert owner.delete(f"/folders/{friday}").json() == {"moved": 4, "ideas": 3}
    loose = owner.get(f"/brands/{brand}/ideas?folder=none").json()
    assert {i["id"] for i in loose["ideas"]} == set(ideas_in)
    assert {i["folder_id"] for i in loose["ideas"]} == {None}
    assert script in [s["id"] for s in owner.get("/scripts?folder=none").json()]
    assert [f["name"] for f in owner.get(f"/brands/{brand}/folders").json()] == ["Keep"]
    other = _folder(owner, brand, "Black Friday")  # a deleted one never blocks
    back = owner.post(f"/folders/{friday}/restore")
    assert (back.status_code, back.json()["detail"]) == (409, folders.TAKEN.format("Black Friday"))
    owner.patch(f"/folders/{other}", json={"name": "Black Friday 2"})
    assert owner.post(f"/folders/{friday}/restore").status_code == 200  # Undo
    tree = owner.get(f"/brands/{brand}/tree").json()
    bf = next(f for f in tree["folders"] if f["name"] == "Black Friday")
    assert (bf["count"], [f["name"] for f in bf["folders"]]) == (3, ["Deals"])
    assert tree["unsorted"]["count"] == 0


def test_many_ideas_move_at_once_with_undo_and_editors_move_only_their_own(owner, editor, db):
    brand = first_brand(owner)
    me, ed = _ids(db)
    other = owner.get("/brands").json()[1]["id"]  # Iron Paws
    to = _folder(editor, brand, "UGC testimonials")
    a, b = _idea(db, brand, ed, "Mine"), _idea(db, brand, ed, "Also mine", to)
    reeds = _idea(db, brand, me, "Reed's")
    moved = editor.post("/folders/file", json={"kind": "video", "ids": [a, b], "folder_id": to})
    assert moved.json()["was"] == [{"id": a, "folder_id": None}, {"id": b, "folder_id": to}]
    no = editor.post("/folders/file", json={"kind": "video", "ids": [a, reeds], "folder_id": None})
    assert no.status_code == 403 and db.get(Project, a).folder_id == to  # all or nothing
    assert owner.post("/folders/file", json={"kind": "video", "ids": [reeds],
                                             "folder_id": to}).status_code == 200  # fmt: skip
    theirs = _idea(db, other, me, "Iron Paws idea")
    no = owner.post("/folders/file", json={"kind": "video", "ids": [theirs], "folder_id": to})
    assert (no.status_code, no.json()["detail"]) == (409, folders.OTHER_BRAND)


def test_who_files_what_videos_and_quick_clips(app, owner, editor, db):
    brand = first_brand(owner)
    fid = editor.post(f"/brands/{brand}/folders", json={"name": "Clips"}).json()["id"]
    me = editor.get("/auth/me").json()
    clip = Job(workspace_id=me["workspace_id"], kind="video", provider="fake", input={},
               credits=0, brand_id=brand, created_by_id=me["id"])  # fmt: skip
    theirs = Job(workspace_id=me["workspace_id"], kind="video", provider="fake", input={},
                 credits=0, brand_id=brand, created_by_id=None)  # fmt: skip
    db.add_all([clip, theirs])
    db.commit()
    assert file_into(editor, "clip", clip.id, fid).status_code == 200
    assert file_into(editor, "clip", theirs.id, fid).status_code == 403  # not theirs
    assert file_into(owner, "clip", theirs.id, fid).status_code == 200  # the owner files anything
    shown = {j["id"]: j["folder_id"] for j in editor.get(f"/jobs?folder={fid}").json()}
    assert shown == {clip.id: fid}  # an editor's Quick clips are their own (Reed's item 4)
    every = {j["id"]: j["folder_id"] for j in owner.get(f"/jobs?folder={fid}").json()}
    assert every == {clip.id: fid, theirs.id: fid}

    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    assert file_into(editor, "video", pid, fid).status_code == 200
    shown = editor.get(f"/brands/{brand}/ideas?folder={fid}").json()["ideas"]
    assert [i["id"] for i in shown] == [pid]
    step = Job(workspace_id=me["workspace_id"], kind="image", provider="fake", input={},
               credits=0, project_id=pid, created_by_id=me["id"])  # fmt: skip
    db.add(step)
    db.commit()
    no = file_into(editor, "clip", step.id, fid)
    assert (no.status_code, no.json()["detail"]) == (409, folders.VIDEO_JOB)
    rows = editor.get(f"/brands/{brand}/folders").json()
    assert rows[0]["items"] == {"scripts": 0, "videos": 1, "clips": 2}
    other, _ = _published(owner, db, breakdown=BREAKDOWN)
    mine = owner.post(f"{other}/drafts/0/produce").json()["project_id"]
    assert file_into(owner, "video", mine, fid).status_code == 200
    counted = {"editor": editor, "owner": owner}  # every idea, as the folder shows (S1-08)
    assert {k: c.get(f"/brands/{brand}/folders").json()[0]["items"]["videos"]
            for k, c in counted.items()} == {"editor": 2, "owner": 2}  # fmt: skip


def test_the_tree_counts_at_any_depth_and_shows_each_folders_newest_dots(owner, editor, db):
    brand = first_brand(owner)
    me, ed = _ids(db)
    rants = _folder(owner, brand, "Dr. Pickle rants")
    hang = _folder(owner, brand, "Hangovers", rants)
    _folder(owner, brand, "Black Friday")
    for n in range(7):
        _idea(db, brand, me, f"Rant {n}", rants)
    _idea(db, brand, ed, "On hangovers", hang)
    _idea(db, brand, me, "First test video")
    _idea(db, brand, me, "Put away", rants, archived_at=utcnow())
    tree = editor.get(f"/brands/{brand}/tree").json()  # an editor sees everyone's (S1-08)
    assert [f["name"] for f in tree["folders"]] == ["Black Friday", "Dr. Pickle rants"]
    top = tree["folders"][1]
    assert (top["count"], top["more"], len(top["ideas"])) == (8, 2, 5)
    assert [i["title"] for i in top["ideas"]] == [f"Rant {n}" for n in (6, 5, 4, 3, 2)]
    assert top["ideas"][0]["status"] == {"kind": "needs_you", "words": "Needs you",
                                         "reason": ideas.START, "at": None, "made": 0,
                                         "total": 0}  # fmt: skip
    (inner,) = top["folders"]
    shown = (inner["name"], inner["count"], inner["ideas"][0]["title"])
    assert shown == ("Hangovers", 1, "On hangovers")
    assert not top["can_manage"]  # the owner's folder, read by an editor
    assert tree["unsorted"]["count"] == 1 and tree["unsorted"]["id"] is None
    assert owner.get("/brands/999/tree").status_code == 404


def test_each_status_in_words_first_thing_first(app, owner, editor, db):
    brand = first_brand(owner)
    me, ed = _ids(db)

    def status(pid, client=owner):
        found = client.get(f"/brands/{brand}/ideas?folder=none").json()["ideas"]
        return next(i["status"] for i in found if i["id"] == pid)

    held = _idea(db, brand, ed, "Why IPAs hit harder")
    _job(db, held, JobStatus.succeeded, credits=10)
    _job(db, held, JobStatus.needs_owner_approval, credits=6)
    assert status(held)["words"] == ideas.YOUR_OK
    assert status(held, editor)["words"] == "Waiting for the owner"

    broken = _idea(db, brand, me, "Night-time bloat")
    bd = BreakdownVersion(project_id=broken, data=BREAKDOWN, source="ai", script_version=1)
    db.add(bd)
    db.commit()
    clip = ProjectClip(project_id=broken, breakdown_id=bd.id, clip_id="c4", seconds=5, prompt="p")
    db.add(clip)
    db.commit()
    _job(db, broken, JobStatus.failed, project_clip_id=clip.id)
    assert (status(broken)["kind"], status(broken)["reason"]) == ("needs_fix", "Stopped at clip 4")

    working = _idea(db, brand, me, "Beer gut doctor rant")
    _job(db, working, JobStatus.running)
    s = status(working)
    assert (s["kind"], s["words"], s["reason"]) == ("working", "Working", None)

    done = _idea(db, brand, me, "3 signs", finished_at=utcnow())
    assert status(done)["kind"] == "delivered"
    fresh = _idea(db, brand, me, "New")
    assert status(fresh)["reason"] == ideas.START
    loose = owner.get(f"/brands/{brand}/ideas?folder=none").json()["ideas"]
    assert next(i["cost"] for i in loose if i["id"] == fresh) is None  # no script: no price yet

    # A run a person stopped says who; one that stopped on its own needs a fix
    run = {"director_run": {"id": "r1", "turn": 1}}
    stopped = _idea(db, brand, me, "Pint vs capsule")
    _job(db, stopped, JobStatus.cancelled, step=director.STEP, ended=director.STOPPED,
         stopped_by=me, stopped_at=utcnow().isoformat(), **run)  # fmt: skip
    s = status(stopped)
    assert (s["kind"], s["reason"]) == ("stopped", "by Reed") and s["at"]
    gave_up = _idea(db, brand, me, "Gave up")
    _job(db, gave_up, JobStatus.succeeded, step=director.STEP, ended="It stopped after 30 turns.",
         result="Stopped.", **run)  # fmt: skip
    s = status(gave_up)
    assert (s["kind"], s["reason"]) == ("needs_fix", "Stopped at the plan")


def test_stop_records_who_pressed_it(app, owner, editor, db):
    from tests.test_director import _made

    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    editor.post(f"/projects/{pid}/director/stop")
    found = editor.get(f"/brands/{first_brand(owner)}/ideas?folder=none").json()["ideas"]
    s = next(i["status"] for i in found if i["id"] == pid)
    editor_name = db.query(User).filter_by(role="editor").one().name
    assert (s["kind"], s["reason"]) == ("stopped", f"by {editor_name}") and s["at"]


def test_an_open_folder_tabs_search_made_by_sort_pages_and_archived(owner, editor, db):
    brand = first_brand(owner)
    me, ed = _ids(db)
    week = _folder(owner, brand, "Week of 3 Nov")
    inner = _folder(owner, brand, "Inside", week)
    made = []
    for n, (name, by) in enumerate([("Beer gut", me), ("Bloated", ed), ("IPAs", ed),
                                    ("Angry gut", me), ("Glow-up", me)]):  # fmt: skip
        pid = _idea(db, brand, by, name, inner if n == 4 else week)
        db.get(Project, pid).created_at = utcnow() - timedelta(days=5 - n)
        made.append(pid)
    db.get(Project, made[3]).finished_at = utcnow()
    db.commit()
    _job(db, made[0], JobStatus.running)
    gone = _idea(db, brand, me, "Old cure", week, archived_at=utcnow())
    url = f"/brands/{brand}/ideas?folder={week}"
    out = editor.get(url).json()
    assert out["counts"] == {"all": 5, "needs_you": 3, "working": 1, "delivered": 1}
    assert (out["total"], out["archived"], out["folders_inside"]) == (5, 1, 1)
    assert [m["name"] for m in out["makers"]] == sorted(
        [db.get(User, me).name, db.get(User, ed).name], key=str.lower
    )
    assert out["ideas"][0]["id"] == made[0]  # newest activity first
    card = out["ideas"][0]
    assert card["cost"]["kind"] == "up_to" and card["cost"]["usd"] is None  # editors: credits
    assert card["can_manage"] is False and card["made_by"]["id"] == me
    assert owner.get(url).json()["ideas"][0]["cost"]["usd"] is not None
    assert [i["title"] for i in editor.get(f"{url}&sort=name").json()["ideas"]] == [
        "Angry gut", "Beer gut", "Bloated", "Glow-up", "IPAs"]  # fmt: skip
    oldest = [i["id"] for i in editor.get(f"{url}&sort=oldest").json()["ideas"]]
    assert (oldest[0], oldest[-1]) == (made[1], made[0])  # least recent activity first
    page = editor.get(f"{url}&sort=name&offset=2&limit=2").json()
    assert (page["total"], [i["title"] for i in page["ideas"]]) == (5, ["Bloated", "Glow-up"])
    found = editor.get(f"{url}&q=gut&made_by={me}&tab=delivered").json()
    assert ([i["title"] for i in found["ideas"]], found["counts"]["all"]) == (["Angry gut"], 2)
    shelf = editor.get(f"{url}&archived=true").json()
    assert [(i["id"], i["status"]["kind"]) for i in shelf["ideas"]] == [(gone, "archived")]
    assert (shelf["counts"]["all"], shelf["archived"]) == (5, 1)  # the header keeps the folder's
    assert editor.get(f"/brands/{brand}/ideas?folder={inner}").json()["counts"]["all"] == 1

    other = owner.get("/brands").json()[1]["id"]  # Iron Paws
    assert owner.get(f"/brands/{other}/ideas?folder={week}").status_code == 404  # brands apart
    assert owner.get(f"/brands/{brand}/ideas?folder=nope").status_code == 404
    assert owner.get(f"/brands/{brand}/ideas?folder=²").status_code == 404
