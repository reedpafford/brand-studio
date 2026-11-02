"""v5 G boards and My credits (Next-Screens, Next-Lead): a Media item says whether the director
made it and, for a sheet, whose sheet; My credits shows the director's own time apart and,
for a freestyle's video, what the owner's OKs cover."""

from app.models.projects import Project
from tests.conftest import first_brand
from tests.test_director import _made, _run
from tests.test_freestyle_dialogue import BODY
from tests.test_freestyle_dialogue import _run as _run_fakes


def test_what_a_director_run_made_says_so_and_a_sheet_names_its_character(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    brand = db.get(Project, pid).brand_id
    from app.models.brands import Brand
    from app.models.library import LibraryItem

    for item in db.query(LibraryItem).filter(LibraryItem.sheet_file_id.is_not(None)):
        item.brands = [db.get(Brand, brand)]  # in the brand's Cast & places
    db.commit()
    items = owner.get(f"/brands/{brand}/media").json()["items"]
    takes = [i for i in items if i["kind"] == "take" and i["project_id"] == pid]
    assert takes and all(i["source"] == "director" for i in takes)
    sheets = [i for i in items if i["kind"] == "sheet"]
    assert sheets and all(i["library_item_id"] and i["library_kind"] for i in sheets)
    assert all(i["library_item_id"] is None for i in takes)


def test_my_credits_shows_the_directors_time_and_what_the_ok_covers(app, db, owner, editor):
    brand = first_brand(owner)
    fs = owner.post("/freestyles", json={**BODY, "brand_id": brand}).json()
    _run_fakes(app, db)
    (video,) = [v for v in owner.get("/usage/mine", params={"brand_id": brand}).json()["videos"]
                if v["project_id"] == fs["project_id"]]  # fmt: skip
    assert 0 < video["director_credits"] <= video["credits"]
    shown = owner.get(f"/freestyles/{fs['id']}").json()
    assert video["approved_up_to"] == shown["up_to"]  # one send, its price
