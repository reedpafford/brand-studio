"""v5 Media (C_Media, Builder-V5-C): tabs by group with their counts, each clip's and song's
length, newest or oldest first, and a picture or clip added to a brand's Media. Free."""

import struct
import subprocess

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


def _long(seconds: int) -> bytes:
    """A real MP4 of `seconds` (tiny: 32 px, 2 frames a second, no sound)."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "long.mp4"
        args = (f"-v error -f lavfi -i color=c=red:s=32x32:r=2:d={seconds} -c:v libx264 "
                "-pix_fmt yuv420p").split()  # fmt: skip
        subprocess.run(["ffmpeg", *args, str(path)], check=True)  # noqa: S603, S607
        return path.read_bytes()


def _lying(data: bytes, seconds: int) -> bytes:
    """The same MP4 with only its mvhd, tkhd and mdhd durations rewritten (QA-13's attack)."""
    out, scale = bytearray(data), {}

    def walk(start, end):
        i = start
        while i + 8 <= end:
            size, kind = struct.unpack(">I4s", out[i : i + 8])
            if size < 8:
                return
            body = i + 8
            if kind in (b"moov", b"trak", b"mdia"):
                walk(body, i + size)
            elif kind in (b"mvhd", b"mdhd") and out[body] == 0:
                scale[kind] = struct.unpack(">I", out[body + 12 : body + 16])[0]
                out[body + 16 : body + 20] = struct.pack(">I", scale[kind] * seconds)
            elif kind == b"tkhd" and out[body] == 0:
                out[body + 20 : body + 24] = struct.pack(">I", scale[b"mvhd"] * seconds)
            i += size

    walk(0, len(out))
    return bytes(out)


def test_a_clip_whose_header_lies_about_its_length_is_measured_by_its_packets(owner):
    """QA-13: a 185 s clip with its durations patched to 10 s got past the 3-minute cap."""
    from app.routes import media
    from app.routes.media import _probe

    lie = _lying(_long(185), 10)
    assert _probe(lie)[1] >= 184  # the header says 10
    refused = _add(owner, first_brand(owner), "short.mp4", lie)
    assert (refused.status_code, refused.json()["detail"]) == (422, media.TOO_LONG)
    honest = _add(owner, first_brand(owner), "ok.mp4", _lying(_long(20), 5)).json()
    assert 19 <= honest["duration_seconds"] <= 21  # its packets, not its header


def test_a_picture_cut_off_part_way_is_refused(owner):
    assert _add(owner, first_brand(owner), "cut.png", PNG[: len(PNG) // 2]).status_code == 415


def test_a_final_cuts_length_is_kept_once(app, db, owner, monkeypatch):
    from app.routes import media

    brand = first_brand(owner)
    project = Project(workspace_id=1, brand_id=brand, name="Dip", created_by_id=1)
    db.add(project)
    db.commit()
    stored = owner.post("/files", files={"upload": ("f.mp4", _mp4("red"), "video/mp4")}).json()
    final = FinalVideo(project_id=project.id, file_id=stored["id"], take_ids=[], created_by_id=1)
    db.add(final)
    db.commit()
    reads = []
    real = media._probe
    monkeypatch.setattr(media, "_probe", lambda data: reads.append(1) or real(data))
    for _ in range(2):
        (item,) = owner.get(f"/brands/{brand}/media", params={"kind": "final"}).json()["items"]
        assert 0.9 <= item["duration_seconds"] <= 1.1
    assert len(reads) == 1  # read once, then kept on the final
    db.expire_all()
    assert db.get(FinalVideo, final.id).seconds == item["duration_seconds"]


def _dense(seconds: int, rate: int) -> bytes:
    """A legal clip of tiny frames: `rate` packets a second (QA-13's dense clip)."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dense.mp4"
        args = (f"-v error -f lavfi -i color=c=red:s=16x16:r={rate} -t {seconds} -c:v libx264 "
                "-preset ultrafast -pix_fmt yuv420p -g 100000").split()  # fmt: skip
        subprocess.run(["ffmpeg", *args, str(path)], check=True)  # noqa: S603, S607
        return path.read_bytes()


def test_a_dense_clip_is_read_as_a_stream_and_stops_once_past_the_cap(owner, monkeypatch):
    """QA-13: every packet held as JSON took gigabytes; now only the latest end is kept, and
    a clip past the cap stops being read as soon as a packet ends after it."""
    import subprocess as sp

    from app.routes import media

    lines = []
    real = sp.Popen

    class Counting(real):  # counts the packet lines the probe reads
        def __init__(self, args, *a, **k):
            super().__init__(args, *a, **k)
            if any("packet=" in str(x) for x in args):  # the packet read only
                self.stdout = (lines.append(line) or line for line in self.stdout)

    monkeypatch.setattr(sp, "Popen", Counting)
    clip = _lying(_dense(190, 200), 10)  # 38,000 packets, 36,000 to the cap; the header: 10 s
    refused = _add(owner, first_brand(owner), "dense.mp4", clip)
    assert (refused.status_code, refused.json()["detail"]) == (422, media.TOO_LONG)
    assert 36_000 <= len(lines) < 37_000  # stopped just past 180 s, never read to the end
    lines.clear()
    kept = _add(owner, first_brand(owner), "dense.mp4", _dense(20, 200))
    assert kept.status_code == 201 and 19.5 <= kept.json()["duration_seconds"] <= 20.5


def test_a_clip_too_slow_to_check_is_refused_plainly(owner, monkeypatch):
    from app.routes import media

    monkeypatch.setattr(media, "PROBE_SECONDS", 0)  # any check runs out of time
    slow = _add(owner, first_brand(owner), "a.mp4", _mp4("red"))
    assert (slow.status_code, slow.json()["detail"]) == (422, media.SLOW)


def test_a_final_whose_file_cant_be_read_is_tried_once(db, owner, monkeypatch):
    """QA-13: an unreadable final was read again on every Media load."""
    from app.routes import media

    brand = first_brand(owner)
    project = Project(workspace_id=1, brand_id=brand, name="Dip", created_by_id=1)
    db.add(project)
    db.commit()
    final = FinalVideo(project_id=project.id, file_id=_file(db, 1, "video/mp4"), take_ids=[],
                       created_by_id=1)  # its file isn't in storage  # fmt: skip
    db.add(final)
    db.commit()
    reads = []
    monkeypatch.setattr(media, "_probe", lambda data, **k: reads.append(1))
    for _ in range(2):
        (item,) = owner.get(f"/brands/{brand}/media", params={"kind": "final"}).json()["items"]
        assert item["duration_seconds"] is None
    db.expire_all()
    assert db.get(FinalVideo, final.id).seconds == media.UNREAD and reads == []  # gone: no read
