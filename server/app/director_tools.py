"""The director's tools (docs/next/director-chat.md §6 item 3): each is a site action, run
through the very function its button calls, as the director's user, on this video only. So
every check stays the button's: price, the video's budget (past it: held for the owner,
Hold requests), the per-video cap, rule 36, ownership. Nothing here spends another way, and no
tool can change Limits or another person's work. A refusal comes back as its plain words.
The approvals a person gives on the step screens are the director's own here: it approves a
step when it moves on from it (rule 21's self-approval)."""

from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame

CAST_LOCKED = "Approve the missing looks in Cast, or unlock the cast, then start it again."
TOOLS = ("plan", "make_looks", "storyboard", "stills", "clip_prompts", "make_take",
         "pick_take", "mute", "splice_word", "song", "narration", "host", "final_cut",
         "watch_cut")  # fmt: skip


def run(db: Session, user: User, project: Project, decision: dict, storage,
        run: dict | None = None) -> str:  # fmt: skip
    """Do one tool; what happened, in plain words (a refusal's own words)."""
    from app.routes.jobs import DIRECTOR_TOOL

    marked = DIRECTOR_TOOL.set(True)  # the jobs it starts are the director's, not a person's
    try:
        return _run(db, user, project, decision, storage, run)
    finally:
        DIRECTOR_TOOL.reset(marked)


def _run(db: Session, user: User, project: Project, decision: dict, storage,
         run: dict | None) -> str:  # fmt: skip
    from app import locks, plans, watch_cut
    from app.director import to_mute
    from app.routes import breakdown, project_assets, project_clips, storyboard
    from app.routes import plan as plan_route

    tool, pid = decision["tool"], project.id
    me = {"project_id": pid, "user": user, "db": db}
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(storage=storage)))
    try:
        if tool == "plan":  # the video's plan first when it needs one, as the Plan step does
            status = plans.status(db, project)
            if (note := (decision.get("note") or "").strip()) and status != "none":
                plan_route.make(body=plan_route.NoteIn(note=note[:500]), **me)  # Make a new plan
                return f"Planning again: {note}"  # the watch's "Re-plan:" (once a run)
            if status == "none":
                plan_route.make(body=None, **me)
                return "Making the plan."
            if status == "ready":
                plan_route.approve(**me)  # approving it makes the shots
                return "Approved the plan; making the shots."
            breakdown.make(**me)
            return "Making the shots."
        if tool == "make_looks":
            if no := locks.refusal(project, "cast"):  # the cast and its looks are fixed
                return f"{no} {CAST_LOCKED}"  # what to do (rule 22), said again when it stops
            project_assets.make_missing_looks(**me)
            return "Making the missing looks."
        if tool == "storyboard":
            try:  # the right cast in each shot first, free (Reed's item 9: the director's job)
                breakdown.fix_cast(**me)
            except HTTPException:
                pass  # every shot already has it
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
            take = db.get(ClipTake, decision["take_id"])  # its number, as the page shows it
            return f"Picked take {take.number} for {row.clip_id}."
        if tool == "mute":  # free: the found stretches, through the Mute button (#1091)
            (row,) = _clips(db, pid, decision.get("clip_id"))
            spans, clip = to_mute(db, row), f"clip {row.clip_id.removeprefix('c')}"
            if not spans:
                return f"Refused: nothing to mute in {clip}."
            for start, end in spans:
                project_clips.mute(clip_id=row.id, body=project_clips.MuteIn(start=start, end=end),
                                   **me)  # fmt: skip
            what = "a stretch" if len(spans) == 1 else f"{len(spans)} stretches"
            return f"Muted {what} of {clip} instead of remaking it."
        if tool == "splice_word":  # free: a clean copy the server found (word_splice)
            from app import word_splice

            (row,) = _clips(db, pid, decision.get("clip_id"))
            said = word_splice.splice(db, project, row, decision.get("word") or "")
            db.commit()
            return said
        if tool in ("song", "narration"):  # the audio first in a song or narrated video
            from app import director_song

            said = director_song.run(db, user, project, decision, run if run is not None else {})
            db.commit()
            return said
        if tool == "host":  # a presenter's host, as Make the host
            from app import host

            return host.make(db, user, project, storage)
        if tool == "watch_cut":  # its own limit, like a turn (watch_cut.start), never the budget
            return watch_cut.start(db, user, project, run)
        if tool == "review_stills":  # its own look at the stills before any take, own limit
            from app import still_review

            return still_review.start(db, user, project, run)
        if tool == "redraw_still":  # a still the review found off-story: Change it…, priced
            from app import still_review

            sid = decision.get("shot_id")
            frame = next((f for f in still_review.frames(db, project) if f.shot_id == sid), None)
            if frame is None:
                return f"Refused: there's no drawn still for shot {sid}."
            note = (decision.get("note") or "").strip()[:500]
            storyboard.change_frame(frame_id=frame.id, body=storyboard.ChangeIn(note=note), **me)
            return f"Drawing shot {sid} again: {note}"
        if tool == "treatment":  # the story first (the Director's step), on its own limit
            from app.director import write_treatment

            return write_treatment(db, user, project, run, decision.get("note") or "")
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
