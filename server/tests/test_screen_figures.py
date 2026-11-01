"""A shot's figure written on its real brand screen (Reed, 30 Oct). Free: PIL, no paid call."""

import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.cut_in import inserts
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.screen_figures import draw, shot_figure
from tests.conftest import png, upload
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_cut_in import approved  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

DARK = (6, 5, 15)
SPOT = {"box": [0, 10, 120, 110], "at": [6, 12], "size": 24, "chart": [0, 60, 120, 105]}
FOMO = Path(__file__).parents[2] / "assets" / "brands" / "fomo" / "screens"


def _colours(data: bytes) -> set:
    return set(Image.open(io.BytesIO(data)).convert("RGB").get_flattened_data())


def _green(c) -> bool:
    return c[1] > 150 and c[0] < 140 and c[2] < 140


def _red(c) -> bool:
    return c[0] > 200 and c[1] < 120 and c[2] < 120


def test_the_figure_is_written_on_the_screen_and_a_loss_is_red():
    screen = png(120, 240, DARK)
    gain = draw(screen, {"spot": SPOT, "balance": "$9,800", "change": "+$1,222"})
    assert any(c[:3] == (255, 255, 255) for c in _colours(gain))  # the balance, white
    assert any(_green(c) for c in _colours(gain)) and not any(_red(c) for c in _colours(gain))
    loss = draw(screen, {"spot": SPOT, "balance": "$880", "change": "-$380"})
    assert any(_red(c) for c in _colours(loss)) and not any(_green(c) for c in _colours(loss))
    assert draw(screen, {"spot": SPOT, "balance": "$880", "change": "-$380"}) == loss  # same line
    assert draw(screen, None) == screen  # no figure: the picture as it is


def test_only_the_shots_first_real_screen_with_a_spot_and_a_figure_is_drawn_on():
    screen = SimpleNamespace(id=7, product="", figure_spot=SPOT)
    shot = {"screen_ids": ["screen:7"], "screen_figure": {"balance": "$12,900", "change": None}}
    assert shot_figure(screen, shot) == {"spot": SPOT, "balance": "$12,900", "change": ""}
    assert shot_figure(screen, {**shot, "screen_ids": ["screen:3", "screen:7"]}) is None
    assert shot_figure(screen, {"screen_ids": ["screen:7"]}) is None  # no figure in the beat
    assert shot_figure(screen, {**shot, "screen_figure": {"balance": None}}) is None
    assert shot_figure(SimpleNamespace(id=7, product="", figure_spot=None), shot) is None
    assert shot_figure(SimpleNamespace(id=7, product="bag", figure_spot=SPOT), shot) is None


def test_fomos_spots_sit_inside_their_pictures():
    manifest = json.loads((FOMO / "screens.json").read_text())
    spots = {name: m["figure_spot"] for name, m in manifest.items() if m.get("figure_spot")}
    assert len(spots) == 3
    for name, spot in spots.items():
        width, height = Image.open(FOMO / name).size
        for x0, y0, x1, y1 in [spot["box"], spot.get("chart") or spot["box"]]:
            assert 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height, name


def test_a_spot_is_set_with_patch_and_checked(owner, editor, setup):  # noqa: F811
    fomo = owner.get("/brands").json()[0]["id"]
    url = f"/brands/{fomo}/screens/{setup['screen']}"
    assert editor.get(f"/brands/{fomo}/screens").json()[0]["figure_spot"] is None
    assert editor.patch(url, json={"figure_spot": {**SPOT, "box": [0, 1]}}).status_code == 422
    assert editor.patch(url, json={"figure_spot": SPOT}).json()["figure_spot"] == SPOT


def _with_figure(db, editor, clip_id: int, shot_id: str, screen: int, figure: dict) -> None:
    """The screen gets a dark picture and a spot; the shot shows it first, with `figure`."""
    fomo = editor.get("/brands").json()[0]["id"]
    picture = upload(editor, data=png(120, 240, DARK))
    editor.patch(f"/brands/{fomo}/screens/{screen}",
                 json={"file_id": picture, "figure_spot": SPOT})  # fmt: skip
    row = db.get(BreakdownVersion, db.get(ProjectClip, clip_id).breakdown_id)
    data = json.loads(json.dumps(row.data))
    shot = next(s for sc in data["scenes"] for s in sc["shots"] if s["id"] == shot_id)
    shot["screen_ids"], shot["screen_figure"] = [f"screen:{screen}"], figure
    row.data = data
    db.commit()


def test_a_take_sends_the_screen_with_its_shots_figure(app, db, editor, setup, clip):  # noqa: F811
    figure = {"balance": "$9,800", "change": "-$380"}
    _with_figure(db, editor, clip["id"], "1.1", setup["screen"], figure)
    editor.post(f"/projects/{setup['project']}/clips/{clip['id']}/generate")
    job = db.query(Job).filter(Job.input["step"].as_string() == "clip_take").one()
    (drawn,) = job.input["screen_figures"].values()
    assert (drawn["balance"], drawn["change"]) == ("$9,800", "-$380")
    fake = FakeSeedance([_mp4("red")])
    _work(app, db, fake)
    sent = json.loads(next(q for q in fake.requests if q.method == "POST").content)["input"]
    pictures = [base64.b64decode(u.split(",", 1)[1]) for u in sent["reference_images"]]
    assert any(any(_red(c) for c in _colours(p)) for p in pictures)  # the loss, written in


def test_a_cut_in_carries_its_shots_figure(db, editor, setup, approved):  # noqa: F811
    base, made = approved
    _with_figure(
        db, editor, made["id"], "1.2", setup["screen"], {"balance": "$46,500", "change": None}
    )
    project = db.get(Project, setup["project"])
    (insert,) = inserts(db, project, db.get(ProjectClip, made["id"]))
    assert insert.figure["balance"] == "$46,500"
    editor.put(f"{base}/clips/{made['id']}/inserts/1.2", json={"use_real_image": True})
    assert editor.post(f"{base}/video").status_code == 201
