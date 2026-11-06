"""The director's tools (docs/next/director-chat.md §6 item 3): each is a site action, run
through the very function its button calls, as the director's user, on this video only. So
every check stays the button's: price, the video's budget (past it: held for the owner,
Hold requests), rule 36, ownership. Nothing here spends another way, and no
tool can change Limits or another person's work. A refusal comes back as its plain words.
The approvals a person gives on the step screens are the director's own here: it approves a
step when it moves on from it (rule 21's self-approval)."""

import re
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cast_gate
from app.models.accounts import User
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame

CAST_LOCKED = "Approve the missing looks in Cast, or unlock the cast, then start it again."
TOOLS = ("plan", "make_looks", "storyboard", "stills", "clip_prompts", "make_take",
         "pick_take", "mute", "splice_word", "add_sound", "song", "narration", "host",
         "final_cut", "watch_cut", "ask", "clip_model", "settings", "add_place", "change_look",
         "ask_cast_ok", "split_clip")  # fmt: skip
WAITING = "{} for the cast and places OK."


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
            from app.director import fresh

            if fresh(db, project, run)[0]:  # "Start the plan again": a whole new plan (S3-08)
                plan_route.make(body=None, **me)
                return "Planning the whole video again."
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
            from app.breakdown import complete_cast

            if complete_cast(db, project):  # every speaker a role, as opening Cast does: a
                db.commit()  # role with no look is then made by make_looks
            storyboard.make(body=storyboard.StoryboardIn(), **me)  # the looks: the person's OK
            return "Making the storyboard."
        if tool == "stills":
            frames = db.scalars(select(StoryboardFrame).where(StoryboardFrame.project_id == pid,
                                StoryboardFrame.file_id.is_(None))).all()  # fmt: skip
            held = 0
            for frame in frames:
                try:
                    storyboard.render(frame_id=frame.id, body=None, **me)
                except cast_gate.Waiting:  # only those that show what waits for the OK
                    db.rollback()
                    held += 1
            return _held("Drawing the stills.", held, frames, "still")
        if tool == "clip_prompts":
            storyboard.approve_all(**me)  # the stills it moves on with
            project_clips.write_prompts(body=None, **me)
            return "Writing the clip prompts."
        if tool == "make_take":
            from app import talker

            said = set() if decision.get("clip_id") else talker.clips(db, project)  # the talker's
            rows = [r for r in _clips(db, pid, decision.get("clip_id")) if r.clip_id not in said]
            if not rows:
                clip = decision.get("clip_id")
                clip = re.sub(r"^(clip\s*|c)", "", str(clip or "").strip(), flags=re.I)
                return (f"Refused: there's no clip {clip}." if clip  # "c9", "C9" or "9": clip 9
                        else "Refused: every clip has a take already.")  # fmt: skip
            held = 0
            for row in rows:
                project_clips.prompt_looks_good(clip_id=row.id, **me)  # read: it moves on
                note = project_clips.TakeIn(note=decision.get("note") or "")
                try:
                    project_clips.generate(clip_id=row.id, request=request, body=note, **me)
                except cast_gate.Waiting:  # its cast or places wait for the OK: the rest go on
                    db.rollback()
                    held += 1
            return _held(f"Making {_n(len(rows) - held, 'take')}.", held, rows, "take")
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
        if tool == "add_sound":  # only when asked: MMAudio's sound under the picked takes
            from app import take_sound

            return take_sound.to_cut(db, user, project, storage, decision.get("clip_id"),
                                     decision.get("note") or "")  # fmt: skip
        if tool in ("song", "narration"):  # the audio first in a song or narrated video
            from app import director_song

            said = director_song.run(db, user, project, decision, run if run is not None else {})
            db.commit()
            return said
        if tool == "clip_model":  # one clip's model, from the model map, its price said first
            from app import model_map

            rows = _clips(db, pid, decision.get("clip_id")) if decision.get("clip_id") else []
            if len(rows) != 1:
                return "Refused: name one clip."
            said = model_map.choose(db, project, rows[0], decision.get("model"),
                                    decision.get("why") or "")  # fmt: skip
            db.commit()
            return said
        if tool == "settings":  # the Plan tab's switch, from the chat; a person's choice stays
            from app import settings_move

            return settings_move.switch(db, user, project, decision.get("setting"),
                                        decision.get("model") or decision.get("value"),
                                        decision.get("why") or "")  # fmt: skip
        if tool == "host":  # a presenter's host, as Make the host
            from app import host

            return host.make(db, user, project, storage, motion=decision.get("note") or "")
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
        if tool == "ask":  # a question for a person: it waits on that point only (asks.py)
            from app import asks

            move = {**(decision.get("ask") or {}), "closed": decision.get("why") or ""}
            return asks.asked(db, project, (run or {}).get("id"), move)
        if tool == "add_place":  # a place for some shots, made for this video only
            from app.routes import cast

            move = decision.get("look") or {}
            if no := locks.refusal(project, "cast"):
                return f"{no} {CAST_LOCKED}"
            body = cast.PlaceIn(name=(move.get("name") or "").strip()[:120] or None,
                                description=(move.get("description") or "")[:2000],
                                shot_ids=move.get("shot_ids") or [],
                                library_item_id=move.get("library_item_id"))  # fmt: skip
            item = cast.add_place(db, user, project, body)
            look = "it has its look" if item.sheet_file_id else "its look is next"
            return f"Added {item.name} for shots {', '.join(body.shot_ids)}; {look}."
        if tool == "change_look":  # Change this… on a character or place, priced
            from app.routes import cast

            name = ((decision.get("look") or {}).get("name") or "").strip()
            return cast.change_look(db, user, project, name, decision.get("note") or "")
        if tool == "ask_cast_ok":  # the card: the person approves the whole set at once
            return cast_gate.ask(db, project, (run or {}).get("id"))
        if tool == "treatment":  # the story first (the Director's step), on its own limit
            from app.director import write_treatment

            return write_treatment(db, user, project, run, decision.get("note") or "")
        if tool == "split_clip":  # free: Split the clip, the breakdown's own fix
            return _split(db, project, decision.get("clip_id") or "", me)
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


def _split(db: Session, project: Project, clip: str, me: dict) -> str:
    """A clip longer than the video model makes, split between its shots and at its sentence
    breaks, as the breakdown's Split the clip does (free; the words don't change)."""
    from app import breakdown_fix
    from app.clip_prompts import newest
    from app.routes import breakdown

    row = newest(db, project)
    n = clip.removeprefix("c")
    said = next((p for p in (row.problems if row else []) if breakdown_fix.too_long([p]) == [clip]),
                None)  # fmt: skip
    if said is None:
        return f"Refused: clip {n} isn't longer than the video model makes."
    before = len(row.data.get("clips", []))
    made = len(breakdown.fix(body=breakdown.FixIn(problems=[said]), **me).breakdown.clips)
    return f"Split clip {n} into {made - before + 1} clips at its sentence breaks."


def _clips(db: Session, project_id: int, clip_id: str | None) -> list[ProjectClip]:
    """One clip ("c2"), or with none named every clip that has no take yet."""
    rows = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project_id)
                      .order_by(ProjectClip.id)).all()  # fmt: skip
    if clip_id:
        return [r for r in rows if r.clip_id == clip_id]
    return [r for r in rows if r.picked_take_id is None]


def _held(said: str, held: int, rows, what: str) -> str:
    """What a stills or takes move did, and how many wait for the cast and places OK."""
    if not held:
        return said
    if held == len(rows):
        return f"Refused: {WAITING.format('They all wait')}"
    return f"{said} {WAITING.format(_n(held, what) + (' waits' if held == 1 else ' wait'))}"


def _n(n: int, what: str) -> str:
    return f"1 {what}" if n == 1 else f"{n} {what}s"
