"""Produce a library version (workflow v2): make its project, once. The project gets the
version's words as script v1, the script's brand, reel and locked cast, and either the saved
breakdown preview (free) or its plan made now (paid, from the project's budget or, for an
editor's own script, their weekly allowance). From there the usual steps run."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import breakdown, credits, narration, plans, script_preview, sheets, song_takes
from app import script_library as lib
from app import video_settings as vs
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.projects import Project
from app.models.script_library import ScriptCastSlot
from app.models.scripts import ScriptVersion
from app.prompts.schemas import Breakdown
from app.routes.clips import generation_on
from app.routes.estimate import version_cost
from app.routes.jobs import enqueue
from app.routes.projects import _set_length
from app.routes.references import for_script as script_reference
from app.routes.script_library import Slot
from app.routes.video_settings import VideoSettingsIn

router = APIRouter(prefix="/scripts/{script_id}/drafts/{slot}", tags=["script library"])


class ProduceOut(BaseModel):
    project_id: int
    breakdown_job_id: int | None  # shots being made: an owner's approved plan (S6)
    plan_job_id: int | None = None  # the plan being made (flows 1b): the usual start


@router.post(
    "/produce", response_model=ProduceOut, status_code=201, dependencies=[Depends(generation_on)]
)
def produce(
    script_id: int,
    slot: Slot,
    request: Request,
    body: VideoSettingsIn | None = None,  # Make this version's Video settings row (VS1)
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Start production of an approved version of a published script. Each version makes
    one video, reserved for whoever starts it, with the settings sent (VS1), each checked by its
    own rules: a look's On/Off, the catalogue's models, the brand's flavours."""
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
        product_variants=lib.offered_flavours(db, script.brand_id, draft),  # n03: its defaults
    )
    settings = body.model_dump(exclude_none=True) if body else {}
    if "product_variants" in settings:  # the picks sent win, product by product (n03)
        settings["product_variants"] = {**project.product_variants, **settings["product_variants"]}
    for field, value in settings.items():
        setattr(project, *vs.check(db, user, project, {field: value}).popitem())
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
    plans.copy_to_video(project, draft)  # S6: the owner's approved plan is its start
    if draft.breakdown and plans.preview_follows(draft):
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
                data={**bd.model_dump(), **({"plan_version": 1} if project.plan else {})},
                problems=breakdown.problems(db, project, draft.text, bd) + removed,
                created_by_id=user.id,
            )
        )
        db.flush()
        vs.follow_lip_sync(db, project, could=True)  # a no-lip-sync model: Sung shots to B-roll
        db.commit()
        return ProduceOut(project_id=project.id, breakdown_job_id=None)
    # Every video gets a plan before its shots (flows 1b): the plan call is what this press
    # charges, and the editor approves it to make the shots. An owner's approved plan (S6) goes
    # straight to the shots. One transaction: if the call is declined (allowance or cap), the
    # project and the reservation go too, so the version stays free to produce.
    shots = bool(project.plan and project.plan.get("approved_at"))
    data = (
        breakdown.job_input(db, project, version)
        if shots
        else plans.job_input(db, project, version)
    )
    try:
        job = enqueue(db, user, plans.KIND, data, project=project, provider="claude")
    except HTTPException:
        db.rollback()
        raise
    if shots:
        return ProduceOut(project_id=project.id, breakdown_job_id=job.id)
    return ProduceOut(project_id=project.id, breakdown_job_id=None, plan_job_id=job.id)


class VersionEstimateOut(BaseModel):
    credits: float  # "about N credits to make", every step: the version's estimate_credits
    over_cap: bool  # over the video limit
    reason: str  # why it can't be made like this ("" when nothing is in the way)


@router.post("/estimate", response_model=VersionEstimateOut)
def version_estimate(
    script_id: int,
    slot: Slot,
    body: VideoSettingsIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Make this version's price line with the Video settings row's picks (VS1), each checked
    as on produce (a bad pick: 422 or 409). The choices come from GET /models, /looks and the
    brand's screens. Free."""
    script = lib.get_script(db, user, script_id)
    draft = lib.get_draft(db, script, slot)
    video = Project(
        workspace_id=user.workspace_id,
        brand_id=script.brand_id,
        look=script.look,
        script_draft_id=draft.id,
        created_by_id=user.id,
    )  # never saved
    for field, value in (body.model_dump(exclude_none=True) if body else {}).items():
        setattr(video, *vs.check(db, user, video, {field: value}).popitem())
    cost = version_cost(db, draft, video)  # a look for each uncast role included
    roles = sheets.roles_needing_look(db, script, video.look)  # cast ones without this look
    cost += len(roles) * sheets.look_price(db, user.workspace_id)  # as VS1's to_finish
    cap = credits.get_limits(db, user.workspace_id).per_video_max_credits
    week = credits.over_allowance(db, user, video, cost)
    reason = vs.OVER_CAP.format(cap) if cost > cap else week
    return VersionEstimateOut(credits=float(cost), over_cap=cost > cap, reason=reason)
