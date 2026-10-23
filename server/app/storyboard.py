"""Storyboard: Claude writes one image prompt per clip (or per shot) of the newest breakdown
and picks its reference pictures. Frames are saved with their problems; the editor can edit
them before any still is rendered."""

import json

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.catalogue import CatalogueModel, catalogue
from app.enhance import escape, project_context, screens_of
from app.images import image_job_input, image_model_block
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts import check
from app.prompts.schemas import Frame, StoryboardFrames

PREFIX = {Kind.character: "char", Kind.place: "place", Kind.prop: "prop"}


def image_model() -> CatalogueModel:
    return next(m for m in catalogue().values() if m.kind == "image" and m.default)


def assets(db: Session, project: Project) -> dict[str, tuple[str, list[int]]]:
    """Every picture a frame may use: asset id -> (its line for the prompt, its file ids).
    The cast, the brand's places and props, and the brand's screens."""
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
        out[key] = (f"{key} | {item.kind} | {item.name} | {item.notes}", item.image_file_ids)
    brand = db.get(Brand, project.brand_id)
    for s in screens_of(db, brand):
        what = f"{brand.name} app screen, {', '.join(s.tags)}"
        out[f"screen:{s.id}"] = (f"screen:{s.id} | screen | {s.name} | {what}", [s.file_id])
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


def frame_problems(db: Session, project: Project, frame: Frame) -> list[str]:
    m = image_model()
    known = assets(db, project)
    problems = check.storyboard(
        StoryboardFrames(frames=[frame]), m.max_reference_images, m.max_character_images
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
                problems=frame_problems(db, project, f),
            )
        )


def render_input(db: Session, project: Project, frame: StoryboardFrame) -> dict:
    """The Nano Banana job for one frame's still: the project's aspect ratio (always sent),
    character sheets first, then the place, props and screens, in the frame's order."""
    known = assets(db, project)
    characters, objects = [], []
    for ref in frame.reference_ids:
        if ref not in known:
            raise HTTPException(409, f"{ref} is no longer part of this project. Edit the frame.")
        files = known[ref][1][:1]  # an item's first picture is its sheet / main reference
        (characters if ref.startswith("char:") else objects).extend(files)
    job = image_job_input(
        image_model(), frame.prompt, project.aspect_ratio, characters=characters, objects=objects
    )
    return {**job, "step": "frame", "project_id": project.id, "frame_id": frame.id}


def save_still(db: Session, job: Job) -> None:
    """Attach the rendered still to its frame (if the frame still exists)."""
    frame = db.get(StoryboardFrame, job.input["frame_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if frame and file_ids:
        frame.file_id = file_ids[0]
