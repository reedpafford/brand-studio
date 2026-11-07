"""Rules for the Script Library: who sees and changes what, and each version's status.

- The owner sees and changes everything. An editor sees published scripts and their own, and
  changes only their own (Reed, 2026-10-25).
- A version's words change only while it is a draft; once approved they never change.
- A published script is final: its versions can't change (duplicate it to change it)."""

import re

from fastapi import HTTPException
from sqlalchemy import delete, event, inspect, or_, select
from sqlalchemy.orm import Session, object_session

from app import guides
from app.models.accounts import User
from app.models.clips import ProjectClip
from app.models.jobs import WAITING, Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft, ScriptDraftText

MAX_SLOT = 2  # the original (0) plus up to two variations
WORDS_PER_SECOND = 4.8


def format_id(script: Script) -> str:
    """The script's format (a guides format id): its own pick, else its kind's."""
    return script.format or guides.KIND.get(script.kind, script.kind)


def pick_format(format_id: str) -> str:
    """The engine (a script's kind) of a format a script may be given: one that is on."""
    found = [f for f in guides.formats() if f["id"] == format_id and f["on"]]
    if not found:
        raise HTTPException(422, "That format isn't available.")
    return found[0]["engine"]


def visible(user: User, script: Script) -> bool:
    return script.workspace_id == user.workspace_id and (
        user.is_owner or script.published or script.created_by_id == user.id
    )


def get_script(db: Session, user: User, script_id: int, archived: bool = False) -> Script:
    """A script the caller may see, or 404. A deleted (archived) one is gone for every route;
    only Restore asks for it with `archived=True`."""
    script = db.get(Script, script_id)
    if not script or not visible(user, script) or script.archived != archived:
        raise HTTPException(404, "No such script.")
    return script


def editable(user: User, script: Script) -> Script:
    """Change it: the author or the owner, and only before it is published."""
    if not (user.is_owner or script.created_by_id == user.id):
        raise HTTPException(403, "Only its author or the owner can change this script.")
    if script.published:
        raise HTTPException(
            409, "This script is published, so it's final. Duplicate it to change it."
        )
    return script


def flavours(db: Session, brand_id: int, picks: dict[str, str]) -> dict[str, str]:
    """A version's default flavours (n03): the picks, checked against the brand, plus each
    product that has one flavour; a product with several and no pick stays Auto."""
    from app.routes.projects import _check_variants, variants

    only = {p: next(iter(v)) for p, v in variants(db, brand_id).items() if len(v) == 1}
    return {**only, **_check_variants(db, brand_id, picks)}


def offered_flavours(db: Session, brand_id: int, draft: ScriptDraft) -> dict[str, str]:
    """A new video's flavours from its version (n03): the defaults the brand still offers; one
    deleted since is dropped, so that product starts on Auto."""
    from app.routes.projects import variants

    offered = variants(db, brand_id)
    return {p: v for p, v in (draft.flavours or {}).items() if v in offered.get(p, set())}


def drafts(db: Session, script: Script) -> list[ScriptDraft]:
    query = select(ScriptDraft).where(ScriptDraft.script_id == script.id)
    return list(db.scalars(query.order_by(ScriptDraft.slot)))


def has_videos(db: Session, script: Script) -> bool:
    """A video was made from one of its versions (released ones too): removing the script
    archives it, and its videos are kept, so it is never purged."""
    ids = select(ScriptDraft.id).where(ScriptDraft.script_id == script.id)
    made = or_(Project.script_draft_id.in_(ids), Project.released_draft_id.in_(ids))
    return db.scalar(select(Project.id).where(made).limit(1)) is not None


def get_draft(db: Session, script: Script, slot: int) -> ScriptDraft:
    found = db.scalar(
        select(ScriptDraft).where(ScriptDraft.script_id == script.id, ScriptDraft.slot == slot)
    )
    if not found:
        raise HTTPException(404, "No such version.")
    return found


def reel_name(breakdown: dict) -> str:
    """An imported reel's name in the library: the first part of its logline."""
    return breakdown.get("logline", "").split(",")[0].strip()[:80] or "Imported reel"


def spoken_seconds(text: str) -> int:
    """A rough length before any breakdown: spoken words at 4.8 a second."""
    said = [ln.split(":", 1)[1] for ln in text.splitlines() if re.match(r"^[A-Z][A-Z .'()-]*:", ln)]
    words = sum(len(s.split()) for s in said) or len(text.split())
    return round(words / WORDS_PER_SECOND)


def seconds(draft: ScriptDraft) -> int:
    """The version's length: its video's breakdown once it has one (LW9: the library said
    "about 11 s" while Breakdown said 22 s), else its own breakdown's, else the owner's target,
    else the larger of the spoken words and the reel it was made from (a montage-heavy reel
    says little: 62 s and 66 shots read as 32 s from its words alone). With several videos
    of the version, none of theirs: they may differ."""
    videos = object_session(draft).scalars(select(Project.breakdown_seconds).where(
        Project.script_draft_id == draft.id, Project.archived_at.is_(None))).all()  # fmt: skip
    if len(videos) == 1 and videos[0]:
        return videos[0]
    if draft.breakdown:
        return sum(c["seconds"] for c in draft.breakdown.get("clips", []))
    return draft.target_seconds or max(spoken_seconds(draft.text), reel_seconds(draft))


def reel_seconds(draft: ScriptDraft) -> int:
    """How long the script's reel is: the imported reel's, else the catalogue reference's."""
    from app.routes.references import catalogue
    from app.settings import get_settings

    script = object_session(draft).get(Script, draft.script_id)
    imported = (script.reference_breakdown or {}).get("duration_seconds") if script else None
    if imported or not (script and script.reference_id):
        return round(imported or 0)
    found = catalogue(get_settings().references_dir).get(script.reference_id)
    return round(found[0].seconds) if found else 0


def version_status(db: Session, draft: ScriptDraft) -> tuple[str, int | None]:
    """draft | approved | in_production | clips_ready | failed | done, and its project."""
    project = db.scalar(select(Project).where(Project.script_draft_id == draft.id))
    if not project:
        return draft.status, None
    if project.finished_at:  # a final video, or the picked takes downloaded
        return "done", project.id
    last = db.scalar(
        select(Job.status).where(Job.project_id == project.id).order_by(Job.id.desc()).limit(1)
    )
    if last == JobStatus.failed:  # "Didn't finish": its last job failed, nothing is running
        return "failed", project.id
    clips = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)).all()
    ready = bool(clips) and all(c.approved for c in clips)
    return ("clips_ready" if ready else "in_production"), project.id


def script_status(script: Script, statuses: list[str]) -> str:
    """draft (not published) | published | in_production | done (every approved version)."""
    if not script.published:
        return "draft"
    made = [s for s in statuses if s in ("in_production", "clips_ready", "failed", "done")]
    approved = [s for s in statuses if s != "draft"]
    if approved and all(s == "done" for s in approved):
        return "done"
    return "in_production" if made else "published"


def writing(db: Session, script_id: int, step: str | None = None) -> bool:
    """A Claude step (variations, cast slots) is still writing into this script."""
    jobs = db.scalars(select(Job).where(Job.status.in_(WAITING), Job.kind == "write-claude"))
    return any(
        j.input.get("script_id") == script_id and (step is None or j.input.get("step") == step)
        for j in jobs
    )


def own_jobs(db: Session, script: Script) -> list[Job]:
    """The script's own work still waiting or running, whoever started it: its words, reel
    read, variations, Directions, plan, cast read and its own looks' sheets. Never its videos'
    jobs, which are theirs."""
    looks = set(db.scalars(select(LibraryItem.id).where(LibraryItem.owner_script_id == script.id)))
    waiting = db.scalars(
        select(Job).where(
            Job.workspace_id == script.workspace_id,
            Job.project_id.is_(None),
            Job.status.in_(WAITING),
        )
    )
    return [
        j
        for j in waiting
        if j.input.get("script_id") == script.id or j.input.get("library_item_id") in looks
    ]


HISTORY = 20  # earlier texts kept per version (Producer, 2026-10-25)


def house(script: Script, text: str) -> str:
    """A person's words as the script keeps them: a screenplay's speakers in the house's
    "MAYA: …" form (check.screenplay), so its cast, its speakers and its spoken words are read
    as any script's. A song's lyrics or a narration as they are ("CHORUS" is no one)."""
    from app.models.brands import Brand
    from app.narration import TIMED
    from app.prompts import check

    if script.kind in TIMED:
        return text
    brand = object_session(script).get(Brand, script.brand_id) if script.brand_id else None
    return check.screenplay(text, brand.name if brand else "")


def keep_text(db: Session, draft: ScriptDraft, new_text: str, source: str, user_id=None) -> None:
    """Keep a version's current words before they're replaced, for its history: the newest
    HISTORY texts, the oldest dropped."""
    if not (draft.id and draft.text.strip() and draft.text != new_text):
        return
    db.add(
        ScriptDraftText(
            draft_id=draft.id, text=draft.text, title=draft.title, source=source,
            created_by_id=user_id,
        )
    )  # fmt: skip
    db.flush()
    old = db.scalars(
        select(ScriptDraftText.id)
        .where(ScriptDraftText.draft_id == draft.id)
        .order_by(ScriptDraftText.id.desc())
        .offset(HISTORY)
    ).all()
    if old:
        db.execute(delete(ScriptDraftText).where(ScriptDraftText.id.in_(old)))


def poster(db: Session, script: Script) -> int | None:
    """The first still of the newest finished video made from the script, for the library."""
    from app.models.storyboards import StoryboardFrame

    drafts = select(ScriptDraft.id).where(ScriptDraft.script_id == script.id)
    project = db.scalar(
        select(Project.id)
        .where(Project.script_draft_id.in_(drafts), Project.finished_at.is_not(None))
        .order_by(Project.finished_at.desc())
        .limit(1)
    )
    if project is None:
        return None
    return db.scalar(
        select(StoryboardFrame.file_id)
        .where(StoryboardFrame.project_id == project, StoryboardFrame.file_id.is_not(None))
        .order_by(StoryboardFrame.id)
        .limit(1)
    )


AWAITING_VIDEO = "This version is waiting for the owner's OK to make a video. Withdraw it to edit."
FROZEN_BY = {  # what making that video may change on it (freestyles.freeze, make_video, release)
    ScriptDraft: {"status", "approved_at", "approved_by_id", "reserved_by_id"},
    Script: {"published", "hidden"},
}


@event.listens_for(Session, "before_flush")
def _awaiting_video(session: Session, _ctx, _instances) -> None:
    """Rule 31 (QA-10 on #1190): while a director-first video an editor asked for from a
    version waits for the owner's OK, nothing that video is made from changes (its words,
    breakdown, flavours, plan, the script's look and cast), whichever route writes it: one
    check at flush, so no route can miss it."""
    drafts: set[int] = set()
    scripts: set[int] = set()
    for row in (*session.new, *session.dirty, *session.deleted):
        if isinstance(row, ScriptDraft) and row.id and _changed(row) - FROZEN_BY[ScriptDraft]:
            drafts.add(row.id)  # a new version beside it is fine: this one stays as sent
        elif isinstance(row, Script) and row.id and _changed(row) - FROZEN_BY[Script]:
            scripts.add(row.id)
        elif isinstance(row, ScriptCastSlot):
            scripts.add(row.script_id)
    if not drafts and not scripts:
        return
    with session.no_autoflush:
        if scripts:
            drafts |= set(session.scalars(select(ScriptDraft.id).where(
                ScriptDraft.script_id.in_(scripts))))  # fmt: skip
        held = session.scalar(select(Job.id).where(
            Job.status == JobStatus.needs_owner_approval,
            Job.input["freeze"]["draft"].as_integer().in_(drafts)).limit(1))  # fmt: skip
    if held:
        raise HTTPException(409, AWAITING_VIDEO)


def _changed(row) -> set[str]:
    state = inspect(row)
    if state.pending or state.deleted or row in (object_session(row) or ()).deleted:
        return {"*"}
    return {a.key for a in state.attrs if a.history.has_changes()}
