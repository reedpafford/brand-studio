"""End on the logo (Reed, 2026-10-27): at the stitch, free, with ffmpeg and the brand's own
logo file, only when the last spoken line is the brand's end line."""

import io
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from app import end_logo
from app.models.brands import Brand
from app.models.projects import Project
from app.providers.fake_local import mp4
from tests.conftest import upload
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

LOGO = (Path(__file__).parents[2] / "assets/brands/fomo/logo.png").read_bytes()


def _length(video: bytes, tmp_path) -> float:
    path = tmp_path / "v.mp4"
    path.write_bytes(video)
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0"]
    return float(subprocess.run([*command, path], capture_output=True, check=True).stdout)  # noqa: S603


def _last_frame(video: bytes, tmp_path) -> Image.Image:
    (tmp_path / "v.mp4").write_bytes(video)
    args = ["ffmpeg", "-v", "error", "-sseof", "-0.2", "-i", "v.mp4", "-frames:v", "1", "-f",
            "image2", "-c:v", "png", "pipe:1"]  # fmt: skip
    done = subprocess.run(args, cwd=tmp_path, capture_output=True, check=True)  # noqa: S603
    return Image.open(io.BytesIO(done.stdout)).convert("RGB")


def _shows_logo(frame: Image.Image, share: float, centre_y: float) -> bool:
    """The logo, scaled as the stitch does, is what the frame shows at that spot."""
    w, h = frame.size
    size = end_logo._even(w * share)
    logo = Image.open(io.BytesIO(LOGO)).convert("RGB").resize((size, size))
    left, top = (w - size) // 2, round(h * centre_y - size / 2)
    seen = frame.crop((left, top, left + size, top + size))
    return max(ImageStat.Stat(ImageChops.difference(seen, logo)).mean) < 12


def test_each_mode_ends_on_the_logo_frame(tmp_path):
    clip_video = mp4("9:16", 2)  # a stand-in take: grey, 2 s
    over = end_logo.overlay(clip_video, LOGO, start=1.0, planned=2)
    assert abs(_length(over, tmp_path) - 2) < 0.1  # the clip keeps its length
    assert _shows_logo(_last_frame(over, tmp_path), end_logo.OVERLAY_WIDTH, end_logo.OVERLAY_Y)
    card = end_logo.card(clip_video, LOGO)
    assert abs(_length(card, tmp_path) - end_logo.CARD_SECONDS) < 0.1
    assert _shows_logo(_last_frame(card, tmp_path), end_logo.CARD_WIDTH, 0.5)
    assert end_logo.card(_mp4("red"), LOGO)  # clips with sound get a silent card that joins


def _brand(db, setup) -> Brand:  # noqa: F811
    return db.get(Brand, db.get(Project, setup["project"]).brand_id)


def test_the_end_line_is_the_call_to_action_only_when_the_last_line_says_it(db, setup, clip):  # noqa: F811
    from app.models.clips import ProjectClip

    project, rows = db.get(Project, setup["project"]), [db.get(ProjectClip, clip["id"])]
    brand = _brand(db, setup)
    brand.end_line = "I bought the dip."  # the test breakdown's last line (shot 1.2, after 2.5 s)
    assert end_logo.cta(db, project, rows) == (0, 2.5)
    brand.end_line = "Nate, where is all your money? I bought the dip."  # over the last two lines
    assert end_logo.cta(db, project, rows) == (0, 0)
    brand.end_line = "Download fomo through the link in my bio."
    assert end_logo.cta(db, project, rows) is None and end_logo.mode(db, project, rows) == "off"


def test_the_stitch_ends_on_the_logo_only_when_the_brand_says_so(
    app, db, owner, editor, setup, clip, tmp_path,  # noqa: F811
):  # fmt: skip
    base, url = f"/projects/{setup['project']}", f"/projects/{setup['project']}/clips/{clip['id']}"
    brand = _brand(db, setup)
    brand_url = f"/brands/{brand.id}"
    owner.patch(
        brand_url, json={"end_line": "I bought the dip.", "logo_file_id": upload(owner, data=LOGO)}
    )
    editor.post(f"{url}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    editor.post(f"{url}/approve")

    assert brand.end_logo == "end_card"  # fomo, from the seed
    assert editor.patch(brand_url, json={"end_logo": "overlay"}).status_code == 403  # owner only
    assert owner.patch(brand_url, json={"end_logo": "off"}).json()["end_logo"] == "off"
    plain = editor.post(f"{base}/video").json()
    data = editor.get(f"/files/{plain['file_id']}").content
    assert abs(_length(data, tmp_path) - 1) < 0.15  # off: just the take

    assert owner.patch(brand_url, json={"end_logo": "end_card"}).status_code == 200
    assert editor.get(f"{base}/video").json()["out_of_date"] is True  # the setting changed
    carded = editor.post(f"{base}/video").json()
    data = editor.get(f"/files/{carded['file_id']}").content
    assert abs(_length(data, tmp_path) - 1 - end_logo.CARD_SECONDS) < 0.15
    assert _shows_logo(_last_frame(data, tmp_path), end_logo.CARD_WIDTH, 0.5)
    assert editor.get(f"{base}/video").json()["out_of_date"] is False
    assert editor.patch(brand_url, json={"end_line": "I bought the dip!"}).status_code == 200
