"""Read a script's cast with Claude (one paid call) and see what it found."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import script_cast_read as cast_read
from app import script_library as lib
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.jobs import Job, JobStatus
from app.routes.clips import generation_on
from app.routes.jobs import JobOut, enqueue
from app.routes.references import load as load_reference

router = APIRouter(prefix="/scripts/{script_id}/cast/read", tags=["script library"])


class ReadOut(BaseModel):
    running: bool  # the cast is being read
    problems: list[str]  # the newest read's checks ("Advice: " never blocks)


def _jobs(db: Session, script_id: int, statuses) -> list[Job]:
    jobs = db.scalars(
        select(Job)
        .where(Job.status.in_(statuses), Job.kind == "write-claude")
        .order_by(Job.id.desc())
    )
    return [
        j
        for j in jobs
        if j.input.get("step") == "cast_slots" and j.input.get("script_id") == script_id
    ]


@router.get("", response_model=ReadOut)
def read_status(script_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    script = lib.get_script(db, user, script_id)
    done = _jobs(db, script.id, (JobStatus.succeeded,))
    return ReadOut(
        running=lib.writing(db, script.id, "cast_slots"),
        problems=cast_read.problems(db, script, done[0]) if done else [],
    )


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(generation_on)])
def read_cast(
    script_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Read the roles every approved version needs a look for. Slots the script already has
    stay (locked ones stay locked); new roles are added unlocked."""
    script = lib.editable(user, lib.get_script(db, user, script_id))
    if not cast_read.ready(db, script):
        raise HTTPException(409, "Approve the original first.")
    if lib.writing(db, script.id, "cast_slots"):
        raise HTTPException(409, "The cast is already being read for this script.")
    reference = load_reference(request, script.reference_id) if script.reference_id else None
    data = cast_read.job_input(db, script, reference)
    return enqueue(db, user, "write-claude", data, provider="claude")
