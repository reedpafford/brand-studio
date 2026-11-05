"""Folders (flows OR1, v6 S0-01, S1): a brand's folder tree with its ideas' status dots, one
folder's ideas (tabs, search, sort, Made by, pages, archived), making a folder (inside
another, or at the top), renaming and moving one, deleting one (its ideas move to Unsorted,
Undo brings them back), and filing ideas, scripts or quick clips in one. Rules:
app/folders.py; the ideas' words: app/ideas.py."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import folders, ideas
from app.auth import current_user
from app.db import get_db
from app.models.accounts import User
from app.models.folders import Folder
from app.models.projects import Project
from app.routes.brands import get_brand

router = APIRouter(tags=["folders"])
Name = Field(min_length=1, max_length=120)
SHOWN = 5  # ideas under an open folder in the tree, then "+ N more" (S0-01)
ALL = "all"  # ?folder=all: every idea in the brand


class FolderIn(BaseModel):
    name: str = Name
    parent_id: int | None = None  # inside this folder; null: at the top


class FolderPatch(BaseModel):
    """Send what changes: a new name, and/or a new place (`parent_id` null: to the top)."""

    name: str | None = Field(None, min_length=1, max_length=120)
    parent_id: int | None = None


class Items(BaseModel):
    scripts: int
    videos: int
    clips: int


class FolderOut(BaseModel):
    id: int
    brand_id: int
    parent_id: int | None
    name: str
    created_by_id: int | None
    items: Items  # its own, as each list shows them
    can_manage: bool  # rename, move and delete: whoever made it, or the owner


class DeletedOut(BaseModel):
    moved: int  # items (with the folders inside) now in Unsorted; POST …/restore is the Undo
    ideas: int  # "Its 3 ideas moved to Unsorted."


class FileIn(BaseModel):
    kind: Literal["script", "video", "clip"]
    ids: list[int] = Field(min_length=1, max_length=500)
    folder_id: int | None  # null: Unsorted


class Was(BaseModel):
    id: int
    folder_id: int | None


class FiledOut(BaseModel):
    folder_id: int | None
    was: list[Was]  # Undo: file each back where it was


class Dot(BaseModel):
    id: int
    title: str
    status: ideas.Status  # the tree shows the dot; the words are on hover
    can_manage: bool = False  # it can be dragged to another folder: whoever made it, or the owner


class Branch(BaseModel):
    """A folder in the tree: its ideas at any depth (`count`), its newest own ideas, and the
    folders inside it. Unsorted has no id."""

    id: int | None
    parent_id: int | None = None
    name: str
    count: int
    can_manage: bool = False
    ideas: list[Dot]
    more: int  # its own ideas past those shown: "+ 5 more"
    folders: list["Branch"] = []


class TreeOut(BaseModel):
    folders: list[Branch]  # at the top, in the order made
    unsorted: Branch


class Counts(BaseModel):
    all: int
    needs_you: int
    working: int
    delivered: int


class IdeasOut(BaseModel):
    total: int  # in this tab, for the pages ("Showing 1–13 of 124")
    counts: (
        Counts  # the tabs and the header: the whole folder (the search and Made by narrow `total`)
    )
    archived: int  # this folder's archived ideas
    folders_inside: int  # "124 video ideas · 2 folders inside"
    makers: list[ideas.Named]  # the Made by filter's people
    ideas: list[ideas.Idea]


def _out(db: Session, user: User, folder: Folder, items: dict | None = None) -> FolderOut:
    items = items or folders.counts(db, user, [folder.id])[folder.id]
    return FolderOut(id=folder.id, brand_id=folder.brand_id, parent_id=folder.parent_id,
                     name=folder.name, created_by_id=folder.created_by_id, items=Items(**items),
                     can_manage=user.is_owner or folder.created_by_id == user.id)  # fmt: skip


@router.get("/brands/{brand_id}/folders", response_model=list[FolderOut])
def list_folders(brand_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The brand's folders in the order made, each with its `parent_id`; Unsorted isn't listed."""
    rows = folders.live(db, get_brand(db, user, brand_id).id)
    counts = folders.counts(db, user, [f.id for f in rows])
    return [_out(db, user, f, counts[f.id]) for f in rows]


def _live_ideas(db: Session, brand_id: int, archived: bool = False):
    done = Project.archived_at.is_not(None) if archived else Project.archived_at.is_(None)
    return select(Project).where(Project.brand_id == brand_id, done)


@router.get("/brands/{brand_id}/tree", response_model=TreeOut)
def tree(brand_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The rail's tree (S0-01, P-01): folders inside folders with their ideas counted at any
    depth, each folder's newest own ideas with their status, and Unsorted."""
    brand = get_brand(db, user, brand_id)
    rows = folders.live(db, brand.id)
    every = list(db.scalars(_live_ideas(db, brand.id)))
    known = ideas.facts(db, every)
    newest = sorted(every, key=lambda p: (known.last[p.id], p.id), reverse=True)
    live = {f.id for f in rows}
    own: dict[int | None, list[Project]] = {}
    for p in newest:
        own.setdefault(p.folder_id if p.folder_id in live else None, []).append(p)
    shown = [p for ps in own.values() for p in ps[:SHOWN]]
    status = ideas.statuses(db, user, shown, known)
    named = ideas.titles(db, [p.id for p in shown])

    def dots(ps: list[Project]) -> list[Dot]:
        return [Dot(id=p.id, title=named.get(p.id, p.name), status=status[p.id],
                    can_manage=user.is_owner or p.created_by_id == user.id)
                for p in ps[:SHOWN]]  # fmt: skip

    def branch(f: Folder) -> Branch:
        inside = [branch(c) for c in rows if c.parent_id == f.id]
        mine = own.get(f.id, [])
        return Branch(id=f.id, parent_id=f.parent_id, name=f.name, ideas=dots(mine),
                      count=len(mine) + sum(b.count for b in inside),
                      more=max(0, len(mine) - SHOWN), folders=inside,
                      can_manage=user.is_owner or f.created_by_id == user.id)  # fmt: skip

    loose = own.get(None, [])
    return TreeOut(folders=[branch(f) for f in rows if f.parent_id not in live],
                   unsorted=Branch(id=None, name="Unsorted", count=len(loose), ideas=dots(loose),
                                   more=max(0, len(loose) - SHOWN)))  # fmt: skip


@router.get("/brands/{brand_id}/ideas", response_model=IdeasOut)
def folder_ideas(
    brand_id: int,
    folder: str = folders.NONE,  # a folder (and the folders inside), none: Unsorted, all: the brand
    tab: ideas.Tab = "all",
    q: str = "",  # in the idea's title
    made_by: int | None = None,  # a person's id: "Made by"
    sort: ideas.Sort = "newest",
    archived: bool = False,  # this folder's archived ideas instead (S1-06)
    offset: int = Query(0, ge=0),
    limit: int = Query(60, ge=1, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """One folder's ideas as cards or list rows (S1-04 to S1-08, P-02), a page at a time."""
    brand = get_brand(db, user, brand_id)
    whole = folder == ALL  # the rail's quick search (S-gaps-04 R2)
    if folder not in (folders.NONE, ALL):
        try:
            opened = folders.get(db, user, int(folder))
        except ValueError:
            raise HTTPException(404, folders.NO_FOLDER) from None
        if opened.brand_id != brand.id:  # brands stay apart
            raise HTTPException(404, folders.NO_FOLDER)
    filed = Project.id.is_not(None) if whole else folders.where(Project.folder_id, folder)
    gone = db.scalar(select(func.count()).select_from(
        _live_ideas(db, brand.id, True).where(filed).subquery()))  # fmt: skip
    every = list(db.scalars(_live_ideas(db, brand.id).where(filed)))
    makers = {p.created_by_id for p in every if p.created_by_id}
    named = ideas.titles(db, [p.id for p in every])
    title = {p.id: named.get(p.id, p.name) for p in every}
    found = [p for p in every if q.strip().lower() in title[p.id].lower()]
    if made_by is not None:
        found = [p for p in found if p.created_by_id == made_by]
    known = ideas.facts(db, every)
    status = ideas.statuses(db, user, every, known)
    # The tabs and the header count the whole folder; the search and Made by narrow the rows.
    in_tab = {t: [p for p in every if status[p.id].kind in kinds]
              for t, kinds in ideas.TABS.items()}  # fmt: skip
    shown = {p.id for p in found}
    rows = [p for p in (every if tab == "all" else in_tab[tab]) if p.id in shown]
    if archived:  # S1-06: the folder's archived ideas; the tabs and the header keep its live ones
        rows = list(db.scalars(_live_ideas(db, brand.id, True).where(filed)))
        named = ideas.titles(db, [p.id for p in rows])
        title.update({p.id: named.get(p.id, p.name) for p in rows})
        rows = [p for p in rows if q.strip().lower() in title[p.id].lower()]
        known = ideas.facts(db, rows)
        status = ideas.statuses(db, user, rows, known)
    order = {"newest": lambda p: (-known.last[p.id].timestamp(), -p.id),
             "oldest": lambda p: (known.last[p.id].timestamp(), p.id),
             "name": lambda p: (title[p.id].lower(), p.id)}  # fmt: skip
    rows = sorted(rows, key=order[sort])
    page = rows[offset : offset + limit]
    inside = 0
    if folder not in (folders.NONE, ALL):
        inside = len(folders.below(folders.live(db, brand.id), int(folder))) - 1
    from app.auth import user_name

    return IdeasOut(
        total=len(rows),
        counts=Counts(all=len(every), **{t: len(ps) for t, ps in in_tab.items()}),
        archived=gone, folders_inside=inside,
        makers=sorted((ideas.Named(id=i, name=user_name(db, i)) for i in makers),
                      key=lambda m: m.name.lower()),
        ideas=ideas.cards(db, user, page, known, status),
    )  # fmt: skip


@router.get("/projects/{project_id}/idea", response_model=ideas.Head)
def idea_head(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """One idea's header on its video page (S3, P-04): status with its reason, used, up to,
    budget, its folder, format, style and length. Read-only and free."""
    from app.routes.projects import get_project

    return ideas.head(db, user, get_project(db, user, project_id))


@router.post("/brands/{brand_id}/folders", response_model=FolderOut, status_code=201)
def make_folder(
    brand_id: int, body: FolderIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """New folder, at the top or inside one ("New folder inside")."""
    brand = get_brand(db, user, brand_id)
    folder = Folder(workspace_id=user.workspace_id, brand_id=brand.id, created_by_id=user.id)
    folders.place(db, user, folder, body.parent_id)
    folder.name = folders.check_name(db, folder, body.name)
    db.add(folder)
    db.commit()
    return _out(db, user, folder)


@router.patch("/folders/{folder_id}", response_model=FolderOut)
def change_folder(
    folder_id: int,
    body: FolderPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Rename it, or move it ("Move to…", or dragged): inside another folder of its brand, or
    to the top; never inside itself or a folder inside it."""
    folder = folders.get(db, user, folder_id)
    folders.may_manage(user, folder)
    if "parent_id" in body.model_fields_set:
        folders.place(db, user, folder, body.parent_id)
    folder.name = folders.check_name(db, folder, body.name or folder.name)
    db.commit()
    return _out(db, user, folder)


@router.delete("/folders/{folder_id}", response_model=DeletedOut)
def delete_folder(
    folder_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """It goes with the folders inside it; their ideas move to Unsorted and nothing inside is
    deleted. Undo: POST …/restore."""
    moved, count = folders.delete(db, user, folders.get(db, user, folder_id))
    return DeletedOut(moved=moved, ideas=count)


@router.post("/folders/{folder_id}/restore", response_model=FolderOut)
def restore_folder(
    folder_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    folder = folders.restore(db, user, folders.get(db, user, folder_id, deleted=True))
    return _out(db, user, folder)


@router.post("/folders/file", response_model=FiledOut)
def file_items(body: FileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Move one or many ideas (or scripts, or quick clips) into a folder, or Unsorted: a drag
    onto the tree, "Move to…", or several selected. Undo files each back where it was."""
    was = folders.file(db, user, body.kind, body.ids, body.folder_id)
    return FiledOut(folder_id=body.folder_id,
                    was=[Was(id=i, folder_id=f) for i, f in was.items()])  # fmt: skip
