"""Which brand a job is charged to, for Usage (DECISIONS #237): the project's brand, else the
request's brand (Quick clip, Improve), else the script's (writing, variations, cast), else the
library item's when it belongs to exactly one brand. Otherwise none: "Not tied to one brand"."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.library import item_brands
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft


def brand_for(db: Session, project: Project | None, input: dict) -> int | None:
    if project is not None:
        return project.brand_id
    if input.get("brand_id"):
        return input["brand_id"]
    script_id = input.get("script_id")
    if script_id is None and input.get("script_draft_id"):
        script_id = db.scalar(
            select(ScriptDraft.script_id).where(ScriptDraft.id == input["script_draft_id"])
        )
    if script_id is not None:
        return db.scalar(select(Script.brand_id).where(Script.id == script_id))
    if input.get("library_item_id"):
        brands = db.scalars(
            select(item_brands.c.brand_id).where(item_brands.c.item_id == input["library_item_id"])
        ).all()
        return brands[0] if len(brands) == 1 else None
    return None
