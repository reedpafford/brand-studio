"""Product variants (e.g. Iron Paws chicken / peanut butter bags): each project picks one,
and only that one reaches the project's steps."""

from app.models.projects import Project
from app.storyboard import assets
from tests.conftest import upload


def _bags(editor):
    brand = editor.post("/brands", json={"name": "Iron Paws Test"}).json()["id"]
    ids = {}
    for variant in ("Chicken", "Peanut butter"):
        body = {
            "name": f"Bag {variant}",
            "file_id": upload(editor),
            "tags": ["product", "bag"],
            "product": "bag",
            "variant": variant,
        }
        r = editor.post(f"/brands/{brand}/screens", json=body)
        assert r.status_code == 201 and r.json()["variant"] == variant
        ids[variant] = r.json()["id"]
    project = editor.post(
        "/projects", json={"brand_id": brand, "name": "Gym", "planned_seconds": 20}
    ).json()["id"]
    return brand, ids, project


def _lines(db, project):
    return [line for line, _ in assets(db, db.get(Project, project)).values()]


def test_project_uses_only_its_chosen_variant(db, editor):
    _, ids, project = _bags(editor)
    first = _lines(db, project)  # nothing picked yet: the first variant
    assert any(f"screen:{ids['Chicken']} | product | Bag Chicken |" in x for x in first)
    assert not any(f"screen:{ids['Peanut butter']}" in x for x in first)

    r = editor.patch(f"/projects/{project}", json={"product_variants": {"bag": "Peanut butter"}})
    assert r.json()["product_variants"] == {"bag": "Peanut butter"}
    picked = _lines(db, project)
    assert any(
        f"screen:{ids['Peanut butter']} | product | Bag Peanut butter |" in x for x in picked
    )
    assert not any(f"screen:{ids['Chicken']}" in x for x in picked)


def test_unknown_variant_is_refused(editor):
    _, _, project = _bags(editor)
    r = editor.patch(f"/projects/{project}", json={"product_variants": {"bag": "Salmon"}})
    assert (r.status_code, r.json()["detail"]) == (422, "bag comes in: Chicken, Peanut butter.")
    r = editor.patch(f"/projects/{project}", json={"product_variants": {"can": "Chicken"}})
    assert r.status_code == 422 and r.json()["detail"] == "can comes in: none."


FOMO_END = "Want to trade like me? Download fomo through the link in my bio."


def test_breakdown_checks_get_the_brands_end_line(db, owner, editor, monkeypatch):
    from app import breakdown
    from app.prompts.schemas import Breakdown
    from tests.test_breakdown import BREAKDOWN

    fomo = owner.get("/brands").json()[0]
    assert fomo["end_line"] == FOMO_END
    project = editor.post(
        "/projects", json={"brand_id": fomo["id"], "name": "Dip", "planned_seconds": 20}
    ).json()["id"]
    seen = {}

    def check_breakdown(script, bd, screens, min_s, max_s, end_line=""):
        seen["end_line"] = end_line
        return ["the script doesn't end on the brand's end line"] if end_line else []

    monkeypatch.setattr(breakdown.check, "breakdown", check_breakdown)
    found = breakdown.problems(
        db, db.get(Project, project), "A\nB", Breakdown.model_validate(BREAKDOWN)
    )
    assert seen["end_line"] == FOMO_END
    assert "the script doesn't end on the brand's end line" in found


def test_seed_fills_an_empty_end_line(app, db, owner):
    from app.models.brands import Brand
    from app.seed import seed_brands

    fomo = db.query(Brand).filter_by(slug="fomo").one()
    fomo.end_line = ""  # a brand made before end lines existed
    db.commit()
    seed_brands(db, fomo.workspace_id, app.state.storage)
    db.refresh(fomo)
    assert fomo.end_line == FOMO_END
