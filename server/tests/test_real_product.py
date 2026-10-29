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


def _bags(db, owner, setup):  # noqa: F811
    """Iron Paws with its two bags; the video's flavour is peanut butter."""
    files = [upload(owner), upload(owner)]
    project = db.get(Project, setup["project"])
    brand = db.get(Brand, project.brand_id)
    brand.name = "Iron Paws"
    ids = {}
    for name, variant, file_id in (("Chicken bag", "Chicken", files[0]),
                                   ("Peanut butter bag", "Peanut butter", files[1])):  # fmt: skip
        screen = BrandScreen(brand_id=brand.id, name=name, file_id=file_id,
                             tags=["product"], product="bag", variant=variant)  # fmt: skip
        db.add(screen)
        db.flush()
        ids[variant] = f"screen:{screen.id}"
    project.product_variants = {"bag": "Peanut butter"}
    db.commit()
    return project, ids


def _c9():
    """#32 c9's shape: a breakdown made before the repair, its shot not listing the bag."""
    from app.prompts.schemas import Breakdown

    data = copy.deepcopy(BREAKDOWN)
    data["scenes"][0]["shots"][0]["action"] = "Mom glares; an Iron Paws bag sits on the shelf."
    return Breakdown.model_validate(data)


def test_a_breakdown_shot_showing_the_bag_gets_the_real_one(app, db, editor, owner, setup):  # noqa: F811
    project, ids = _bags(db, owner, setup)
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


def test_an_old_shot_showing_the_bag_attaches_the_real_one(db, owner, setup):  # noqa: F811
    from app.clip_prompts import with_cast as clip_cast
    from app.prompts.schemas import ClipPrompt, Frame, Reference
    from app.storyboard import with_cast as still_cast

    project, ids = _bags(db, owner, setup)
    bd = _c9()
    frame = still_cast(db, project, Frame(clip_id="c1", shot_id="1.1", prompt="Mom glares.",
                                          reference_ids=[]), bd)  # fmt: skip
    assert frame.reference_ids == [ids["Peanut butter"]]  # the video's flavour, never invented
    assert "Show the real Peanut butter bag from image 1 as it is." in frame.prompt
    again = still_cast(db, project, frame, bd)
    assert again == frame  # free; doing it again changes nothing

    prompt = "Audio: x.\nReferences: none.\nShot 1 | 0-5 s. Mom glares.\nAudio: x."
    clip = clip_cast(db, project, ClipPrompt(clip_id="c1", seconds=5, prompt=prompt,
                                             references=[]), bd)  # fmt: skip
    assert [r.id for r in clip.references] == [ids["Peanut butter"]]
    assert "[Image1] is the real Peanut butter bag; show it exactly as it is." in clip.prompt
    refs = [Reference(kind="image", id=ids["Chicken"], role="Chicken bag")]
    named = clip_cast(db, project, ClipPrompt(clip_id="c1", seconds=5, prompt=prompt,
                                              references=refs), bd)  # fmt: skip
    assert [r.id for r in named.references] == [ids["Chicken"]]  # a product attached: kept


def test_a_full_clip_makes_room_and_a_note_attaches_the_bag(db, owner, setup, monkeypatch):  # noqa: F811
    import app.clip_prompts as clip_prompts
    from app.models.library import Kind, LibraryItem
    from app.prompts.schemas import ClipPrompt, Reference

    project, ids = _bags(db, owner, setup)
    place = LibraryItem(workspace_id=project.workspace_id, kind=Kind.place, name="Kitchen",
                        image_file_ids=[upload(owner)])  # fmt: skip
    place.brands = [db.get(Brand, project.brand_id)]
    db.add(place)
    db.commit()
    full = clip_prompts.video_model().model_copy(update={"max_reference_images": 1})
    monkeypatch.setattr(clip_prompts, "video_model", lambda: full)
    prompt = (
        "Audio: x.\nReferences: [Image1] is the Kitchen.\nShot 1 | 0-5 s. Mom glares.\nAudio: x."
    )
    refs = [Reference(kind="image", id=f"place:{place.id}", role="Kitchen")]
    clip = clip_prompts.with_cast(db, project, ClipPrompt(clip_id="c1", seconds=5, prompt=prompt,
                                                          references=refs), _c9())  # fmt: skip
    assert [r.id for r in clip.references] == [ids["Peanut butter"]]  # the place made room

    plain = copy.deepcopy(_c9())
    plain.scenes[0].shots[0].action = "Mom glares."
    monkeypatch.setattr(clip_prompts, "video_model", lambda: full.model_copy(
        update={"max_reference_images": 5}))  # fmt: skip
    noted = clip_prompts.with_cast(db, project, ClipPrompt(clip_id="c1", seconds=5, prompt=prompt,
                                                           references=refs), plain,
                                   note="USE THE ACTUAL IRON PAWS PRODUCT BAG")  # fmt: skip
    assert ids["Peanut butter"] in [r.id for r in noted.references]  # Change it's note: attached
    bare = clip_prompts.with_cast(db, project, ClipPrompt(clip_id="c1", seconds=5, prompt=prompt,
                                                          references=refs), plain)  # fmt: skip
    assert [r.id for r in bare.references] == [f"place:{place.id}"]  # no bag in its words


def test_an_old_clip_with_three_screens_gets_no_fourth(db, owner, setup):  # noqa: F811
    from app.clip_prompts import with_cast
    from app.prompts.schemas import ClipPrompt

    project, ids = _bags(db, owner, setup)
    bd = _c9()
    bd.scenes[0].shots[1].screen_ids = ["screen:901", "screen:902", "screen:903"]
    prompt = "Audio: x.\nReferences: none.\nShot 1 | 0-5 s. Mom glares.\nAudio: x."
    clip = with_cast(db, project, ClipPrompt(clip_id="c1", seconds=5, prompt=prompt,
                                             references=[]), bd)  # fmt: skip
    assert ids["Peanut butter"] not in [r.id for r in clip.references]  # "keep the 3" blocks
