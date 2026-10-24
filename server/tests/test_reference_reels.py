"""The reference reels a brief can adapt (docs/references), and picking one on a project."""

ALTAR = "fomo-DehudnaAmce"


def test_catalogue_lists_the_fomo_altar_reel_first(editor, client):
    refs = editor.get("/references").json()
    assert refs[0]["id"] == ALTAR and refs[0]["brand"] == "fomo" and refs[0]["seconds"] > 40
    assert all(r["has_thumbnail"] for r in refs) and len(refs) >= 2
    thumb = editor.get(f"/references/{ALTAR}/thumbnail")
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/jpeg"
    assert editor.get("/references/nope/thumbnail").status_code == 404
    assert editor.get("/references/..%2F..%2Fsettings/thumbnail").status_code == 404


def test_picking_a_reel_copies_its_breakdown_into_the_project(editor):
    fomo = editor.get("/brands").json()[0]["id"]
    body = {"brand_id": fomo, "name": "Altar", "planned_seconds": 45, "reference_id": ALTAR}
    made = editor.post("/projects", json=body).json()
    ref = made["reference_breakdown"]
    assert ref["source_id"] == ALTAR and len(ref["shots"]) == 50 and ref["duration_seconds"] > 40
    url = f"/projects/{made['id']}"
    replace = "the montage: a fomo trading montage"
    patched = editor.patch(url, json={"reference_id": ALTAR, "reference_replace": replace}).json()
    assert patched["reference_replace"] == replace and patched["reference_breakdown"] == ref
    assert editor.patch(url, json={"reference_id": "nope"}).status_code == 404
    assert (
        editor.patch(url, json={"reference_breakdown": None}).json()["reference_breakdown"] is None
    )


def test_a_picked_reel_still_drops_its_live_action_shots(editor):
    from app.prompts import reference_block

    fomo = editor.get("/brands").json()[0]["id"]
    body = {"brand_id": fomo, "name": "Altar", "planned_seconds": 45, "reference_id": ALTAR}
    ref = editor.post("/projects", json=body).json()["reference_breakdown"]
    assert {s["n"] for s in ref["shots"] if "live action" in s["style"]} == set(range(45, 51))
    block = reference_block(ref)
    listed = {int(line.split(".")[0]) for line in block.splitlines() if line[:1].isdigit()}
    assert max(listed) == 43  # 44 morphs into photoreal, 45–50 are live action: all dropped
    assert "Shots 44–50" in block and "always removed" in block
