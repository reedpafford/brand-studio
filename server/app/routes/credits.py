"""Credit rates per job kind, owner-set limits, and each person's quick-clip allowance."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user, owner_only
from app.credits import get_limits, get_rate, quick_clip_used
from app.db import get_db
from app.models.accounts import User
from app.models.credits import CreditLimits, CreditRate
from app.schemas import Name

router = APIRouter(prefix="/credits", tags=["credits"])


class RateIn(BaseModel):
    unit: Name
    credits_per_unit: Decimal = Field(gt=0, le=10000)


class RateOut(BaseModel):
    kind: str
    unit: str
    credits_per_unit: float


class LimitsIn(BaseModel):
    max_planned_seconds: int = Field(gt=0, le=3600)
    weekly_quick_clip_credits: Decimal = Field(ge=0, le=100000)
    per_video_max_credits: int = Field(340, gt=0, le=100000)


class LimitsOut(BaseModel):
    max_planned_seconds: int
    weekly_quick_clip_credits: float
    per_video_max_credits: int


class AllowanceOut(BaseModel):
    quick_clip_credits_used: float
    quick_clip_credits_allowed: float


@router.get("/rates", response_model=list[RateOut])
def list_rates(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(CreditRate)
        .where(CreditRate.workspace_id == user.workspace_id)
        .order_by(CreditRate.kind)
    ).all()


@router.put("/rates/{kind}", response_model=RateOut)
def set_rate(
    kind: Annotated[str, Path(pattern=r"^[a-z0-9.-]{1,40}$")],
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


@router.get("/limits", response_model=LimitsOut)
def read_limits(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return get_limits(db, user.workspace_id)


@router.put("/limits", response_model=LimitsOut)
def set_limits(body: LimitsIn, owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    limits = db.scalar(
        select(CreditLimits).where(CreditLimits.workspace_id == owner.workspace_id)
    ) or CreditLimits(workspace_id=owner.workspace_id)
    for field, value in body.model_dump().items():
        setattr(limits, field, value)
    db.add(limits)
    db.commit()
    return limits


@router.get("/me", response_model=AllowanceOut)
def my_allowance(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """This week's quick-clip credits used and allowed for the caller."""
    return AllowanceOut(
        quick_clip_credits_used=quick_clip_used(db, user),
        quick_clip_credits_allowed=get_limits(db, user.workspace_id).weekly_quick_clip_credits,
    )
