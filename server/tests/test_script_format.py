"""A script's format is a guides format (stream D): a format folder is a choice with no code
change, and the format's engine stays the script's kind for everything that runs it."""

import pytest

from app import guides
from app.models.freestyles import Freestyle
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from tests.conftest import first_brand

COOKING = {"id": "cooking", "name": "Cooking", "order": 9.0, "on": True, "engine": "story",
           "blurb": "A recipe, step by step.", "sections": {}}  # fmt: skip


@pytest.fixture
def cooking(monkeypatch):
    """Reed adds formats/cooking/guide.md: nothing else changes."""
    found = guides.formats()
    monkeypatch.setattr(guides, "formats", lambda: [*found, COOKING])


def _new(owner, **fields):
    body = {"brand_id": first_brand(owner), "title": "T", **fields}
    return owner.post("/scripts", json=body)


def test_a_new_format_folder_is_a_choice_and_a_script_can_take_it(owner, cooking):
    assert "cooking" in [f["id"] for f in owner.get("/formats").json()]
    made = _new(owner, format="cooking").json()
    assert (made["format"], made["kind"]) == ("cooking", "story")


def test_a_scripts_format_sets_its_kind_to_the_formats_engine(owner):
    assert _new(owner, format="narrated").json()["kind"] == "narrated"
    assert _new(owner, format="song").json()["kind"] == "song"


def test_a_script_with_no_format_has_its_kinds_default(owner):
    assert _new(owner).json()["format"] == "dialogue"
    assert _new(owner, kind="narrated").json()["format"] == "narrated"


def test_only_a_format_that_is_on_can_be_picked(owner):
    assert _new(owner, format="zack-d").status_code == 422  # on: no
    assert _new(owner, format="nope").status_code == 422
    made = _new(owner).json()
    assert owner.patch(f"/scripts/{made['id']}", json={"format": "zack-d"}).status_code == 422


def test_a_draft_changes_format_but_a_song_stays_a_song(owner, cooking):
    from app.routes.script_library import SONG_STAYS

    made = _new(owner, format="narrated").json()
    url = f"/scripts/{made['id']}"
    got = owner.patch(url, json={"format": "cooking"}).json()
    assert (got["format"], got["kind"]) == ("cooking", "story")
    assert owner.patch(url, json={"format": "song"}).status_code == 409
    song = _new(owner, format="song").json()
    no = owner.patch(f"/scripts/{song['id']}", json={"format": "narrated"})
    assert (no.status_code, no.json()["detail"]) == (409, SONG_STAYS)


def test_a_freestyle_type_is_a_format_and_its_script_carries_it(owner, db, cooking):
    body = {"type": "cooking", "look": "house", "shape": "9:16", "text": "MIA: Salt first."}
    fs = owner.post("/freestyles", json=body)
    assert fs.status_code == 201, fs.text
    row = db.get(Freestyle, fs.json()["id"])
    seen = {"see_hidden": True}
    project = db.get(Project, row.project_id, execution_options=seen)
    draft = db.get(ScriptDraft, project.script_draft_id)
    script = db.get(Script, draft.script_id, execution_options=seen)
    assert (row.type, script.format, script.kind) == ("cooking", "cooking", "story")
    assert owner.post("/freestyles", json={**body, "type": "zack-d"}).status_code == 422
    assert owner.post("/freestyles", json={**body, "type": "nope"}).status_code == 422


def test_the_scripts_own_format_beats_the_style_that_is_also_a_format():
    assert guides.video_format("narrated", "zack-d") == "zack-d"  # no pick: the style brings it
    assert guides.video_format("narrated", "zack-d", "narrated") == "narrated"  # a pick wins
    assert guides.video_format("story", "house", "gone") == "dialogue"  # a pick since removed
