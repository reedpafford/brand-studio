"""Next-Screens (v5 G boards): a library item's page says which videos use it, so nobody
changes or removes a character, place or prop without seeing what it's in."""

from sqlalchemy.orm.attributes import flag_modified

from app.db import utcnow
from app.models.clips import ProjectClip
from app.models.projects import Project
from tests.conftest import first_brand
from tests.test_clip_takes import clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


def test_an_item_lists_the_videos_that_use_it(app, db, owner, editor, setup, clip):  # noqa: F811
    pid = setup["project"]
    (mom,) = [c for c in editor.get("/library/character").json() if c["name"] == "Mom"]
    dip = [{"project_id": pid, "name": "Dip", "status": "making"}]
    assert editor.get(f"/library/character/{mom['id']}").json()["used_in"] == dip  # its cast
    assert owner.get(f"/library/character/{mom['id']}").json()["used_in"] == dip

    brand = first_brand(owner)
    place = editor.post("/library/place", json={"name": "Kitchen", "brand_ids": [brand]}).json()
    url = f"/library/place/{place['id']}"
    assert editor.get(url).json()["used_in"] == []  # in the brand, but no video shows it
    row = db.get(ProjectClip, clip["id"])
    row.references = [*row.references, {"kind": "image", "id": f"place:{place['id']}"}]
    flag_modified(row, "references")
    db.commit()
    assert editor.get(url).json()["used_in"] == dip  # pictured in a clip

    db.get(Project, pid).archived_at = utcnow()
    db.commit()
    assert editor.get(url).json()["used_in"] == []  # a deleted video isn't listed
    assert "used_in" in editor.get("/library/place").json()[0]  # the list carries it empty
