"""Next-Screens (v5 G boards): one Media item's own page, read as the list shows it, and only
what the caller may see."""

from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.routes import media
from tests.conftest import first_brand
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_media import _file, _media


def _quick(db, brand, user) -> Job:
    job = Job(workspace_id=user.workspace_id, kind="video", provider="fake", input={}, credits=0,
              brand_id=brand, status=JobStatus.succeeded, created_by_id=user.id,
              output={"file_ids": [_file(db, user.workspace_id, "video/mp4")]})  # fmt: skip
    db.add(job)
    db.commit()
    return job


def test_one_media_item_reads_as_the_list_shows_it(db, owner, editor):
    brand = first_brand(owner)
    ed = db.query(User).filter_by(email="ed@example.com").one()
    job = _quick(db, brand, ed)
    key = f"quick:{job.id}:0"
    (listed,) = [i for i in _media(editor, brand)["items"] if i["key"] == key]
    assert editor.get(f"/brands/{brand}/media/{key}").json() == listed
    assert owner.get(f"/brands/{brand}/media/{key}").json()["made_by"]["name"] == ed.name
    gone = editor.get(f"/brands/{brand}/media/take:999")
    assert (gone.status_code, gone.json()["detail"]) == (404, media.NOT_FOUND)
    mine = _quick(db, brand, db.query(User).filter_by(email="reed@example.com").one())
    hidden = editor.get(f"/brands/{brand}/media/quick:{mine.id}:0")  # the owner's own quick clip
    assert hidden.status_code == 404


def test_the_owner_removes_a_quick_clip_and_a_videos_part_is_refused(
    db,
    owner,
    editor,
    setup,  # noqa: F811
):
    from app.models.brands import Brand
    from app.models.clips import FinalVideo
    from app.models.library import LibraryItem
    from app.models.projects import Project

    project = db.get(Project, setup["project"])
    brand = project.brand_id
    ed = db.query(User).filter_by(email="ed@example.com").one()
    url = f"/brands/{brand}/media/quick:{_quick(db, brand, ed).id}:0"
    assert editor.delete(url).status_code == 403  # the owner only
    assert owner.delete(url).status_code == 204
    assert owner.get(url).status_code == 404  # off Media…
    job_id = url.rsplit(":", 2)[1]
    assert owner.post(f"/jobs/{job_id}/restore").status_code == 200  # …and Undo brings it back
    assert owner.get(url).status_code == 200

    final = FinalVideo(project_id=project.id, file_id=_file(db, ed.workspace_id, "video/mp4"),
                       take_ids=[], created_by_id=ed.id)  # fmt: skip
    db.add(final)
    db.commit()
    part = owner.delete(f"/brands/{brand}/media/final:{final.id}")
    assert part.status_code == 409
    assert part.json()["detail"] == "This is part of Dip. Remove it from the video instead."
    mom = LibraryItem(workspace_id=ed.workspace_id, kind="character", name="Mom",
                      sheet_file_id=_file(db, ed.workspace_id))  # fmt: skip
    mom.brands = [db.get(Brand, brand)]
    db.add(mom)
    db.commit()
    sheet = owner.delete(f"/brands/{brand}/media/sheet:{mom.id}:0")
    assert (sheet.status_code, sheet.json()["detail"]) == (409, media.SHEET)
