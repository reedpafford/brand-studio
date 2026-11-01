"""The director's tools (docs/next/director-chat.md §6 item 3): each is a site action, run
through the very function its button calls, as the director's user, on this video only. So
every check stays the button's: price, the video's budget (past it: held for the owner,
Hold requests), the per-video cap, rule 32, ownership. Nothing here spends another way, and no
tool can change Limits or another person's work. A refusal comes back as its plain words.
The approvals a person gives on the step screens are the director's own here: it approves a
step when it moves on from it (rule 21's self-approval)."""

from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.clips import ProjectClip
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame

TOOLS = ("plan", "make_looks", "storyboard", "stills", "clip_prompts", "make_take",
         "pick_take", "final_cut")  # fmt: skip


def run(db: Session, user: User, project: Project, decision: dict, storage) -> str:
    """Do one tool; what happened, in plain words (a refusal's own words)."""
    from app import plans
    from app.routes import breakdown, project_assets, project_clips, storyboard
    from app.routes import plan as plan_route

    tool, pid = decision["tool"], project.id
    me = {"project_id": pid, "user": user, "db": db}
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(storage=storage)))
    try:
        if tool == "plan":  # the video's plan first when it needs one, as the Plan step does
            status = plans.status(db, project)
            if status == "none":
                plan_route.make(body=None, **me)
                return "Making the plan."
            if status == "ready":
                plan_route.approve(**me)  # approving it makes the shots
                return "Approved the plan; making the shots."
            breakdown.make(**me)
            return "Making the shots."
        if tool == "make_looks":
            project_assets.make_missing_looks(**me)
            return "Making the missing looks."
        if tool == "storyboard":
            project_assets.approve_all(**me)  # the looks it moves on with
            storyboard.make(body=storyboard.StoryboardIn(), **me)
            return "Making the storyboard."
        if tool == "stills":
            frames = db.scalars(select(StoryboardFrame).where(
                StoryboardFrame.project_id == pid, StoryboardFrame.file_id.is_(None)))  # fmt: skip
            for frame in list(frames):
                storyboard.render(frame_id=frame.id, body=None, **me)
            return "Drawing the stills."
        if tool == "clip_prompts":
            storyboard.approve_all(**me)  # the stills it moves on with
            project_clips.write_prompts(body=None, **me)
            return "Writing the clip prompts."
        if tool == "make_take":
            rows = _clips(db, pid, decision.get("clip_id"))
            if not rows:
                clip = decision.get("clip_id")
                return (f"Refused: there's no clip {clip}." if clip
                        else "Refused: every clip has a take already.")  # fmt: skip
            for row in rows:
                project_clips.prompt_looks_good(clip_id=row.id, **me)  # read: it moves on
                note = project_clips.TakeIn(note=decision.get("note") or "")
                project_clips.generate(clip_id=row.id, request=request, body=note, **me)
            return f"Making {_n(len(rows), 'take')}."
        if tool == "pick_take":
            (row,) = _clips(db, pid, decision.get("clip_id"))
            project_clips.pick_take(clip_id=row.id, take_id=decision["take_id"], **me)
            return f"Picked take {decision['take_id']} for {row.clip_id}."
        if tool == "final_cut":
            project_clips.approve_all(**me)  # the picked takes it cuts with
            project_clips.make_video(request=request, **me)
            return "Made the cut."
    except HTTPException as no:
        db.rollback()
        return f"Refused: {no.detail}"
    except ValueError:  # pick_take named no single clip
        return "Refused: name one clip."
    return f"Refused: there's no tool called {tool}."


def _clips(db: Session, project_id: int, clip_id: str | None) -> list[ProjectClip]:
    """One clip ("c2"), or with none named every clip that has no take yet."""
    rows = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project_id)
                      .order_by(ProjectClip.id)).all()  # fmt: skip
    if clip_id:
        return [r for r in rows if r.clip_id == clip_id]
    return [r for r in rows if r.picked_take_id is None]


def _n(n: int, what: str) -> str:
    return f"1 {what}" if n == 1 else f"{n} {what}s"
