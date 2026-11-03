"""v5 Media (C_Media, Builder-V5-C): tabs by group with their counts, each clip's and song's
length, newest or oldest first, and a picture or clip added to a brand's Media. Free."""

from app.models.clips import FinalVideo
from app.models.files import MediaUpload
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.conftest import PNG, first_brand
from tests.test_clip_takes import _mp4
from tests.test_media import _file


def _add(client, brand, name, data, content_type="application/octet-stream"):
    return client.post(f"/brands/{brand}/media", files={"upload": (name, data, content_type)})


def test_a_picture_and_a_clip_are_added_to_a_brands_media_by_their_contents(owner, editor, db):
    brand = first_brand(owner)
    picture = _add(editor, brand, "logo.bin", PNG)  # its name and label don't decide its type
    assert picture.status_code == 201, picture.text
    item = picture.json()
    assert (item["kind"], item["group"], item["content_type"]) == ("upload", "still", "image/png")
    assert item["duration_seconds"] is None and item["made_by"]["name"] == "Ed"
    clip = _add(owner, brand, "clip.png", _mp4("red"), "image/png").json()
    assert (clip["group"], clip["content_type"]) == ("clip", "video/mp4")
    assert 0.9 <= clip["duration_seconds"] <= 1.1
    keys = {i["key"] for i in owner.get(f"/brands/{brand}/media").json()["items"]}
    assert {item["key"], clip["key"]} <= keys  # everyone with the brand sees them
    assert item["key"] in {i["key"] for i in editor.get(f"/brands/{brand}/media").json()["items"]}

    fake = _add(editor, brand, "photo.png", b"<svg onload=alert(1)>", "image/png")
    assert fake.status_code == 415  # not a picture, whatever it's called
    no_picture = _add(editor, brand, "x.mp4", b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    assert no_picture.status_code == 415  # an MP4 header with no video in it
    assert db.query(MediaUpload).count() == 2

    assert owner.delete(f"/brands/{brand}/media/{item['key']}").status_code == 204
    assert item["key"] not in {
        i["key"] for i in owner.get(f"/brands/{brand}/media").json()["items"]
    }


def test_an_upload_too_big_is_refused(app, owner):
    app.state.settings.max_upload_mb = 0  # anything is too big
    assert _add(owner, first_brand(owner), "a.png", PNG).status_code == 413


def test_tabs_counts_lengths_and_order(app, db, owner):
    brand = first_brand(owner)
    project = Project(workspace_id=1, brand_id=brand, name="Dip", created_by_id=1)
    db.add(project)
    db.commit()
    quick = Job(workspace_id=1, kind="video", provider="fake", credits=0, brand_id=brand,
                input={"input": {"duration": 5}}, status=JobStatus.succeeded,
                output={"file_ids": [_file(db, 1, "video/mp4")]}, created_by_id=1)  # fmt: skip
    db.add(quick)
    db.add(FinalVideo(project_id=project.id, file_id=_file(db, 1, "video/mp4"), take_ids=[],
                      created_by_id=1))  # fmt: skip
    db.commit()
    _add(owner, brand, "a.png", PNG)
    counts = owner.get(f"/brands/{brand}/media-counts").json()
    assert counts == {"all": counts["all"], "clips": 2, "stills": 1, "songs": 0}
    assert counts["all"] == 3
    clips = owner.get(f"/brands/{brand}/media", params={"group": "clip"}).json()["items"]
    assert {i["kind"] for i in clips} == {"take", "final"}
    (take,) = [i for i in clips if i["kind"] == "take"]
    assert take["duration_seconds"] == 5.0  # as the take was asked for
    (final,) = [i for i in clips if i["kind"] == "final"]
    assert final["duration_seconds"] is None  # its file can't be read: no length, no error
    newest = [i["key"] for i in owner.get(f"/brands/{brand}/media").json()["items"]]
    oldest = [i["key"] for i in owner.get(f"/brands/{brand}/media",
                                          params={"sort": "oldest"}).json()["items"]]  # fmt: skip
    assert oldest == newest[::-1]


def test_oldest_first_pages_walk_the_list_once(db, owner, monkeypatch):
    from app.routes import media

    monkeypatch.setattr(media, "PAGE", 2)
    brand = first_brand(owner)
    for _ in range(5):
        _add(owner, brand, "a.png", PNG)
    seen, after = [], None
    while True:
        params = {"sort": "oldest", **({"before": after} if after else {})}
        page = owner.get(f"/brands/{brand}/media", params=params).json()
        seen += [i["key"] for i in page["items"]]
        if not (after := page["next"]):
            break
    every = [i["key"] for i in owner.get(f"/brands/{brand}/media", params={"sort": "oldest"})
             .json()["items"]]  # fmt: skip
    assert len(seen) == len(set(seen)) == 5
    assert seen[:2] == every[:2]
