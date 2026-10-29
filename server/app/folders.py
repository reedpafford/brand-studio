"""Projects (flows OR1): the rules for a brand's folders and what's filed in them. A script,
a video or a quick clip (a job with no video) can be filed in one project of its own brand.
Editors make projects and file their own items, also into someone else's project; only the
owner renames or deletes a project someone else made, and the owner files anything. A
deleted project is kept for Undo; its items read as No project until it's back."""

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.accounts import User
from app.models.folders import Folder
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import Script

KINDS = {"script": Script, "video": Project, "clip": Job}
NONE = "none"  # ?folder=none: No project
TAKEN = "A project called {} already exists. Rename one first."
NO_FOLDER = "No such project."
NO_ITEM = "No such {} to file."
NOT_YOURS = "Only whoever made it, or the owner, can do that."
OTHER_BRAND = "That project is for another brand."
PICK = "Pick a project, or No project."
VIDEO_JOB = "That's part of a video, so it's filed with the video."


def get(db: Session, user: User, folder_id: int, deleted: bool = False) -> Folder:
    folder = db.get(Folder, folder_id)
    if folder is None or folder.workspace_id != user.workspace_id:
        raise HTTPException(404, NO_FOLDER)
    if (folder.deleted_at is not None) != deleted:
        raise HTTPException(404, NO_FOLDER)
    return folder


def check_name(db: Session, brand_id: int, name: str, but: int | None = None) -> str:
    """A live project's name is its brand's only one (in code: a deleted one never blocks)."""
    name = name.strip()
    same = select(Folder.id).where(Folder.brand_id == brand_id, Folder.deleted_at.is_(None),
                                   func.lower(Folder.name) == name.lower())  # fmt: skip
    if any(i != but for i in db.scalars(same)):
        raise HTTPException(409, TAKEN.format(name))
    return name


def may_manage(user: User, folder: Folder) -> None:
    """Rename or delete: whoever made it, or the owner."""
    if not (user.is_owner or folder.created_by_id == user.id):
        raise HTTPException(403, NOT_YOURS)


def item(db: Session, user: User, kind: str, item_id: int):
    """A script, video or quick clip the caller may file (theirs, or anything for the owner)."""
    found = db.get(KINDS[kind], item_id)
    if found is None or found.workspace_id != user.workspace_id:
        raise HTTPException(404, NO_ITEM.format(kind))
    if kind == "clip" and found.project_id is not None:
        raise HTTPException(409, VIDEO_JOB)  # a video's own jobs are never clips in a project
    if not (user.is_owner or found.created_by_id == user.id):
        raise HTTPException(403, NOT_YOURS)
    return found


def file(db: Session, user: User, kind: str, item_id: int, folder_id: int | None) -> tuple:
    """(now, was): filed in `folder_id`, or No project; Undo files it back to `was`."""
    found = item(db, user, kind, item_id)
    if folder_id is not None:
        folder = get(db, user, folder_id)
        if folder.brand_id != found.brand_id:
            raise HTTPException(409, OTHER_BRAND)
    was = found.live_folder_id
    found.folder_id = folder_id
    db.commit()
    return folder_id, was


def delete(db: Session, user: User, folder: Folder) -> int:
    """Soft: its items read as No project (nothing inside is touched); restore is Undo."""
    may_manage(user, folder)
    moved = sum(counts(db, user, [folder.id]).get(folder.id, {}).values())
    folder.deleted_at = utcnow()
    db.commit()
    return moved


def restore(db: Session, user: User, folder: Folder) -> Folder:
    may_manage(user, folder)
    check_name(db, folder.brand_id, folder.name)
    folder.deleted_at = None
    db.commit()
    return folder


def where(column, folder: str | None):
    """The list filter for ?folder=: one project's, or No project (none, or a deleted one)."""
    if folder is None:
        return None
    if folder == NONE:
        gone = select(Folder.id).where(Folder.deleted_at.is_not(None))
        return or_(column.is_(None), column.in_(gone))
    try:
        return column == int(folder)
    except ValueError:
        raise HTTPException(422, PICK) from None


def _scripts(user: User):
    """The scripts the caller's Scripts list shows (live; an editor's: published or theirs)."""
    query = select(Script.folder_id, func.count()).where(~Script.archived)
    if not user.is_owner:
        query = query.where(or_(Script.published, Script.created_by_id == user.id))
    return query


def _videos(user: User):
    """The videos the caller's Videos list shows (live; an editor's: only theirs)."""
    query = select(Project.folder_id, func.count()).where(Project.archived_at.is_(None))
    if not user.is_owner:
        query = query.where(Project.created_by_id == user.id)
    return query


def counts(db: Session, user: User, folder_ids: list[int]) -> dict[int, dict[str, int]]:
    """Each project's items as its lists show them: live scripts, videos and quick clips."""
    out = {i: {"scripts": 0, "videos": 0, "clips": 0} for i in folder_ids}
    queries = {
        "scripts": _scripts(user).where(Script.folder_id.in_(folder_ids))
        .group_by(Script.folder_id),
        "videos": _videos(user).where(Project.folder_id.in_(folder_ids))
        .group_by(Project.folder_id),
        "clips": select(Job.folder_id, func.count()).where(
            Job.folder_id.in_(folder_ids), Job.project_id.is_(None), Job.removed_at.is_(None)
        ).group_by(Job.folder_id),
    }  # fmt: skip
    for kind, query in queries.items():
        for folder_id, n in db.execute(query):
            out[folder_id][kind] = n
    return out
