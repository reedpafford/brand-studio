"""A shot that shows the brand's product lists the real product picture, so its still and its
clip attach it (Reed, Iron Paws #32 c9: an invented "Iron Paws" bag on a shelf). Free, in
code, said as advice; the video's flavour unless the shot names another."""

import copy

from app.models.brands import Brand, BrandScreen
from app.models.projects import Project
from app.prompts import check
from tests.conftest import upload
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture

BAGS = [
    {"id": "screen:7", "name": "Peanut butter bag", "product": "bag", "variant": "Peanut butter"},
    {"id": "screen:8", "name": "Chicken bag", "product": "bag", "variant": "Chicken"},
]


def test_the_words_of_a_shot_find_the_product_it_shows():
    def shown(text):
        return check.product_shown(text, "Iron Paws", BAGS)

    assert shown("An Iron Paws bag sits on the shelf behind her.") == "screen:7"  # the flavour
    assert shown("She scoops from the chicken bag.") == "screen:8"  # the one named
    assert shown("Close on the Peanut butter bag, label to camera.") == "screen:7"
    assert shown("Two Iron Paws bags on the counter.") == "screen:7"
    assert shown("A bag of groceries on the counter.") is None  # not the brand's
    assert shown("Iron Paws the dog sleeps.") is None
    assert check.product_shown("An Iron Paws bag.", "Iron Paws", []) is None  # no product


def test_a_breakdown_shot_showing_the_bag_gets_the_real_one(app, db, editor, owner, setup):  # noqa: F811
    files = [upload(owner), upload(owner)]  # before the session writes (one SQLite writer)
    project = db.get(Project, setup["project"])
    brand = db.get(Brand, project.brand_id)
    brand.name = "Iron Paws"
    ids = {}
    pairs = (("Chicken bag", "Chicken"), ("Peanut butter bag", "Peanut butter"))
    for (name, variant), file_id in zip(pairs, files, strict=True):
        screen = BrandScreen(brand_id=brand.id, name=name, file_id=file_id,
                             tags=["product"], product="bag", variant=variant)  # fmt: skip
        db.add(screen)
        db.flush()
        ids[variant] = f"screen:{screen.id}"
    project.product_variants = {"bag": "Peanut butter"}
    db.commit()
    data = copy.deepcopy(BREAKDOWN)
    shots = data["scenes"][0]["shots"]
    shots[0]["action"] = "Mom glares; an Iron Paws bag sits on the shelf behind her."
    shots[1]["action"] = "Nate holds up the chicken bag."
    editor.post(f"/projects/{project.id}/breakdown")
    _run(app, db, FakeClaude(data))
    got = editor.get(f"/projects/{project.id}/breakdown").json()
    saved = got["breakdown"]["scenes"][0]["shots"]
    assert ids["Peanut butter"] in saved[0]["screen_ids"]  # the video's flavour
    assert ids["Chicken"] in saved[1]["screen_ids"]  # the one the shot names
    assert "Advice: Shot 1.1 now shows the real Peanut butter bag." in got["problems"]


def test_the_bag_never_makes_a_fourth_screen_in_a_clip(app, db, editor, owner, setup):  # noqa: F811
    """QA: "N screens; keep the 3" blocks with no one-click fix, so the repair stays out."""
    from app.breakdown import product_shots
    from app.prompts.schemas import Breakdown

    files = [upload(owner)]
    project = db.get(Project, setup["project"])
    brand = db.get(Brand, project.brand_id)
    brand.name = "Iron Paws"
    db.add(BrandScreen(brand_id=brand.id, name="Peanut butter bag", file_id=files[0],
                       tags=["product"], product="bag", variant="Peanut butter"))  # fmt: skip
    db.commit()
    data = copy.deepcopy(BREAKDOWN)
    shots = data["scenes"][0]["shots"]
    shots[0]["screen_ids"] = ["screen:901", "screen:902", "screen:903"]  # already 3
    shots[1]["action"] = "An Iron Paws bag sits on the counter."
    bd, notes = product_shots(db, project, Breakdown.model_validate(data))
    assert bd.scenes[0].shots[1].screen_ids == [] and notes == []
