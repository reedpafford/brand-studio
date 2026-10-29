"""Per-look sheets (flows ST2): the owner adds a sheet in another look to a Cast & places
character (a new version; House kept); a video in that look uses it; with none, the editor
makes this video's own copy in the look, never saved to Cast & places (rule 12). House
videos are unchanged. All on the free stand-ins (no paid calls)."""

from app import storyboard
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from tests.test_breakdown import BREAKDOWN
from tests.test_script_produce import _published
from tests.test_song_takes import _work

LOOK = "disney-pixar"


def _video(app, owner, editor, db, look=LOOK):
    app.state.settings.fake_providers = True
    base, mia = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    db.get(Project, pid).look = look
    db.commit()
    return db.get(Project, pid), mia


def test_the_owner_adds_a_sheet_in_another_look_and_house_is_kept(app, db, owner, editor):
    _, mia = _video(app, owner, editor, db)
    url = f"/library/character/{mia}/sheet"
    house = db.get(LibraryItem, mia).sheet_file_id
    no = editor.post(url, json={"look_id": LOOK})
    assert no.status_code == 403  # only the owner adds a look to Cast & places
    made = owner.post(url, json={"look_id": LOOK})
    assert made.status_code == 201, made.text
    job = db.get(Job, made.json()["id"])
    assert (
        job.input["sheet_look_id"] == LOOK and job.input["files"]
    )  # the House sheet as the person
    _work(app, db)
    item = owner.get(f"/library/character/{mia}").json()
    assert item["look_sheets"][LOOK]["status"] == "needs_approval"
    assert item["sheet_file_id"] == house and item["sheet_status"] == "approved"  # House kept
    ok = owner.post(f"{url}/approve?look_id={LOOK}").json()
    assert ok["look_sheets"][LOOK]["status"] == "approved" and ok["version"] > item["version"] - 1
    assert owner.delete(f"{url}/approve?look_id={LOOK}").json()["look_sheets"][LOOK]["status"] == (
        "needs_approval"
    )  # Undo


def test_a_video_in_another_look_uses_the_looks_sheet_or_makes_its_own(app, db, owner, editor):
    project, mia = _video(app, owner, editor, db)
    assert storyboard.assets(db, project)[f"char:{mia}"][1] == []  # its sheet is House only
    rows = editor.get(f"/projects/{project.id}/assets").json()
    (row,) = [r for r in rows if r["library_item_id"] == mia]
    assert row["look_needed"] == "Disney Pixar" and not row["ready"] and row["look_credits"]

    made = editor.post(f"/projects/{project.id}/assets/looks/{mia}/copy")
    assert made.status_code == 200, made.text
    db.refresh(project)
    copy = db.get(LibraryItem, project.look_copies[str(mia)])
    assert copy.owner_project_id == project.id and copy.sheet_look == LOOK  # this video only
    again = editor.post(f"/projects/{project.id}/assets/looks/{mia}/copy")
    assert again.status_code == 409
    _work(app, db)
    editor.post(f"/library/character/{copy.id}/sheet/approve")
    db.expire_all()
    assert storyboard.assets(db, project)[f"char:{mia}"][1] == [copy.sheet_file_id]
    assert db.get(LibraryItem, mia).look_sheets == {}  # Cast & places untouched
    listed = [i["id"] for i in editor.get("/library/character").json()]
    assert mia in listed and copy.id not in listed


def test_a_house_video_is_unchanged(app, db, owner, editor):
    project, mia = _video(app, owner, editor, db, look="house")
    house = db.get(LibraryItem, mia).sheet_file_id
    assert storyboard.assets(db, project)[f"char:{mia}"][1] == [house]
    no = editor.post(f"/projects/{project.id}/assets/looks/{mia}/copy")
    assert no.status_code == 409


def test_a_cast_character_with_only_a_house_sheet_is_lookless_in_another_look():
    """Flow-QA: Mia has only a House sheet and the video is Pixar, so `known` (sheet_for) has
    no picture of her and marks it; she's named, and nothing is drawn without her. One with
    no sheet at all (Bo) is left to require_sheet's "Approve Bo's sheet first"."""
    from app.sheets import NO_LOOK, lookless

    known = {"char:5": (f"char:5 | character | Mia | plays Mom | {NO_LOOK}", []),
             "char:6": ("char:6 | character | Bo", []),
             "char:7": ("char:7 | character | Ann", [9])}  # fmt: skip
    assert lookless([["char:5", "char:6"], ["char:7"], ["char:5"]], known) == ["Mia"]
