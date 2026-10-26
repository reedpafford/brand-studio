"""The studio's name (Team, Reed only): shown on invite links ("Join Reed's studio")."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import current_user, owner_only
from app.db import get_db
from app.models.accounts import User, Workspace
from app.schemas import Name

router = APIRouter(prefix="/workspace", tags=["team"])


class WorkspaceIn(BaseModel):
    name: Name


class WorkspaceOut(BaseModel):
    id: int
    name: str


@router.get("", response_model=WorkspaceOut)
def read_workspace(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.get(Workspace, user.workspace_id)


@router.put("", response_model=WorkspaceOut)
def rename_workspace(
    body: WorkspaceIn, owner: User = Depends(owner_only), db: Session = Depends(get_db)
):
    workspace = db.get(Workspace, owner.workspace_id)
    workspace.name = body.name.strip()
    db.commit()
    return workspace
