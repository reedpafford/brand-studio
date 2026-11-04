"""Folders (flows OR1, v6 S0-01): the rules for a brand's free folders and what's filed in
them. A folder can sit inside another of its brand. A video idea, a script or a quick clip (a
job with no video) can be filed in one folder of its own brand. Editors make folders and file
their own items, also into someone else's folder; only the owner renames, moves or deletes a
folder someone else made, and the owner files anything. A deleted folder is kept for Undo,
with the folders inside it; their items read as Unsorted until it's back."""

from datetime import datetime

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
NONE = "none"  # ?folder=none: Unsorted
TAKEN = "A folder called {} is already there. Rename one first."
NO_FOLDER = "No such folder."
NO_ITEM = "No such {} to file."
NOT_YOURS = "Only whoever made it, or the owner, can do that."
OTHER_BRAND = "That folder is for another brand."
PICK = "Pick a folder, or Unsorted."
VIDEO_JOB = "That's part of a video, so it's filed with the video."
INSIDE_ITSELF = "A folder can't go inside itself or a folder inside it."


def get(db: Session, user: User, folder_id: int, deleted: bool = False) -> Folder:
    folder = db.get(Folder, folder_id)
    if folder is None or folder.workspace_id != user.workspace_id:
        raise HTTPException(404, NO_FOLDER)
    if (folder.deleted_at is not None) != deleted:
        raise HTTPException(404, NO_FOLDER)
    return folder


def live(db: Session, brand_id: int) -> list[Folder]:
    """The brand's folders, by name (a folder inside a deleted one is deleted with it)."""
    return list(db.scalars(select(Folder).where(Folder.brand_id == brand_id,
                                                Folder.deleted_at.is_(None))
                           .order_by(func.lower(Folder.name), Folder.id)))  # fmt: skip


def below(rows: list[Folder], folder_id: int) -> set[int]:
    """The folder's id and every folder inside it, at any depth, from `rows`."""
    out, todo = {folder_id}, [folder_id]
    while todo:
        parent = todo.pop()
        for f in rows:
            if f.parent_id == parent and f.id not in out:
                out.add(f.id)
                todo.append(f.id)
    return out


def check_name(db: Session, folder: Folder, name: str) -> str:
    """A live folder's name is the only one among the folders beside it (in code: a deleted
    one never blocks)."""
    name = name.strip()
    same = select(Folder.id).where(Folder.brand_id == folder.brand_id,
                                   Folder.parent_id.is_(None) if folder.parent_id is None
                                   else Folder.parent_id == folder.parent_id,
                                   Folder.deleted_at.is_(None),
                                   func.lower(Folder.name) == name.lower())  # fmt: skip
    if any(i != folder.id for i in db.scalars(same)):
        raise HTTPException(409, TAKEN.format(name))
    return name


def may_manage(user: User, folder: Folder) -> None:
    """Rename, move or delete: whoever made it, or the owner."""
    if not (user.is_owner or folder.created_by_id == user.id):
        raise HTTPException(403, NOT_YOURS)


def place(db: Session, user: User, folder: Folder, parent_id: int | None) -> None:
    """Put the folder inside `parent_id` (None: at the top), in its own brand, never inside
    itself or a folder inside it."""
    if parent_id is not None:
        parent = get(db, user, parent_id)
        if parent.brand_id != folder.brand_id:
            raise HTTPException(409, OTHER_BRAND)
        if folder.id is not None and parent.id in below(live(db, folder.brand_id), folder.id):
            raise HTTPException(409, INSIDE_ITSELF)
    folder.parent_id = parent_id


def item(db: Session, user: User, kind: str, item_id: int):
    """A script, video or quick clip the caller may file (theirs, or anything for the owner)."""
    found = db.get(KINDS[kind], item_id)
    if found is None or found.workspace_id != user.workspace_id:
        raise HTTPException(404, NO_ITEM.format(kind))
    if kind == "clip" and found.project_id is not None:
        raise HTTPException(409, VIDEO_JOB)  # a video's own jobs are never clips in a folder
    if not (user.is_owner or found.created_by_id == user.id):
        raise HTTPException(403, NOT_YOURS)
    return found


def file(db: Session, user: User, kind: str, ids: list[int], folder_id: int | None) -> dict:
    """Each item filed in `folder_id`, or Unsorted, all or none: {id: where it was}, so Undo
    files each back."""
    found = [item(db, user, kind, i) for i in dict.fromkeys(ids)]
    if folder_id is not None:
        folder = get(db, user, folder_id)
        if any(f.brand_id != folder.brand_id for f in found):
            raise HTTPException(409, OTHER_BRAND)
    was = {f.id: f.live_folder_id for f in found}
    for f in found:
        f.folder_id = folder_id
    db.commit()
    return was


def delete(db: Session, user: User, folder: Folder) -> tuple[int, int]:
    """Soft, with every folder inside it (one time, so Undo brings back just those): their
    items read as Unsorted (nothing inside is touched). (items, video ideas) moved."""
    may_manage(user, folder)
    ids = below(live(db, folder.brand_id), folder.id)
    found = counts(db, user, list(ids))
    ideas = db.scalar(select(func.count()).where(Project.folder_id.in_(ids),
                                                 Project.archived_at.is_(None)))  # fmt: skip
    now = utcnow()
    for f in db.scalars(select(Folder).where(Folder.id.in_(ids))):
        f.deleted_at = now
    db.commit()
    return sum(sum(c.values()) for c in found.values()), ideas


def restore(db: Session, user: User, folder: Folder) -> Folder:
    """Undo a delete: the folder and the folders deleted with it. One whose parent was deleted
    on its own since comes back at the top."""
    may_manage(user, folder)
    when: datetime = folder.deleted_at
    same = list(db.scalars(select(Folder).where(Folder.brand_id == folder.brand_id,
                                                Folder.deleted_at == when)))  # fmt: skip
    back = below(same, folder.id)
    parent = db.get(Folder, folder.parent_id) if folder.parent_id else None
    if parent is not None and parent.deleted_at is not None:
        folder.parent_id = None
    check_name(db, folder, folder.name)
    for f in same:
        if f.id in back:
            f.deleted_at = None
    db.commit()
    return folder


def _inside(folder_id: int):
    """The folder's id and every live folder inside it, as SQL."""
    tree = select(Folder.id).where(Folder.id == folder_id).cte("tree", recursive=True)
    tree = tree.union_all(select(Folder.id).where(Folder.parent_id == tree.c.id,
                                                  Folder.deleted_at.is_(None)))  # fmt: skip
    return select(tree.c.id)


def where(column, folder: str | None):
    """The list filter for ?folder=: a folder's, with the folders inside it, or Unsorted
    (none, or a deleted one)."""
    if folder is None:
        return None
    if folder == NONE:
        gone = select(Folder.id).where(Folder.deleted_at.is_not(None))
        return or_(column.is_(None), column.in_(gone))
    try:
        return column.in_(_inside(int(folder)))
    except ValueError:
        raise HTTPException(422, PICK) from None


def _scripts(user: User):
    """The scripts the caller's Scripts list shows (live; an editor's: published or theirs)."""
    query = select(Script.folder_id, func.count()).where(~Script.archived)
    if not user.is_owner:
        query = query.where(or_(Script.published, Script.created_by_id == user.id))
    return query


def counts(db: Session, user: User, folder_ids: list[int]) -> dict[int, dict[str, int]]:
    """Each folder's own items as their lists show them: live scripts, video ideas (everyone's,
    as the folder shows them, S1-08) and quick clips."""
    out = {i: {"scripts": 0, "videos": 0, "clips": 0} for i in folder_ids}
    queries = {
        "scripts": _scripts(user).where(Script.folder_id.in_(folder_ids))
        .group_by(Script.folder_id),
        "videos": select(Project.folder_id, func.count()).where(
            Project.folder_id.in_(folder_ids), Project.archived_at.is_(None)
        ).group_by(Project.folder_id),
        "clips": select(Job.folder_id, func.count()).where(
            Job.folder_id.in_(folder_ids), Job.project_id.is_(None), Job.removed_at.is_(None)
        ).group_by(Job.folder_id),
    }  # fmt: skip
    for kind, query in queries.items():
        for folder_id, n in db.execute(query):
            out[folder_id][kind] = n
    return out
