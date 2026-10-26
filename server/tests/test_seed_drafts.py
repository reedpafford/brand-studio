"""Script draft files from the repo, loaded into the library by `seed refresh`: once each per
workspace, never undoing Reed's edits or deletions; a bad file is skipped."""

import json
import logging
import shutil

import pytest

from app import seed_drafts
from app.models.script_library import Script
from app.settings import REPO_ROOT

REEL = "fomo-DehudnaAmce"
DRAFT = {
    "brand": "fomo",
    "title": "Altar, fomo",
    "description": "The altar reel for fomo",
    "reference_id": REEL,
    "text": "SCENE 1 — EXT. ALTAR — DAY\nNATE: I do.\nBRIDE: HELL NO!",
    "changed_lines": [],
    "cast": [
        {"role": "Nate", "description": "the groom", "kind": "Main", "appears_in": [0]},
        {"role": "Bride", "kind": "Rival"},
    ],
}


@pytest.fixture
def refs(tmp_path):
    root = tmp_path / "references"
    shutil.copytree(REPO_ROOT / "docs/references" / REEL, root / REEL)
    return root


def _write(refs, name: str, data: dict) -> None:
    (refs / REEL / name).write_text(json.dumps(data))


def test_a_draft_file_becomes_one_unpublished_script_once(owner, db, refs):
    _write(refs, "DRAFT-fomo.json", DRAFT)
    assert seed_drafts.import_drafts(db, str(refs)) == 1
    (row,) = owner.get("/scripts").json()
    script = owner.get(f"/scripts/{row['id']}").json()
    assert (script["title"], script["published"], script["reference_id"]) == (
        "Altar, fomo",
        False,
        REEL,
    )
    assert script["versions"][0]["text"] == DRAFT["text"]
    assert [(c["role"], c["kind"], c["locked"]) for c in script["cast"]] == [
        ("Nate", "Main", False), ("Bride", "Rival", False)
    ]  # fmt: skip
    assert seed_drafts.import_drafts(db, str(refs)) == 0  # a second deploy: nothing new


def test_edits_and_deletes_are_never_undone(owner, db, refs):
    _write(refs, "DRAFT-fomo.json", DRAFT)
    seed_drafts.import_drafts(db, str(refs))
    sid = owner.get("/scripts").json()[0]["id"]
    owner.patch(f"/scripts/{sid}", json={"title": "Reed's title"})
    seed_drafts.import_drafts(db, str(refs))
    assert [s["title"] for s in owner.get("/scripts").json()] == ["Reed's title"]
    owner.delete(f"/scripts/{sid}")
    assert seed_drafts.import_drafts(db, str(refs)) == 0
    assert owner.get("/scripts").json() == []


def test_a_bad_file_is_skipped_and_the_others_still_load(owner, db, refs, caplog, monkeypatch):
    _write(refs, "DRAFT-fomo.json", DRAFT)
    _write(refs, "DRAFT-bad.json", {**DRAFT, "reference_id": "nope"})
    _write(refs, "DRAFT-empty.json", {**DRAFT, "text": "  "})
    # alembic's logging config (other tests run migrations) switches existing loggers off
    monkeypatch.setattr(logging.getLogger("app.seed_drafts"), "disabled", False)
    with caplog.at_level(logging.WARNING, logger="app.seed_drafts"):
        assert seed_drafts.import_drafts(db, str(refs)) == 1
    assert db.query(Script).count() == 1
    assert "DRAFT-bad.json" in caplog.text and "DRAFT-empty.json" in caplog.text


@pytest.mark.parametrize("path", seed_drafts.files(str(REPO_ROOT / "docs/references")), ids=str)
def test_every_draft_file_in_the_repo_is_valid(path):
    """A bad DRAFT-*.json fails CI here before a deploy skips it on live."""
    seed_drafts.load(path, str(REPO_ROOT / "docs/references"))


def test_seeded_drafts_are_by_the_first_active_owner(owner, db, refs):
    """QA on #504: a removed owner (the QA test owner) never authors seeded drafts."""
    from app.models.accounts import Role, User

    reed = db.query(User).filter_by(email="reed@example.com").one()
    other = User(workspace_id=reed.workspace_id, email="o@example.com", name="Other",
                 password_hash="x", role=Role.owner)  # fmt: skip
    db.add(other)
    reed.active = False  # removed: the first owner by id, but not active
    db.commit()
    _write(refs, "DRAFT-fomo.json", DRAFT)
    assert seed_drafts.import_drafts(db, str(refs)) == 1
    assert db.query(Script).one().created_by_id == other.id
