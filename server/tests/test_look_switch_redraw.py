"""A look switch leaves a locked character with no sheet in the new look: the redraw of
their out-of-date still is refused before any charge, never drawn without them (Flow-QA,
QA-3's note on #947). All on the free stand-ins."""

from app.models.jobs import Job
from app.providers import get_providers
from tests.conftest import upload
from tests.helpers import with_sheet
from tests.test_fake_local import _drain
from tests.test_look_sheets import _video


def test_a_redraw_after_a_look_switch_waits_for_the_casts_look(app, db, editor, owner):
    project, _ = _video(app, owner, editor, db, look="house")
    providers = get_providers(app.state.settings)
    url = f"/projects/{project.id}"
    nate = owner.post(
        "/library/character", json={"name": "Nate", "image_file_ids": [upload(owner)]}
    )
    with_sheet(db, nate.json()["id"])
    (slot,) = [
        a["slot_id"] for a in editor.get(f"{url}/assets").json() if not a.get("library_item_id")
    ]
    editor.put(f"{url}/assets/slots/{slot}", json={"library_item_id": nate.json()["id"]})
    assert editor.post(f"{url}/storyboard", json={"per_shot": False}).status_code == 201
    _drain(app, db, providers)
    (frame,) = editor.get(f"{url}/storyboard").json()
    assert editor.post(f"{url}/storyboard/frames/{frame['id']}/render").status_code == 201
    _drain(app, db, providers)

    assert owner.post(f"{url}/settings", json={"look": "disney-pixar"}).status_code == 200
    assert not any(a["ready"] for a in editor.get(f"{url}/assets").json())
    (frame,) = editor.get(f"{url}/storyboard").json()
    assert frame["still_stale"]
    jobs = db.query(Job).count()
    redraw = editor.post(f"{url}/storyboard/frames/{frame['id']}/render")
    assert redraw.status_code == 422, redraw.text  # before: 201, drawn with files {}
    assert redraw.json()["detail"] == "Mia has no approved look yet. Approve one in Cast."
    for press in ("storyboard", "update-after?from=storyboard"):  # the same refusal
        again = editor.post(f"{url}/{press}", json={"per_shot": False})
        assert again.status_code in (409, 422) and "no approved look yet" in again.text, press
    redo = editor.post(f"{url}/storyboard/frames/{frame['id']}/redo")
    assert redo.status_code == 409, redo.text  # refused too: its breakdown is unchanged
    assert db.query(Job).count() == jobs  # nothing charged
