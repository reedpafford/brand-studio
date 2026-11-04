"""The best take of a clip (take check, the director's hand fix): the one to pick, from what
the checks found. It only reads: picking and approving stay the caller's (rule 21)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clip_prompts, item_checks, looks, video_settings
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project

ORDER = {"clean": 0, "checking": 1, "unchecked": 2, "flagged": 3}


def best_take(db: Session, clip: ProjectClip) -> ClipTake | None:
    """The clip's best current take: clean first, then checking, unchecked and flagged (a
    flagged one only when nothing is better, so there's always something to show); among
    flagged ones the fewest open findings (Looks fine doesn't count); then the newest. A take
    in another look, made with other video settings, or from an older sheet, still or prompt
    version isn't current and is never chosen (the picked one stays when a person kept it
    anyway); a clip made for an older breakdown has no best take: its prompt needs rewriting.
    Callers wait while any take is still "checking": the order can change when it ends."""
    project = db.get(Project, clip.project_id)
    newest = db.scalar(select(BreakdownVersion).where(BreakdownVersion.project_id == project.id)
                       .order_by(BreakdownVersion.id.desc()).limit(1))  # fmt: skip
    if clip_prompts.is_stale(db, clip, newest):
        return None
    known = clip_prompts.assets(db, project)

    def older(take: ClipTake) -> bool:
        if take.id == clip.picked_take_id:
            return clip_prompts.take_stale(clip)  # as its card says, Keep anyway included
        return bool(clip_prompts.older_take(db, known, clip, take)
                    or clip_prompts.older_still(db, known, clip, take)
                    or clip_prompts.older_prompt(db, clip, take))  # fmt: skip

    takes = db.scalars(select(ClipTake).where(ClipTake.clip_id == clip.id)).all()
    current = [t for t in takes if t.look == looks.take_look(project, t)
               and not video_settings.made_stale(project, clip, t) and not older(t)]  # fmt: skip
    if not current:
        return None
    ids = [t.id for t in current]
    found = [item_checks.latest(db, target, ids) for target in ("take", "words")]

    def rank(take: ClipTake) -> tuple[int, int, int]:
        checks = [item_checks.shown(db, c.get(take.id)) for c in found]
        open_ = sum(len(c.findings) for c in checks if c)  # Looks fine is already left out
        return ORDER[item_checks.verdict(checks)], open_, -take.number

    return min(current, key=rank)
