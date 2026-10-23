"""Script drafts: Claude writes 2–3 drafts from the brief (and, if the project has one, a
reference reel to adapt). They stay in the job's output; the editor picks one, which becomes
a new script version."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.auth import current_user
from app.db import get_db
from app.enhance import escape, project_context
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.projects import get_project
from app.routes.scripts import ScriptOut, _out, save_version

router = APIRouter(prefix="/projects/{project_id}/script", tags=["scripts"])
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)


class DraftOut(BaseModel):
    job_id: int
    n: int  # 1, 2, 3 within that job
    hook_idea: str
    script: str


def _draft_jobs(db: Session, project: Project, statuses) -> list[Job]:
    jobs = db.scalars(
        select(Job)
        .where(Job.project_id == project.id, Job.status.in_(statuses))
        .order_by(Job.id.desc())
    )
    return [j for j in jobs if j.input.get("step") == "script_draft"]


def job_input(db: Session, project: Project) -> dict:
    system, context = project_context(db, project, "script_draft")
    if project.reference_breakdown:
        ref = prompts.reference_block(project.reference_breakdown, project.reference_replace)
        context += f"\n{escape(ref)}"
    return {"step": "script_draft", "project_id": project.id, "system": system, "prompt": context}


@router.post(
    "/draft", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)]
)
def draft(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Queue a script-draft call (a paid Claude call, counted against the project budget)."""
    project = get_project(db, user, project_id)
    if _draft_jobs(db, project, WAITING):
        raise HTTPException(409, "Drafts are already being written for this project.")
    return enqueue(
        db, user, "write-claude", job_input(db, project), project=project, provider="claude"
    )


@router.get("/drafts", response_model=list[DraftOut])
def list_drafts(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The newest finished set of drafts (empty if none yet)."""
    done = _draft_jobs(db, get_project(db, user, project_id), (JobStatus.succeeded,))
    if not done:
        return []
    job = done[0]
    return [
        DraftOut(job_id=job.id, n=n, hook_idea=d["hook_idea"], script=d["script"])
        for n, d in enumerate(job.output.get("drafts", []), 1)
    ]


@router.post("/drafts/{job_id}/{n}/use", response_model=ScriptOut, status_code=201)
def use_draft(
    project_id: int,
    job_id: int,
    n: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Make draft `n` of that job the new working script (a new version, source "draft")."""
    project = get_project(db, user, project_id)
    job = db.get(Job, job_id)
    drafts = (job.output or {}).get("drafts", []) if job else []
    if (
        not job
        or job.project_id != project.id
        or job.input.get("step") != "script_draft"
        or not 1 <= n <= len(drafts)
    ):
        raise HTTPException(404, "No such draft.")
    return _out(save_version(db, user, project, drafts[n - 1]["script"], "draft"))
