"""Projects with a credit budget (2x the 480p estimate), and the credit rates per job kind.
Editors see credits and % of budget, never dollars."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_user, owner_only
from app.credits import credits_used, get_rate
from app.db import get_db
from app.models.accounts import User
from app.models.credits import CreditRate, Project
from app.routes.brands import get_brand
from app.schemas import Name

router = APIRouter(tags=["credits"])


class ProjectIn(BaseModel):
    brand_id: int
    name: Name
    estimate_credits: Decimal = Field(gt=0, le=100000)  # credits at 480p


class ProjectPatch(BaseModel):
    name: Name | None = None
    estimate_credits: Decimal | None = Field(None, gt=0, le=100000)  # owner only


class ProjectOut(BaseModel):
    id: int
    brand_id: int
    name: str
    estimate_credits: float
    budget_credits: float
    credits_used: float
    budget_pct: float


class RateIn(BaseModel):
    unit: Name
    credits_per_unit: Decimal = Field(gt=0, le=10000)


class RateOut(BaseModel):
    kind: str
    unit: str
    credits_per_unit: float


def get_project(db: Session, user: User, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project or project.workspace_id != user.workspace_id:
        raise HTTPException(404, "No such project.")
    return project


def _out(db: Session, project: Project) -> ProjectOut:
    used = credits_used(db, project)
    return ProjectOut(
        id=project.id,
        brand_id=project.brand_id,
        name=project.name,
        estimate_credits=project.estimate_credits,
        budget_credits=project.budget_credits,
        credits_used=used,
        budget_pct=round(float(used / project.budget_credits * 100), 1),
    )


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    brand_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    query = select(Project).where(Project.workspace_id == user.workspace_id)
    if brand_id is not None:
        query = query.where(Project.brand_id == brand_id)
    return [_out(db, p) for p in db.scalars(query.order_by(func.lower(Project.name)))]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    get_brand(db, user, body.brand_id)
    project = Project(workspace_id=user.workspace_id, **body.model_dump())
    db.add(project)
    db.commit()
    return _out(db, project)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def read_project(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return _out(db, get_project(db, user, project_id))


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Anyone can rename. Changing the estimate changes the budget, so only the owner can."""
    project = get_project(db, user, project_id)
    if body.estimate_credits is not None:
        if not user.is_owner:
            raise HTTPException(403, "Only the owner can change a project's estimate.")
        project.estimate_credits = body.estimate_credits
    if body.name is not None:
        project.name = body.name
    db.commit()
    return _out(db, project)


@router.get("/credits/rates", response_model=list[RateOut])
def list_rates(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(CreditRate)
        .where(CreditRate.workspace_id == user.workspace_id)
        .order_by(CreditRate.kind)
    ).all()


@router.put("/credits/rates/{kind}", response_model=RateOut)
def set_rate(
    kind: Annotated[str, Path(pattern=r"^[a-z0-9-]{1,40}$")],
    body: RateIn,
    owner: User = Depends(owner_only),
    db: Session = Depends(get_db),
):
    rate = get_rate(db, owner.workspace_id, kind) or CreditRate(
        workspace_id=owner.workspace_id, kind=kind
    )
    rate.unit, rate.credits_per_unit = body.unit, body.credits_per_unit
    db.add(rate)
    db.commit()
    return rate
