"""Approve cast & places (Reed, 4 Nov, on S-gaps-07): every character and place a video shows
is approved together, once, by the person making it; a still or take that shows something
new or changed waits for it, in the code that makes them; unrelated work carries on."""

import copy
from unittest.mock import ANY

from sqlalchemy.orm.attributes import flag_modified

from app import cast_gate
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.routes import cast
from app.worker import start_next
from tests.conftest import upload
from tests.helpers import approve_cast, with_sheet
from tests.test_video_looks import _video


def _newest(db, pid) -> BreakdownVersion:
    return db.query(BreakdownVersion).filter_by(project_id=pid).order_by(
        BreakdownVersion.id.desc()).first()  # fmt: skip


def _two_clips(db, pid, place: int | None = None) -> None:
    """Shot 1.1 (clip 1) shows no one, at `place`; shot 1.2 (clip 2) shows Nate."""
    row = _newest(db, pid)
    data = copy.deepcopy(row.data)
    data["scenes"][0]["shots"][0].update(character_ids=[], speaker=None, line=None,
                                         place_id=f"place:{place}" if place else None)  # fmt: skip
    data["clips"] = [{"id": "c1", "shot_ids": ["1.1"], "seconds": 4, "seam": "Cut."},
                     {"id": "c2", "shot_ids": ["1.2"], "seconds": 4, "seam": "End."}]  # fmt: skip
    row.data = data
    flag_modified(row, "data")
    db.commit()


def _frame(db, pid, shot: str, refs: list[str]) -> int:
    clip = "c1" if shot == "1.1" else "c2"
    frame = StoryboardFrame(project_id=pid, breakdown_id=_newest(db, pid).id, clip_id=clip,
                            shot_id=shot, prompt=f"Shot {shot}.", reference_ids=refs)  # fmt: skip
    db.add(frame)
    db.commit()
    return frame.id


def _drawn(db, client, item_id) -> None:
    """Its sheet job finished: a look made for the video is usable at once (save_sheet)."""
    sheet = upload(client)  # first: the test's session holds no write while the app writes
    for job in db.query(Job).all():
        if job.input.get("library_item_id") == item_id:
            job.status = JobStatus.succeeded
    item = db.get(LibraryItem, item_id)
    item.sheet_file_id, item.sheet_approved = sheet, True
    db.commit()


def _nate(editor, db, pid, slot) -> int:
    editor.post(f"/projects/{pid}/assets/slots/{slot}/make-look")
    look = next(r for r in editor.get(f"/projects/{pid}/assets").json()
                if r["slot_id"] == slot)["library_item_id"]  # fmt: skip
    return look


def _render(client, pid, frame):
    return client.post(f"/projects/{pid}/storyboard/frames/{frame}/render")


def test_an_editor_on_a_published_script_approves_their_own_cast_and_places(owner, editor, db):
    _, pid, slot = _video(owner, editor, db)
    url = f"/projects/{pid}/cast"
    shown = editor.get(url).json()
    assert shown["state"] == "not_ready" and shown["not_ready"][0]["why"] == "Nate needs a look"
    look = _nate(editor, db, pid, slot)
    _two_clips(db, pid)
    shown = editor.get(url).json()
    (nate,) = shown["items"]
    assert (nate["readiness"], nate["source"], nate["approval"]) == ("drawing", "video", "new")
    seen = {nate["ref"]: nate["sig"]}
    no = editor.post(f"{url}/approve", json={"seen": seen})
    assert (no.status_code, no.json()["detail"]) == (
        409, "Nate is still being drawn first, then approve the cast and places.")  # fmt: skip

    _drawn(db, editor, look)
    shown = editor.get(url).json()
    assert shown["state"] == "ready" and shown["waiting"] == ["Nate"]
    assert shown["paused_clips"] == ["c2"] and shown["items"][0]["preview_file_id"]
    near, far = _frame(db, pid, "1.2", [f"char:{look}"]), _frame(db, pid, "1.1", [])
    held = _render(editor, pid, near)
    said = "Nate waits for the cast and places OK. Approve them in Cast to go on."
    assert (held.status_code, held.json()["detail"]) == (409, said)
    assert _render(editor, pid, far).status_code == 201  # unrelated work carries on

    stale = editor.post(f"{url}/approve", json={"seen": seen})  # the sig before it was drawn
    assert stale.status_code == 409 and "Look at it again" in stale.json()["detail"]
    done = approve_cast(editor, pid)  # no owner OK: it's the editor's creative call
    assert (done["state"], done["approved_by"], done["waiting"]) == ("approved", "Ed", [])
    made = _render(editor, pid, near)
    assert made.status_code == 201, made.text
    stamp = db.get(Job, made.json()["id"]).input["made_with"]["cast"]
    assert stamp == {f"char:{look}": done["items"][0]["sig"]}
    assert editor.post(f"{url}/approve", json={"seen": {}}).json()["detail"] == cast_gate.NOTHING


def test_a_change_needs_the_ok_again_unchanged_items_stay_approved(owner, editor, db):
    _, pid, slot = _video(owner, editor, db)
    brand = db.get(Project, pid).brand_id
    kitchen = editor.post("/library/place", json={
        "name": "Kitchen", "image_file_ids": [upload(editor)], "brand_ids": [brand]})  # fmt: skip
    kitchen = kitchen.json()["id"]
    with_sheet(db, kitchen)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid, kitchen)
    items = {i["name"]: i for i in approve_cast(editor, pid)["items"]}
    assert items["Kitchen"]["source"] == "library" and items["Nate"]["source"] == "video"
    near = _frame(db, pid, "1.2", [f"char:{look}"])
    job = db.get(Job, _render(editor, pid, near).json()["id"])
    frame = db.get(StoryboardFrame, near)
    frame.file_id, frame.made_with = upload(editor), job.input["made_with"]  # it was drawn
    job.status = JobStatus.succeeded
    db.commit()

    db.get(LibraryItem, look).sheet_file_id = upload(editor)  # Change this… drew a new Nate
    db.commit()
    shown = editor.get(f"/projects/{pid}/cast").json()
    states = {i["name"]: i["approval"] for i in shown["items"]}
    assert states == {"Kitchen": "approved", "Nate": "changed"} and shown["state"] == "ready"
    assert shown["update"]["stills"] == ["1.2"] and shown["update"]["credits"] >= 1  # priced
    assert db.get(StoryboardFrame, near).file_id == frame.file_id  # kept, never redrawn alone
    assert _render(editor, pid, near).status_code == 409  # Nate's shot waits
    kept = editor.post(f"/projects/{pid}/cast/keep", json={"stills": ["1.2"]}).json()["update"]
    assert (kept["stills"], kept["credits"]) == ([], 0)  # Keep them: no longer to update
    assert [(k["kind"], k["id"], k["by"]) for k in kept["kept_items"]] == [("still", "1.2", "Ed")]
    far = _frame(db, pid, "1.1", [f"place:{kitchen}"])
    assert _render(editor, pid, far).status_code == 201  # the kitchen stayed approved
    assert (
        owner.post(
            f"/projects/{pid}/cast/approve",
            json={"seen": {i["ref"]: i["sig"] for i in shown["items"]}},
        ).status_code
        == 200
    )  # the owner may too
    assert _render(editor, pid, near).status_code == 201


def test_a_queued_still_never_runs_on_a_look_changed_since(app, owner, editor, db):
    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    approve_cast(editor, pid)
    job = db.get(Job, _render(editor, pid, _frame(db, pid, "1.2", [f"char:{look}"])).json()["id"])
    assert cast_gate.job_paused(db, job) is False
    db.get(LibraryItem, look).sheet_file_id = upload(editor)
    db.commit()
    assert cast_gate.job_paused(db, job) is True
    for other in db.query(Job).filter(Job.id != job.id, Job.status == JobStatus.queued):
        other.status = JobStatus.succeeded
    db.commit()
    assert start_next(db, {}, app.state.storage)
    db.refresh(job)
    assert (job.status, job.error) == (JobStatus.cancelled, cast_gate.PAUSED)  # uncharged


def test_places_for_this_video_only_pick_upload_or_make(owner, editor, db):
    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    url = f"/projects/{pid}/cast"
    body = {"shot_ids": ["1.1"], "name": "The penthouse", "description": "Glass walls, night."}
    added = editor.post(f"{url}/places", json=body)
    assert added.status_code == 201, added.text
    place = next(i for i in added.json()["items"] if i["kind"] == "place")
    assert (place["name"], place["readiness"], place["source"]) == (
        "The penthouse", "needs_look", "video")  # fmt: skip
    item = db.get(LibraryItem, place["library_item_id"])
    assert item.owner_project_id == pid and item.brands == []  # never the brand's
    assert item.id not in [p["id"] for p in owner.get("/library/place").json()]
    shot = _newest(db, pid).data["scenes"][0]["shots"][0]
    assert shot["place_id"] == f"place:{item.id}"  # the plan's shot happens there
    row = next(r for r in editor.get(f"/projects/{pid}/assets").json() if r["kind"] == "place")
    assert row["only_here"] == "video" and row["look_credits"] >= 1  # Make a look · up to
    assert editor.get(url).json()["state"] == "not_ready"
    assert "The penthouse" in editor.get(f"/projects/{pid}/assets/missing-looks").json()["roles"]

    photo = upload(editor)
    up = editor.post(f"{url}/places/{item.id}/upload", json={"file_id": photo})
    db.refresh(item)
    assert up.status_code == 200 and item.source_photo_file_id == photo
    assert next(i for i in up.json()["items"] if i["kind"] == "place")["source"] == "uploaded"
    made = editor.post(f"{url}/places/{item.id}/make-look")
    assert made.status_code == 200, made.text
    sheet = next(j for j in db.query(Job).all() if j.input.get("library_item_id") == item.id)
    assert sheet.project_id == pid  # paid from this video's budget
    assert next(i for i in made.json()["items"] if i["kind"] == "place")["readiness"] == "drawing"

    roof = owner.post(
        "/library/place",
        json={
            "name": "Roof",
            "image_file_ids": [upload(owner)],
            "brand_ids": [db.get(Project, pid).brand_id],
        },
    )
    roof = roof.json()["id"]
    with_sheet(db, roof)
    picked = editor.put(f"{url}/places/{item.id}", json={"library_item_id": roof})
    assert picked.status_code == 200, picked.text
    place = next(i for i in picked.json()["items"] if i["kind"] == "place")
    assert (place["name"], place["source"]) == ("Roof", "library")
    assert editor.post(f"{url}/places", json={"shot_ids": ["9.9"], "name": "X"}).status_code == 422


def test_the_director_asks_for_the_ok_waits_on_that_point_and_goes_on(app, owner, editor, db):
    from app import director_tools

    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    project = db.get(Project, pid)
    assert director_tools.run(db, editor_user(db), project, {"tool": "ask_cast_ok"}, None, {
        "id": "r1"}).startswith("Refused: Nate is still being drawn")  # fmt: skip
    _drawn(db, editor, look)
    _two_clips(db, pid)
    said = director_tools.run(db, editor_user(db), project, {"tool": "ask_cast_ok"}, None,
                              {"id": "r1"})  # fmt: skip
    assert said == "Asked for the cast and places OK: Nate."
    assert editor.get(f"/projects/{pid}/cast").json()["asked"] is True
    _frame(db, pid, "1.2", [f"char:{look}"])
    _frame(db, pid, "1.1", [])
    said = director_tools.run(db, editor_user(db), project, {"tool": "stills"}, None, {})
    assert said == "Drawing the stills. 1 still waits for the cast and places OK."
    approve_cast(editor, pid)
    assert editor.get(f"/projects/{pid}/cast").json()["asked"] is False  # answered


def editor_user(db):
    from app.models.accounts import User

    return db.query(User).filter_by(email="ed@example.com").one()


def test_a_video_with_no_shots_yet_has_nothing_to_approve(owner, editor, db):
    _, pid, _ = _video(owner, editor, db)
    for row in db.query(BreakdownVersion).filter_by(project_id=pid):
        db.delete(row)
    db.commit()
    shown = editor.get(f"/projects/{pid}/cast").json()
    assert (shown["state"], shown["items"]) == ("none", [])
    added = editor.post(f"/projects/{pid}/cast/places", json={"shot_ids": ["1.1"], "name": "X"})
    assert added.json()["detail"] == cast.NO_PLAN and "after Make it" in cast.NO_PLAN


def test_only_the_person_making_the_video_or_the_owner_approves(app, owner, editor, db):
    from fastapi.testclient import TestClient

    from tests.conftest import PASSWORD

    _, pid, slot = _video(owner, editor, db)
    _drawn(db, editor, _nate(editor, db, pid, slot))
    shown = editor.get(f"/projects/{pid}/cast").json()
    seen = {i["ref"]: i["sig"] for i in shown["items"]}
    token = owner.post("/team/invites", json={"email": "kel@example.com"}).json()["token"]
    with TestClient(app) as kel:
        kel.post("/auth/accept-invite", json={"token": token, "name": "Kel", "password": PASSWORD})
        assert kel.get(f"/projects/{pid}/cast").json()["state"] == "ready"  # may look
        assert kel.post(f"/projects/{pid}/cast/approve", json={"seen": seen}).status_code == 403
    assert editor.post(f"/projects/{pid}/cast/approve", json={"seen": seen}).status_code == 200


def test_each_look_says_who_made_it_its_last_change_and_what_previews_cost(owner, editor, db):
    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    first, second = upload(editor), upload(editor)
    (made,) = [j for j in db.query(Job).all() if j.input.get("step") == "sheet"]
    made.status, made.output = JobStatus.succeeded, {"file_ids": [first]}
    item = db.get(LibraryItem, look)
    item.sheet_file_id, item.sheet_approved = first, True
    db.commit()
    asked = editor.post(f"/library/character/{look}/sheet", json={"change": "Make him older."})
    assert asked.status_code == 201, asked.text
    again = db.get(Job, asked.json()["id"])
    again.status, again.output = JobStatus.succeeded, {"file_ids": [second]}
    db.commit()
    (nate,) = editor.get(f"/projects/{pid}/cast").json()["items"]
    assert (nate["made_by"], nate["revised_by"], nate["revised_why"]) == (
        "Ed", "Ed", "Make him older.")  # fmt: skip
    assert nate["was_preview_file_id"] == first and nate["made_at"] <= nate["revised_at"]
    shown = editor.get(f"/projects/{pid}/cast").json()["previews"]
    assert shown["credits"] > 0 and shown["usd"] is None and shown["budget_usd"] is None
    assert owner.get(f"/projects/{pid}/cast").json()["previews"]["usd"] > 0  # owner: dollars


def test_a_director_send_with_no_brand_is_refused(owner, editor):
    body = {"type": "dialogue", "look": "house", "shape": "9:16", "text": "MOM: Hi."}
    no = editor.post("/freestyles", json=body)
    assert (no.status_code, no.json()["detail"]) == (
        422, "Pick a brand first: every video is made inside a brand.")  # fmt: skip
    clip = {**body, "type": "one_clip", "text": "A cat at dawn."}
    assert editor.post("/freestyles", json=clip).status_code == 201  # One clip: no cast


def test_what_a_still_attaches_beyond_its_shot_waits_too(owner, editor, db):
    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    approve_cast(editor, pid)
    roof = owner.post(
        "/library/place",
        json={
            "name": "Roof",
            "image_file_ids": [upload(owner)],
            "brand_ids": [db.get(Project, pid).brand_id],
        },
    )
    roof = roof.json()["id"]
    with_sheet(db, roof)
    frame = _frame(db, pid, "1.1", [f"place:{roof}"])  # shot 1.1 names no place
    held = _render(editor, pid, frame)
    assert held.status_code == 409 and held.json()["detail"].startswith("Roof waits")
    shown = editor.get(f"/projects/{pid}/cast").json()
    assert "Roof" in shown["waiting"] and shown["state"] == "ready"
    approve_cast(editor, pid)
    assert _render(editor, pid, frame).status_code == 201


def test_a_voice_change_needs_the_ok_again_and_says_so(owner, editor, db):
    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    approve_cast(editor, pid)
    near = _frame(db, pid, "1.2", [f"char:{look}"])
    db.get(LibraryItem, look).voice_stock_key = "Roger"
    db.commit()
    (nate,) = editor.get(f"/projects/{pid}/cast").json()["items"]
    assert (nate["approval"], nate["changes"]) == ("changed", ["voice"])
    assert nate["voice"]["name"] == "Roger" and nate["was_voice"] is None  # had none before
    assert nate["voice"]["sample_url"] == "/voices/samples/Roger.mp3"
    assert _render(editor, pid, near).status_code == 409
    approve_cast(editor, pid)
    (nate,) = editor.get(f"/projects/{pid}/cast").json()["items"]
    assert (nate["approval"], nate["changes"]) == ("approved", [])
    db.get(LibraryItem, look).voice_stock_key = "Austin"
    db.commit()
    (nate,) = editor.get(f"/projects/{pid}/cast").json()["items"]
    assert (nate["voice"]["name"], nate["was_voice"]["name"]) == ("Austin", "Roger")


def test_the_director_asks_again_after_a_revision(owner, editor, db):
    from app import director_tools

    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    project, run = db.get(Project, pid), {"id": "r1"}
    ask = {"tool": "ask_cast_ok"}
    assert director_tools.run(db, editor_user(db), project, ask, None, run).startswith("Asked")
    assert director_tools.run(db, editor_user(db), project, ask, None, run).startswith("Refused")
    db.get(LibraryItem, look).sheet_file_id = upload(editor)  # revised after a note
    db.commit()
    assert editor.get(f"/projects/{pid}/cast").json()["asked"] is False
    assert director_tools.run(db, editor_user(db), project, ask, None, run).startswith("Asked")


def test_a_host_piece_made_again_waits_for_the_ok(owner, editor, db, monkeypatch):
    from fastapi import HTTPException

    from app import host

    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    project = db.get(Project, pid)
    monkeypatch.setattr(host, "host_look", lambda db, p: db.get(LibraryItem, look))
    monkeypatch.setattr(host, "on", lambda db, p: True)  # a presenter video: the host is cast
    try:
        host._cast(db, project, check=True)
        raise AssertionError("not held")
    except HTTPException as no:
        assert no.status_code == 409 and "Nate waits" in no.detail
    approve_cast(editor, pid)
    db.refresh(project)  # as approved, read again
    assert host._cast(db, project, check=True) == {f"char:{look}": ANY}


def test_a_place_swap_sends_its_clips_back_to_be_written_again(owner, editor, db):
    from app.models.clips import ProjectClip

    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    url = f"/projects/{pid}/cast"
    first = editor.post(f"{url}/places", json={"shot_ids": ["1.1"], "name": "Hall"}).json()
    hall = next(i for i in first["items"] if i["kind"] == "place")["library_item_id"]
    bd = _newest(db, pid)
    clip = ProjectClip(project_id=pid, breakdown_id=bd.id, clip_id="c1", seconds=4,
                       prompt="Shot 1.1 in the Hall.", references=[
                           {"id": f"place:{hall}", "kind": "image"}])  # fmt: skip
    db.add(clip)
    db.commit()
    roof = owner.post(
        "/library/place",
        json={
            "name": "Roof",
            "image_file_ids": [upload(owner)],
            "brand_ids": [db.get(Project, pid).brand_id],
        },
    )
    editor.put(f"{url}/places/{hall}", json={"library_item_id": roof.json()["id"]})
    db.refresh(clip)
    assert clip.breakdown_id != _newest(db, pid).id  # stale: its prompt is written again


def test_qa_fixes_hold_only_what_waits(owner, editor, db):
    """QA on #1331: the same place picked again changes nothing; Keep them with stills only
    keeps no clip; a price read works while the cast waits; Update after draws the stills
    that don't wait; a director change_look on a place no shot is at spends nothing."""
    from app import director_tools, update_after

    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    roof = owner.post(
        "/library/place",
        json={
            "name": "Roof",
            "image_file_ids": [upload(owner)],
            "brand_ids": [db.get(Project, pid).brand_id],
        },
    )
    roof = roof.json()["id"]
    with_sheet(db, roof)
    url = f"/projects/{pid}/cast"
    editor.post(f"{url}/places", json={"shot_ids": ["1.1"], "library_item_id": roof})
    versions, jobs = db.query(BreakdownVersion).count(), db.query(Job).count()
    assert editor.put(f"{url}/places/{roof}", json={"library_item_id": roof}).status_code == 200
    assert (db.query(BreakdownVersion).count(), db.query(Job).count()) == (versions, jobs)

    approve_cast(editor, pid)
    near, far = _frame(db, pid, "1.2", [f"char:{look}"]), _frame(db, pid, "1.1", [f"place:{roof}"])
    db.get(LibraryItem, look).sheet_file_id = upload(editor)  # Nate changed: waits again
    db.commit()
    price = editor.get(f"/projects/{pid}/storyboard/frames/{near}/change")
    assert price.status_code == 200 and price.json()["credits"] >= 1  # the price still shows
    frames = [db.get(StoryboardFrame, near), db.get(StoryboardFrame, far)]
    update_after._draw(db, editor_user(db), db.get(Project, pid), frames, {})
    drawn = {j.input.get("frame_id") for j in db.query(Job).all()}
    assert far in drawn and near not in drawn  # the roof's still went; Nate's waits

    jobs = db.query(Job).count()
    move = {"tool": "change_look", "look": {"name": "Nate"}, "note": "Older."}
    db.get(Project, pid).locks = {}
    db.commit()
    lone = owner.post(
        "/library/place",
        json={
            "name": "Attic",
            "image_file_ids": [upload(owner)],
            "brand_ids": [db.get(Project, pid).brand_id],
        },
    )
    with_sheet(db, lone.json()["id"])
    _frame(db, pid, "1.2", [f"char:{look}", f"place:{lone.json()['id']}"])  # attached only
    said = director_tools.run(db, editor_user(db), db.get(Project, pid),
                              {**move, "look": {"name": "Attic"}}, None, {})  # fmt: skip
    assert said == "Refused: no shot in the plan is at Attic." and db.query(Job).count() == jobs


def test_a_narration_in_a_changed_host_voice_waits_for_the_ok(owner, editor, db, monkeypatch):
    import pytest

    from app import host

    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    monkeypatch.setattr(host, "host_look", lambda db, p: db.get(LibraryItem, look))
    monkeypatch.setattr(host, "on", lambda db, p: True)
    project = db.get(Project, pid)
    cast_gate.require_voice(db, project)  # never approved: not held (the cast comes later)
    approve_cast(editor, pid)
    db.refresh(project)
    cast_gate.require_voice(db, project)  # approved as it is
    db.get(LibraryItem, look).voice_stock_key = "Roger"
    db.commit()
    with pytest.raises(cast_gate.Waiting, match="Nate's new voice waits"):
        cast_gate.require_voice(db, project)


def test_ask_answers_for_looks_and_places_land_in_cast(owner, editor, db):
    """QA on #1331: a generated option picked on a cast card is this video's look, ready for
    the OK; a place card's answer moves the shots at that place."""
    from app import asks
    from app.models.asks import Ask

    _, pid, slot = _video(owner, editor, db)
    project = db.get(Project, pid)
    _two_clips(db, pid)
    pic = upload(editor)
    ask = Ask(workspace_id=project.workspace_id, project_id=pid, kind="cast", subject="Nate",
              question="Who plays Nate?", state="answered",
              answer={"how": "option", "option": 0, "file_id": pic})  # fmt: skip
    db.add(ask)
    db.commit()
    asks._effect(db, editor_user(db), project, ask)
    db.commit()
    from app.routes.sheets import save_fit

    (check,) = [j for j in db.query(Job).all() if j.input.get("step") == "look_fit"]
    check.status, check.output = (
        JobStatus.succeeded,
        {"fits": True, "seen": "teen boy", "problem": "", "anchors": "dark hair"},
    )
    save_fit(db, check)  # its words read off it, as off any drawn sheet (video 294)
    db.commit()
    shown = editor.get(f"/projects/{pid}/cast").json()
    assert shown["state"] == "ready" and shown["items"][0]["readiness"] == "ready"

    url = f"/projects/{pid}/cast"
    editor.post(f"{url}/places", json={"shot_ids": ["1.1"], "name": "Hall"})
    roof = owner.post(
        "/library/place",
        json={"name": "Roof", "image_file_ids": [upload(owner)], "brand_ids": [project.brand_id]},
    ).json()["id"]
    place = Ask(workspace_id=project.workspace_id, project_id=pid, kind="place", subject="Hall",
                question="Where's the hall?", state="answered",
                answer={"how": "saved", "option": f"item:{roof}"})  # fmt: skip
    db.add(place)
    db.commit()
    asks._effect(db, editor_user(db), db.get(Project, pid), place)
    db.commit()
    assert _newest(db, pid).data["scenes"][0]["shots"][0]["place_id"] == f"place:{roof}"


def test_a_narration_in_another_voice_is_not_held(owner, editor, db, monkeypatch):
    from app import host

    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    monkeypatch.setattr(host, "host_look", lambda db, p: db.get(LibraryItem, look))
    monkeypatch.setattr(host, "on", lambda db, p: True)
    approve_cast(editor, pid)
    db.get(LibraryItem, look).voice_stock_key = "Roger"
    db.commit()
    project = db.get(Project, pid)
    db.refresh(project)
    cast_gate.require_voice(db, project, "Austin")  # read in another voice: not held


def test_a_place_card_for_a_place_no_shot_is_at_yet_keeps_its_photo(owner, editor, db):
    from app import director_tools
    from app.routes import cast
    from tests.helpers import mp4

    _, pid, slot = _video(owner, editor, db)
    _two_clips(db, pid)
    project = db.get(Project, pid)
    photo = upload(editor)
    clip = upload(editor, name="a.mp4", data=mp4(1), content_type="video/mp4")
    cast.answer_place(
        db, editor_user(db), project, "The penthouse", {"how": "upload", "file_id": clip}
    )  # a clip: never a place's photo
    assert db.query(LibraryItem).filter_by(name="The penthouse").count() == 0
    cast.answer_place(
        db, editor_user(db), project, "The penthouse", {"how": "upload", "file_id": photo}
    )
    db.commit()
    made = db.query(LibraryItem).filter_by(name="The penthouse").one()
    assert made.owner_project_id == pid and made.source_photo_file_id == photo
    said = director_tools.run(db, editor_user(db), project, {
        "tool": "add_place", "look": {"name": "The penthouse", "shot_ids": ["1.1"]}},
        None, {})  # fmt: skip  # by name: the place the card's answer kept
    assert said.startswith("Added The penthouse for shots 1.1"), said
    assert _newest(db, pid).data["scenes"][0]["shots"][0]["place_id"] == f"place:{made.id}"


def test_only_whoever_made_the_video_or_the_owner_is_offered_the_press(app, owner, editor, db):
    _, pid, _ = _video(owner, editor, db)
    assert editor.get(f"/projects/{pid}/cast").json()["can_approve"] is True
    assert owner.get(f"/projects/{pid}/cast").json()["can_approve"] is True


def test_a_watch_remake_of_a_changed_look_says_it_waits_for_the_ok(owner, editor, db, monkeypatch):
    from fastapi import HTTPException

    no = cast_gate.Waiting(409, cast_gate.WAIT.format("Nate", "waits"))
    assert cast_gate.not_yet(no) == ("Not remade yet: Nate waits for the cast and places OK. "
                                     "Approve them in Cast, then remake it.")  # fmt: skip
    assert isinstance(no, HTTPException)


def test_a_stills_price_with_its_clips_take_shows_while_the_cast_waits(owner, editor, db):
    """QA on #1329: Change the still… on a clip with a take is a new still and a new take
    (S-gaps-08 2); its price reads both while the cast and places wait for the OK, as a price
    read needs no OK (`check` passed through to the take)."""
    from decimal import Decimal

    from app import change, credits
    from app.models.clips import ClipTake, ProjectClip

    _, pid, slot = _video(owner, editor, db)
    look = _nate(editor, db, pid, slot)
    _drawn(db, editor, look)
    _two_clips(db, pid)
    approve_cast(editor, pid)
    frame = db.get(StoryboardFrame, _frame(db, pid, "1.2", [f"char:{look}"]))
    alone = change.credits(db, db.get(Project, pid), frame)  # no take yet: the still only
    made, sheet = upload(editor), upload(editor)  # first: the app writes these
    clip = ProjectClip(project_id=pid, breakdown_id=frame.breakdown_id, clip_id="c2", seconds=4,
                       prompt="Nate looks up.")  # fmt: skip
    project = db.get(Project, pid)
    job = Job(workspace_id=project.workspace_id, kind="video", provider="fake", input={},
              project_id=pid, credits=5, status="succeeded")  # fmt: skip
    db.add_all([clip, job])
    db.flush()
    db.add(ClipTake(clip_id=clip.id, number=1, job_id=job.id, file_id=made))
    db.get(LibraryItem, look).sheet_file_id = sheet  # Nate changed: waits again
    db.commit()
    url = f"/projects/{pid}/storyboard/frames/{frame.id}/change"
    price = editor.get(url)
    assert price.status_code == 200, price.text  # the price still shows
    project, frame = db.get(Project, pid), db.get(StoryboardFrame, frame.id)
    both = change.credits(db, project, frame)
    assert both > alone > Decimal(0)  # the still, then its clip's new take
    assert price.json()["credits"] == credits.price(both)  # the press says both, as it charges
