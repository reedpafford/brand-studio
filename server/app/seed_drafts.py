"""Script drafts written by agents from reels, loaded into the live Script Library on every
deploy (`python -m app.seed refresh`). Each `docs/references/**/DRAFT-<brand>.json` becomes one
unpublished script, owned by the workspace owner, in each workspace with that brand: its
catalogue reel, version A's words and unlocked cast slots. Reed reviews, locks and publishes.

A file is imported once per workspace (`seeded_scripts` keeps the key), so Reed's edits, locks,
publishing and deletions are never undone. A bad file is skipped with a log line. Files are
checked with the same request models the routes use; tests/test_seed_drafts.py checks every
file in the repo, so a bad one fails CI before it reaches live."""

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import Role, User
from app.models.brands import Brand
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft, SeededScript
from app.routes.references import catalogue
from app.routes.script_cast import SlotIn
from app.routes.script_library import DraftIn, ScriptIn

log = logging.getLogger(__name__)


class CastIn(SlotIn):
    appears_in: list[int] = Field(default_factory=list)


class DraftFile(BaseModel):
    brand: str  # the brand's slug
    title: str
    description: str = ""
    reference_id: str
    text: str
    changed_lines: list[str] = Field(default_factory=list)
    cast: list[CastIn] = Field(default_factory=list, max_length=30)


def load(path: Path, references_dir: str) -> DraftFile:
    """The file, checked like the routes check a new script, its words and its cast slots.
    Raises ValueError with a plain reason."""
    try:
        draft = DraftFile.model_validate(json.loads(path.read_text()))
        ScriptIn(brand_id=0, **draft.model_dump(include={"title", "description", "reference_id"}))
        DraftIn(text=draft.text)
    except (ValueError, ValidationError) as exc:
        raise ValueError(f"{path.name}: {exc}") from None
    if draft.reference_id not in catalogue(references_dir):
        raise ValueError(f"{path.name}: no reel {draft.reference_id!r} in the catalogue")
    roles = [c.role.lower() for c in draft.cast]
    if len(roles) != len(set(roles)):
        raise ValueError(f"{path.name}: a cast role is listed twice")
    return draft


def files(references_dir: str) -> list[Path]:
    return sorted(Path(references_dir).glob("**/DRAFT-*.json"))


def import_drafts(db: Session, references_dir: str) -> int:
    """Each new (workspace, file) once; returns how many scripts were made."""
    made = 0
    for path in files(references_dir):
        try:
            draft = load(path, references_dir)
        except ValueError as exc:
            log.warning("Skipping script draft %s", exc)
            continue
        key = f"{draft.reference_id}/{path.name}"
        for brand in db.scalars(select(Brand).where(Brand.slug == draft.brand)):
            done = select(SeededScript.id).where(
                SeededScript.workspace_id == brand.workspace_id, SeededScript.key == key
            )
            owner = db.scalar(  # the first active owner: a removed one never authors drafts
                select(User)
                .where(
                    User.workspace_id == brand.workspace_id,
                    User.role == Role.owner,
                    User.active.is_(True),
                )
                .order_by(User.id)
                .limit(1)
            )
            if db.scalar(done) or owner is None:
                continue
            _make(db, brand, owner, draft)
            db.add(SeededScript(workspace_id=brand.workspace_id, brand_id=brand.id, key=key))
            db.commit()
            made += 1
    return made


def _make(db: Session, brand: Brand, owner: User, draft: DraftFile) -> None:
    script = Script(
        workspace_id=brand.workspace_id,
        brand_id=brand.id,
        title=draft.title.strip(),
        description=draft.description,
        reference_id=draft.reference_id,
        created_by_id=owner.id,
    )
    db.add(script)
    db.flush()
    db.add(
        ScriptDraft(
            script_id=script.id, slot=0, text=draft.text.strip(), changed_lines=draft.changed_lines
        )
    )
    for position, slot in enumerate(draft.cast, 1):
        db.add(
            ScriptCastSlot(
                script_id=script.id,
                role=slot.role,
                kind=slot.kind or "Main",
                description=slot.description,
                appears_in=sorted(set(slot.appears_in)),
                position=position,
            )
        )
