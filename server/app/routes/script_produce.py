"""Produce a library version (workflow v2): make its project, once. The project gets the
version's words as script v1, the script's brand, reel and locked cast, and either the saved
breakdown preview (free) or a breakdown run now (paid, from the project's budget or, for an
editor's own script, their weekly allowance). From there the usual steps run."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import breakdown, narration, script_preview, song_takes
from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot
from app.models.scripts import ScriptVersion
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.jobs import enqueue
from app.routes.projects import _set_length
from app.routes.references import for_script as script_reference
from app.routes.script_library import Slot

router = APIRouter(prefix="/scripts/{script_id}/drafts/{slot}", tags=["script library"])


class ProduceOut(BaseModel):
    project_id: int
    breakdown_job_id: int | None  # a breakdown being made; null when the saved one was used


@router.post(
    "/produce", response_model=ProduceOut, status_code=201, dependencies=[Depends(generation_on)]
)
def produce(
    script_id: int,
    slot: Slot,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Start production of an approved version of a published script. Each version makes
    one video, reserved for whoever starts it."""
    script = lib.get_script(db, user, script_id)
    draft = lib.get_draft(db, script, slot)
    if not script.published:
        raise HTTPException(409, "Publish this script first.")
    if draft.status != "approved":
        raise HTTPException(409, "Approve this version first.")
    if db.scalar(select(Project.id).where(Project.script_draft_id == draft.id)):
        raise HTTPException(409, "This version already has a video.")
    slots = db.scalars(select(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id))
    name = f"{script.title} — {draft.title}" if slot and draft.title else script.title
    project = Project(
        workspace_id=user.workspace_id,
        brand_id=script.brand_id,
        name=name[:120],
        goal=script.description,
        created_by_id=user.id,
        cast_ids=sorted({s.library_item_id for s in slots if s.library_item_id}),
        reference_breakdown=script_reference(request, script),
        reference_replace=script.reference_replace,
        script_draft_id=draft.id,
        look=script.look,  # the video's own from here on (VS1)
    )
    if script.kind in narration.TIMED and (take := song_takes.preferred(db, draft)):
        project.song_take_id = take.id  # the video's own choice from here on (rule 31)
    _set_length(db, user, project, draft.target_seconds)
    draft.reserved_by_id = user.id
    db.add(project)
    try:
        db.flush()  # the unique version link: two people pressing at once can't both win
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This version already has a video.") from None
    version = ScriptVersion(
        project_id=project.id, version=1, text=draft.text, source="library", created_by_id=user.id
    )
    db.add(version)
    if draft.breakdown:
        plan = Breakdown.model_validate(draft.breakdown)
        named = {r for sc in plan.scenes for sh in sc.shots for r in sh.character_ids}
        live = named & script_preview.live_looks(db, script)  # a look the plan names joins the cast
        project.cast_ids = sorted({*project.cast_ids, *(int(r[5:]) for r in live)})
        db.flush()
        bd, removed = breakdown.land(db, project, plan)
        breakdown.record_length(project, bd)
        db.add(
            BreakdownVersion(
                project_id=project.id,
                script_version=1,
                source="library",
                data=bd.model_dump(),
                problems=breakdown.problems(db, project, draft.text, bd) + removed,
                created_by_id=user.id,
            )
        )
        db.commit()
        return ProduceOut(project_id=project.id, breakdown_job_id=None)
    # One transaction: if the breakdown is declined (allowance or cap), the project and the
    # reservation go too, so the version stays free to produce.
    try:
        job = enqueue(
            db,
            user,
            "write-claude",
            breakdown.job_input(db, project, version),
            project=project,
            provider="claude",
        )
    except HTTPException:
        db.rollback()
        raise
    return ProduceOut(project_id=project.id, breakdown_job_id=job.id)
