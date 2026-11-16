"""Per-look sheets (flows ST2): the owner adds a sheet in another look to a Cast & places
character (a new version; House kept); a video in that look uses it; with none, the editor
makes this video's own copy in the look, never saved to Cast & places (rule 12). House
videos are unchanged. A picture is drawn in, and used in, the style of the video it is for,
places too, and never in House because nothing was said (Reed, 15 Nov). All on the free
stand-ins (no paid calls)."""

from app import cast_gate, guides, storyboard
from app.models.jobs import Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from tests.conftest import upload
from tests.helpers import with_sheet
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


def test_a_looks_first_sheet_is_listed_as_drawing_until_it_is_back(app, db, owner, editor):
    """Flow-QA on #944: after a reload, a look whose first sheet is still being drawn reads
    drawing (not missing), so "Make a {look} sheet" isn't offered again."""
    _, mia = _video(app, owner, editor, db)
    assert owner.post(f"/library/character/{mia}/sheet", json={"look_id": LOOK}).status_code == 201
    item = owner.get(f"/library/character/{mia}").json()
    assert item["look_sheets"] == {LOOK: {"file_id": None, "status": "drawing"}}
    assert item["sheet_status"] == "approved"  # House unchanged
    _work(app, db)
    assert owner.get(f"/library/character/{mia}").json()["look_sheets"][LOOK]["status"] == (
        "needs_approval")  # fmt: skip


def test_a_real_looking_person_in_words_is_seedreams_and_one_from_a_photo_stays(
    app, db, owner, editor
):
    """Reed, 12 Nov: Seedance takes a real-looking face only on a sheet Seedream drew from
    words. So a Movie or UGC sheet of someone described is Seedream's, from the words alone
    (never their House drawing), wide; from an uploaded photo it is Nano Banana's as before,
    and so is every House sheet."""
    from tests.conftest import upload

    project, mia = _video(app, owner, editor, db, look="movie")
    url = f"/library/character/{mia}/sheet"

    def drawn(job_id: int) -> tuple:
        job = db.get(Job, job_id)
        return job.input["model"], bool(job.input["files"]), job.input["input"]["aspect_ratio"]

    db.get(LibraryItem, mia).notes = "A woman in her 40s in a long oatmeal cardigan."
    db.commit()
    assert drawn(owner.post(url, json={"look_id": "ugc"}).json()["id"]) == (
        "seedream-5.5", False, "16:9")  # fmt: skip
    made = editor.post(f"/projects/{project.id}/assets/looks/{mia}/copy")  # this video's own
    assert made.status_code == 200, made.text
    db.refresh(project)
    copy = db.get(LibraryItem, project.look_copies[str(mia)])
    (job,) = db.query(Job).filter(Job.input["library_item_id"].as_integer() == copy.id)
    assert drawn(job.id) == ("seedream-5.5", False, "16:9")
    assert drawn(owner.post(url, json={"look_id": "house"}).json()["id"])[0] == "nano-banana-pro"
    db.get(LibraryItem, mia).source_photo_file_id = upload(editor)
    db.commit()
    assert drawn(owner.post(url, json={"look_id": "movie"}).json()["id"]) == (
        "nano-banana-pro", True, "9:16")  # fmt: skip


def _words(db, asked) -> str:
    assert asked.status_code == 201, asked.text
    return db.get(Job, asked.json()["id"]).input["input"]["prompt"]


def test_a_cast_and_places_sheet_names_its_style_and_a_videos_own_takes_the_videos(
    app, db, owner, editor
):
    """Reed, 15 Nov: ten place pictures asked with no style, for a Movie ad made by hand, came
    back in the animated House look. Cast & places has no video to take a style from, so the
    request names it and nothing is drawn until it does; a look made for a video through the
    library is drawn in that video's style."""
    from app.routes.sheets import NO_STYLE

    project, _ = _video(app, owner, editor, db, look="movie")
    movie, house = (guides.tokens(s)["place_look"].strip() for s in ("movie", "house"))
    said = {"name": "Mall", "notes": "A real photograph of a big, crowded, festive mall."}
    url = f"/library/place/{owner.post('/library/place', json=said).json()['id']}/sheet"
    for model in ("nano-banana-2.1", "seedream-5.5"):  # a place has style words on both
        unsaid = owner.post(url, json={"model_id": model})
        assert (unsaid.status_code, unsaid.json()["detail"]) == (422, NO_STYLE)
    assert db.query(Job).count() == 0  # nothing drawn, nothing charged
    drawn = _words(db, owner.post(url, json={"look_id": "movie"}))
    assert movie in drawn and house not in drawn
    assert house in _words(db, owner.post(url, json={"look_id": "house"}))  # House when asked

    own = owner.post("/library/place", json={**said, "owner_project_id": project.id}).json()["id"]
    assert db.get(LibraryItem, own).sheet_look == "movie"
    drawn = _words(db, owner.post(f"/library/place/{own}/sheet", json={}))
    assert movie in drawn and house not in drawn


def test_a_video_uses_a_place_only_in_its_own_style(app, db, owner, editor):
    """A brand place with only a House picture is never sent into a Movie video: the video
    gets its own copy drawn in its style, as it does of a brand character, and the brand's
    stays as it is. A House video, and the owner's approved Movie picture, use theirs as
    before; after the video's style changes, its own place gets a copy in the new one."""
    from app.models.accounts import User
    from app.routes.project_assets import make_missing
    from tests.test_cast_gate import _two_clips

    project, _ = _video(app, owner, editor, db, look="house")
    pid, movie = project.id, guides.tokens("movie")["place_look"].strip()
    roof = owner.post("/library/place", json={
        "name": "Roof", "notes": "A flat roof at dusk.", "image_file_ids": [upload(owner)],
        "brand_ids": [project.brand_id]}).json()["id"]  # fmt: skip
    failed = owner.post(f"/library/place/{roof}/sheet", json={"look_id": "house"}).json()["id"]
    db.get(Job, failed).status = JobStatus.failed  # a House sheet that once didn't draw
    with_sheet(db, roof)
    _two_clips(db, pid, roof)
    house, key = db.get(LibraryItem, roof).sheet_file_id, f"place:{roof}"

    def used() -> list[int]:
        db.expire_all()
        return storyboard.assets(db, project)[key][1]

    def missing() -> list[str]:
        return editor.get(f"/projects/{pid}/assets/missing-looks").json()["roles"]

    assert used() == [house] and "Roof" not in missing()  # House with House

    project.look = "movie"
    db.commit()
    assert used() == []  # never its House picture
    assert cast_gate.redrawable(db, project, cast_gate.current(db, project)) == []  # nor again
    db.get(LibraryItem, roof).look_sheets = {"movie": {"file_id": house, "approved": True}}
    db.commit()
    assert used() == [house] and "Roof" not in missing()  # the owner's Movie picture of it
    db.get(LibraryItem, roof).look_sheets = {}
    db.commit()
    assert "Roof" in missing()
    make_missing(db, db.get(User, project.created_by_id), project)  # as make_looks does
    db.refresh(project)
    copy = db.get(LibraryItem, project.look_copies[str(roof)])
    assert (copy.kind, copy.owner_project_id, copy.sheet_look) == ("place", pid, "movie")
    (job,) = [j for j in db.query(Job) if j.input.get("library_item_id") == copy.id]
    assert movie in job.input["input"]["prompt"] and not job.input["files"]  # from its words
    assert "Roof" not in missing()  # being drawn: never asked for twice
    _work(app, db)
    brand = db.get(LibraryItem, roof)
    assert used() == [copy.sheet_file_id] != [house]
    assert (brand.sheet_file_id, brand.sheet_approved, brand.look_sheets) == (house, True, {})

    project.look = "house"  # a person changed the video's style: the brand's own again
    db.commit()
    assert used() == [house] and "Roof" not in missing()

    den = {"name": "Den", "notes": "A small den.", "owner_project_id": pid}
    den = db.get(LibraryItem, owner.post("/library/place", json=den).json()["id"])
    den.sheet_file_id, den.sheet_approved = house, True  # this video's own, drawn in House
    _two_clips(db, pid, den.id)
    key = f"place:{den.id}"
    assert used() == [house]
    project.look = "claymation"
    db.commit()
    assert used() == [] and "Den" in missing()  # its own place from before the change
    made = editor.post(f"/projects/{pid}/cast/places/{den.id}/make-look")  # or make_looks
    db.refresh(project)
    again = db.get(LibraryItem, project.look_copies[str(den.id)])
    assert made.status_code == 200 and again.sheet_look == "claymation" and "Den" not in missing()
