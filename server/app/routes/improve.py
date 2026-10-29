"""Quick clip "Improve prompt": Claude turns the editor's idea into a full video prompt in the
Director's shape. Only camera, movement, reactions and where brand screens show are added; the
editor's quoted words and names stay exactly. The result is shown for editing; nothing is
generated until the editor presses Generate (then sent with `improved: true`)."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.advice import Said, SaidText
from app.auth import current_user
from app.db import get_db
from app.enhance import escape, screens_of
from app.models.accounts import User
from app.models.brands import Brand
from app.models.jobs import Job, JobStatus
from app.prompts import check
from app.prompts.schemas import ImprovedPrompt
from app.routes.clips import ClipIn, _plan, generation_on
from app.routes.jobs import JobOut, enqueue

router = APIRouter(prefix="/clips/improve", tags=["clips"])


class ImproveIn(ClipIn):
    direction: Literal["Cinematic", "Realistic", "Funny", "Product ad"] = "Cinematic"
    shots: int = Field(2, ge=1, le=4)


class ImproveOut(BaseModel):
    status: str
    prompt: str | None  # the improved prompt, when ready; editable before Generate
    problems: Said  # what the checks found, in plain words
    error: SaidText


def job_input(db: Session, brand: Brand, body: ImproveIn, references: str) -> dict:
    screens = [
        {
            "id": s.id,
            "name": s.name,
            "tags": s.tags,
            "default_for": s.default_for,
            "balance": s.balance,
        }
        for s in screens_of(db, brand)
    ]
    brand_dict = {
        "name": brand.name,
        "tone_notes": brand.tone_notes,
        "never_say": brand.dont_list,
        "legal_line": brand.legal_line,
    }
    brief = f"direction: {body.direction}; shots: {body.shots}; seconds: {body.duration}"
    return {
        "step": "improve",
        "brand_id": brand.id,
        "idea": body.prompt,
        "references": references,
        "shots": body.shots,
        "seconds": body.duration,
        "system": [prompts.system("improve"), prompts.brand_block(brand_dict, screens)],
        "prompt": (
            f"<brief>{brief}</brief>\n<references>{escape(references)}</references>\n"
            f"<idea>{escape(body.prompt)}</idea>"
        ),
    }


def save_improved(db: Session, job: Job) -> None:
    """Keep the checks' problems next to the answer for the editor to see."""
    result = ImprovedPrompt.model_validate(job.output)
    i = job.input
    problems = check.improve(i["idea"], result, i["references"], i["shots"], i["seconds"])
    job.output = {**job.output, "problems": problems}


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def improve(
    body: ImproveIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Queue an Improve call (a paid Claude call, about 3 credits from the weekly allowance).
    The brand pieces are checked as for Generate, so the reference lines match."""
    waiting = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
    mine = db.scalars(select(Job).where(Job.created_by_id == user.id, Job.status.in_(waiting)))
    if any(j.input.get("step") == "improve" for j in mine):  # a double press: one paid call
        raise HTTPException(409, "Your prompt is already being improved.")
    plan = _plan(db, user, body, request.app.state.storage)
    brand = db.get(Brand, body.brand_id)
    return enqueue(
        db, user, "write-claude", job_input(db, brand, body, plan.references), provider="claude"
    )


@router.get("/{job_id}", response_model=ImproveOut)
def result(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.workspace_id != user.workspace_id or job.input.get("step") != "improve":
        raise HTTPException(404, "No such Improve run.")
    done = job.status == JobStatus.succeeded and job.output
    return ImproveOut(
        status=job.status,
        prompt=job.output.get("prompt") if done else None,
        problems=job.output.get("problems", []) if done else [],
        error=job.error,
    )
