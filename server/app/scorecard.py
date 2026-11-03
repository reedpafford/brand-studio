"""Spend you can forecast, and a score per video: for every (format, look) pair, what a finished
second costs in credits, how often takes are made again, and how Reed scored the videos.

A finished video is a Project with `finished_at`. Its credits are everything charged to it, the
director's own turns included (kept apart too). The forecast is shown beside the prices, caps
and rule 34's bound; it changes none of them. Credits only: nothing here is in dollars."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import script_library as lib
from app.credits import credits_used, director_credits
from app.models.checks import ItemCheck
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft

ENOUGH = 3  # finished videos a pair needs before its own rate beats the estimate
KINDS = {"story": "dialogue", "song": "song", "narrated": "narrated"}  # script kind -> format
WORDS = "words"  # the take's words check target (take_words.TARGET)
MUST_SHOW = ("product",)  # item-check finding kinds about the brand's must-show items


def format_of(script: Script) -> str:
    """The script's format. The one place to change when scripts get a `format` of their own."""
    return getattr(script, "format", None) or KINDS.get(script.kind, script.kind)


def pair_of(db: Session, project: Project) -> tuple[str, str] | None:
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    script = db.get(Script, draft.script_id) if draft else None
    return (format_of(script), project.look) if script else None


@dataclass
class Facts:
    pair: tuple[str, str]
    seconds: int
    credits: Decimal
    director: Decimal
    clips: int
    takes: int
    score: int | None


def _cut(db: Session, project: Project) -> FinalVideo | None:
    return db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id)
                     .order_by(FinalVideo.id.desc()).limit(1))  # fmt: skip


def facts(db: Session, project: Project) -> Facts | None:
    """What one finished video cost and how it went; None if it has no format or no seconds."""
    pair = pair_of(db, project)
    if not pair:
        return None
    cut = _cut(db, project)
    clips = select(ProjectClip).where(ProjectClip.project_id == project.id)
    if cut:
        clips = clips.where(ProjectClip.picked_take_id.in_(cut.take_ids))
    else:
        clips = clips.where(ProjectClip.picked_take_id.is_not(None))
    made = list(db.scalars(clips))
    seconds = sum(c.seconds for c in made)
    if not seconds:
        return None
    takes = db.scalar(select(func.count()).select_from(ClipTake)
                      .where(ClipTake.clip_id.in_([c.id for c in made])))  # fmt: skip
    return Facts(pair, seconds, credits_used(db, project), director_credits(db, project),
                 len(made), takes, project.score)  # fmt: skip


def finished(db: Session, workspace_id: int, look: str | None = None) -> list[Facts]:
    query = select(Project).where(Project.workspace_id == workspace_id,
                                  Project.finished_at.is_not(None))  # fmt: skip
    if look:
        query = query.where(Project.look == look)
    return [f for p in db.scalars(query) if (f := facts(db, p))]


def table(db: Session, workspace_id: int) -> list[dict]:
    """One row a (format, look) pair, weighted by seconds: credits per finished second, the
    redo rate (takes made per clip; 1.0 is no redo) and the average of Reed's scores."""
    groups: dict[tuple[str, str], list[Facts]] = {}
    for f in finished(db, workspace_id):
        groups.setdefault(f.pair, []).append(f)
    rows = []
    for (fmt, look), fs in sorted(groups.items()):
        seconds, credits = sum(f.seconds for f in fs), sum(f.credits for f in fs)
        clips, scores = sum(f.clips for f in fs), [f.score for f in fs if f.score]
        rows.append({
            "format": fmt, "look": look, "videos": len(fs), "seconds": seconds,
            "credits": float(credits), "director_credits": float(sum(f.director for f in fs)),
            "credits_per_second": round(float(credits / seconds), 3),
            "redo_rate": round(sum(f.takes for f in fs) / clips, 2) if clips else None,
            "scored": len(scores),
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        })  # fmt: skip
    return rows


def forecast(db: Session, draft: ScriptDraft, project: Project | None = None) -> dict:
    """What making this version will probably cost, in credits, and what that rests on. With
    ENOUGH finished videos of its (format, look): its length x their credits per second, basis
    "N finished videos". Otherwise the price Make already quotes, basis "estimate"."""
    from app.routes.estimate import version_cost

    script = db.get(Script, draft.script_id)
    pair = (format_of(script), project.look if project else script.look)
    seconds = lib.seconds(draft) or int(project.estimate_credits if project else 0)
    same = [f for f in finished(db, script.workspace_id, pair[1]) if f.pair == pair]
    if len(same) >= ENOUGH and seconds:
        rate = sum(f.credits for f in same) / sum(f.seconds for f in same)
        return {"credits": float(round(rate * seconds, 2)), "basis": f"{len(same)} finished videos"}
    return {"credits": float(round(version_cost(db, draft, project), 2)), "basis": "estimate"}


def record_forecast(db: Session, project: Project, draft: ScriptDraft) -> None:
    """At Make: keep the forecast on the video, to set the actual against it later."""
    found = forecast(db, draft, project)
    project.forecast_credits = Decimal(str(found["credits"]))
    project.forecast_basis = found["basis"]


def _clean(db: Session, project: Project, target: str, ids: list[int], kinds=None) -> bool | None:
    """True once a check ran on the picked takes and left no finding (Looks fine dismisses
    one) of the kinds asked for; False if one is left; None if no check ran."""
    rows = db.scalars(select(ItemCheck).where(ItemCheck.project_id == project.id,
                      ItemCheck.target == target, ItemCheck.target_id.in_(ids),
                      ItemCheck.status == "done").order_by(ItemCheck.id)).all()  # fmt: skip
    newest = {r.target_id: r for r in rows}
    if not newest:
        return None
    for r in newest.values():
        gone = {d["index"] for d in r.dismissed or []}
        if any(
            f["kind"] in (kinds or [f["kind"]])
            for i, f in enumerate(r.findings or [])
            if i not in gone
        ):
            return False
    return True


def card(db: Session, project: Project) -> dict:
    """One finished video's scorecard, in credits only. The score and note are the owner's;
    the route drops them for an editor."""
    cut = _cut(db, project)
    takes = list(cut.take_ids) if cut else []
    actual, planned = credits_used(db, project), project.forecast_credits
    return {
        "forecast_credits": float(planned) if planned is not None else None,
        "forecast_basis": project.forecast_basis,
        "actual_credits": float(actual),
        "director_credits": float(director_credits(db, project)),
        "within_forecast": None if planned is None else actual <= planned,
        "words_exact": _clean(db, project, WORDS, takes),
        "must_show_ok": _clean(db, project, "take", takes, MUST_SHOW),
        "score": project.score,
        "note": project.score_note,
    }
