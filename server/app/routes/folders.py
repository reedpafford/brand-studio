"""Projects (flows OR1): a brand's list of projects, making, renaming and deleting one (with
Undo), and filing a script, video or quick clip in one. Rules: app/folders.py."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import folders
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.folders import Folder
from app.routes.brands import get_brand

router = APIRouter(tags=["projects (folders)"])
Name = Field(min_length=1, max_length=120)


class FolderIn(BaseModel):
    name: str = Name


class Items(BaseModel):
    scripts: int
    videos: int
    clips: int


class FolderOut(BaseModel):
    id: int
    brand_id: int
    name: str
    created_by_id: int | None
    items: Items  # as each list shows them ("Its 6 items move to No project")
    can_manage: bool  # rename and delete: whoever made it, or the owner


class DeletedOut(BaseModel):
    moved: int  # items now read as No project; POST …/restore is the Undo


class FileIn(BaseModel):
    kind: Literal["script", "video", "clip"]
    id: int
    folder_id: int | None  # null: No project


class FiledOut(BaseModel):
    folder_id: int | None
    was_folder_id: int | None  # Undo: file it back here


def _out(db: Session, user: User, folder: Folder) -> FolderOut:
    items = folders.counts(db, user, [folder.id])[folder.id]
    mine = user.is_owner or folder.created_by_id == user.id
    return FolderOut(id=folder.id, brand_id=folder.brand_id, name=folder.name,
                     created_by_id=folder.created_by_id, items=Items(**items),
                     can_manage=mine)  # fmt: skip


@router.get("/brands/{brand_id}/folders", response_model=list[FolderOut])
def list_folders(brand_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The brand's projects, by name; "No project" is always there and isn't listed."""
    brand = get_brand(db, user, brand_id)
    rows = list(db.scalars(select(Folder).where(Folder.brand_id == brand.id,
                                                Folder.deleted_at.is_(None))
                           .order_by(func.lower(Folder.name))))  # fmt: skip
    counts = folders.counts(db, user, [f.id for f in rows])
    return [FolderOut(id=f.id, brand_id=f.brand_id, name=f.name, created_by_id=f.created_by_id,
                      items=Items(**counts[f.id]),
                      can_manage=user.is_owner or f.created_by_id == user.id)
            for f in rows]  # fmt: skip


@router.post("/brands/{brand_id}/folders", response_model=FolderOut, status_code=201)
def make_folder(
    brand_id: int, body: FolderIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    brand = get_brand(db, user, brand_id)
    name = folders.check_name(db, brand.id, body.name)
    folder = Folder(workspace_id=user.workspace_id, brand_id=brand.id, name=name,
                    created_by_id=user.id)  # fmt: skip
    db.add(folder)
    db.commit()
    return _out(db, user, folder)


@router.patch("/folders/{folder_id}", response_model=FolderOut)
def rename_folder(
    folder_id: int,
    body: FolderIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    folder = folders.get(db, user, folder_id)
    folders.may_manage(user, folder)
    folder.name = folders.check_name(db, folder.brand_id, body.name, but=folder.id)
    db.commit()
    return _out(db, user, folder)


@router.delete("/folders/{folder_id}", response_model=DeletedOut)
def delete_folder(
    folder_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Its items move to No project; nothing inside is deleted. Undo: POST …/restore."""
    return DeletedOut(moved=folders.delete(db, user, folders.get(db, user, folder_id)))


@router.post("/folders/{folder_id}/restore", response_model=FolderOut)
def restore_folder(
    folder_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    folder = folders.restore(db, user, folders.get(db, user, folder_id, deleted=True))
    return _out(db, user, folder)


@router.post("/folders/file", response_model=FiledOut)
def file_item(body: FileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Project: none ▾ → picked: filed (toast, Undo files it back to was_folder_id)."""
    now, was = folders.file(db, user, body.kind, body.id, body.folder_id)
    return FiledOut(folder_id=now, was_folder_id=was)
