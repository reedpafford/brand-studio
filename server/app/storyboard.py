"""Storyboard: Claude writes one image prompt per clip (or per shot) of the newest breakdown
and picks its reference pictures. Frames are saved with their problems; the editor can edit
them before any still is rendered."""

import json

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.catalogue import CatalogueModel, catalogue
from app.enhance import escape, project_context, project_screens, screen_name
from app.images import image_job_input, image_model_block
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot, ScriptDraft
from app.models.storyboards import StoryboardFrame
from app.prompts import check
from app.prompts.schemas import Breakdown, Frame, StoryboardFrames
from app.sheets import require_cast_sheets, require_sheet, usable_files

PREFIX = {Kind.character: "char", Kind.place: "place", Kind.prop: "prop"}


def image_model() -> CatalogueModel:
    return next(m for m in catalogue().values() if m.kind == "image" and m.default)


def script_slots(db: Session, project: Project) -> list[ScriptCastSlot]:
    """The cast slots of the library script this video is made from (none for older videos)."""
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if draft is None:
        return []
    return list(
        db.scalars(select(ScriptCastSlot).where(ScriptCastSlot.script_id == draft.script_id))
    )


def assets(db: Session, project: Project) -> dict[str, tuple[str, list[int]]]:
    """Every picture a frame may use: asset id -> (its line for the prompt, its file ids).
    The cast, the script's cast slots (slot:N, locked or not: an unlocked one has no picture
    until Assets casts it, and is never a problem), the brand's places and props, and the
    brand's screens."""
    out: dict[str, tuple[str, list[int]]] = {}
    items = db.scalars(
        select(LibraryItem).where(
            LibraryItem.workspace_id == project.workspace_id, LibraryItem.archived.is_(False)
        )
    )
    for item in items:
        in_brand = any(b.id == project.brand_id for b in item.brands)
        if item.kind == Kind.character and item.id not in project.cast_ids:
            continue
        if item.kind != Kind.character and not in_brand:
            continue
        key = f"{PREFIX[item.kind]}:{item.id}"
        out[key] = (f"{key} | {item.kind} | {item.name} | {item.notes}", usable_files(item))
    for slot in script_slots(db, project):  # a role a breakdown may name before it's cast
        item_id = slot.library_item_id or project.slot_cast.get(str(slot.id))
        item = db.get(LibraryItem, item_id) if item_id else None
        look = "" if item else " (no look yet)"
        line = f"slot:{slot.id} | character | {slot.role} | {slot.description}{look}"
        out[f"slot:{slot.id}"] = (line, usable_files(item) if item else [])
    brand = db.get(Brand, project.brand_id)
    for s in project_screens(db, project):
        product = "product" in s.tags  # e.g. the Iron Paws bag: shown as a product, no face
        kind, what = ("product", "product") if product else ("screen", "app screen")
        name = screen_name(s)
        line = f"screen:{s.id} | {kind} | {name} | {brand.name} {what}, {', '.join(s.tags)}"
        out[f"screen:{s.id}"] = (line, [s.file_id])
    return out


def job_input(db: Session, project: Project, bd: BreakdownVersion, per_shot: bool) -> dict:
    system, _ = project_context(db, project, "storyboard")
    lines = "\n".join(line for line, _ in assets(db, project).values())
    parts = [
        image_model_block(image_model(), project.aspect_ratio),
        f"<assets>\n{escape(lines)}\n</assets>",
        f"<breakdown>\n{escape(json.dumps(bd.data, ensure_ascii=False))}\n</breakdown>",
    ]
    if per_shot:
        parts.append("<per_shot>true</per_shot>")
    return {
        "step": "storyboard",
        "project_id": project.id,
        "breakdown_id": bd.id,
        "system": system,
        "prompt": "\n".join(parts),
        "max_tokens": 32000,
    }


def frame_problems(db: Session, project: Project, frame: Frame, breakdown_id: int) -> list[str]:
    """With the frame's breakdown, a character in the shot but not attached is flagged too."""
    m = image_model()
    known = assets(db, project)
    bd = Breakdown.model_validate(db.get(BreakdownVersion, breakdown_id).data)
    problems = check.storyboard(
        StoryboardFrames(frames=[frame]), m.max_reference_images, m.max_character_images, bd
    )
    problems += [
        f"{frame.clip_id}: unknown reference {r}" for r in frame.reference_ids if r not in known
    ]
    return problems


def save_frames(db: Session, job: Job) -> None:
    """Replace the project's frames with Claude's new ones (a new storyboard was asked for)."""
    project = db.get(Project, job.input["project_id"])
    result = StoryboardFrames.model_validate(job.output)
    db.execute(delete(StoryboardFrame).where(StoryboardFrame.project_id == project.id))
    for f in result.frames:
        db.add(
            StoryboardFrame(
                project_id=project.id,
                breakdown_id=job.input["breakdown_id"],
                job_id=job.id,
                clip_id=f.clip_id,
                shot_id=f.shot_id,
                prompt=f.prompt,
                reference_ids=f.reference_ids,
                problems=frame_problems(db, project, f, job.input["breakdown_id"]),
            )
        )


def render_input(db: Session, project: Project, frame: StoryboardFrame, note: str = "") -> dict:
    """The Nano Banana job for one frame's still: the project's aspect ratio (always sent),
    character sheets first, then the place, props and screens, in the frame's order."""
    known = assets(db, project)
    breakdown = db.get(BreakdownVersion, frame.breakdown_id)
    require_cast_sheets(db, breakdown.data, [frame.shot_id])
    characters, objects = [], []
    for ref in frame.reference_ids:
        if ref not in known:
            raise HTTPException(409, f"{ref} is no longer part of this project. Edit the frame.")
        files = known[ref][1][:1]  # the approved sheet (characters, places) or main picture
        if not files and ref.startswith(("char:", "place:")):
            require_sheet(db.get(LibraryItem, int(ref.split(":")[1])))
        (characters if ref.startswith("char:") else objects).extend(files)
    prompt = f"{frame.prompt}\nChange from the last still: {note}" if note else frame.prompt
    job = image_job_input(
        image_model(), prompt, project.aspect_ratio, characters=characters, objects=objects
    )
    return {**job, "step": "frame", "project_id": project.id, "frame_id": frame.id}


def save_still(db: Session, job: Job) -> None:
    """Attach the rendered still to its frame (if the frame still exists)."""
    frame = db.get(StoryboardFrame, job.input["frame_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if frame and file_ids:
        if frame.file_id and frame.file_id != file_ids[0]:  # the old still stays, to pick back
            frame.earlier = [
                *(frame.earlier or []),
                {"file_id": frame.file_id, "prompt": frame.prompt},
            ]
        frame.file_id, frame.approved, frame.still_stale = file_ids[0], False, False
