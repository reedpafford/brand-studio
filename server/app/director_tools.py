"""The director's tools (docs/next/director-chat.md §6 item 3): each is a site action, run
through the very function its button calls, as the director's user, on this video only. So
every check stays the button's: price, the video's budget (past it: held for the owner,
Hold requests), rule 36, ownership. Nothing here spends another way, and no
tool can change Limits or another person's work. A refusal comes back as its plain words.
The approvals a person gives on the step screens are the director's own here: it approves a
step when it moves on from it (rule 21's self-approval)."""

import logging
import re
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cast_gate, take_mute
from app.models.accounts import User
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame

log = logging.getLogger(__name__)
CAST_LOCKED = "Approve the missing looks in Cast, or unlock the cast, then start it again."
TOOLS = ("plan", "make_looks", "storyboard", "stills", "clip_prompts", "make_take",
         "pick_take", "mute", "unmute", "splice_word", "add_sound", "song", "narration", "host",
         "edit_cut", "final_cut", "watch_cut", "ask", "clip_model", "settings", "add_place",
         "change_look", "ask_cast_ok", "split_clip", "outfit", "locked_line")  # fmt: skip
WAITING = "{} for the cast and places OK."
LONG_NOTE = ("Refused: a {what} note is at most {most} characters (this one is {n}); say it "
             "shorter, keeping everything it asks.")  # fmt: skip  # never cut (261: its end lost)
NOTES = {"make_take": "redo", "redraw_still": "redraw", "plan": "plan", "change_look": "change",
         "host": "motion", "add_sound": "sound"}  # fmt: skip  # their note goes on as written
REDRAW = " Use redraw_still on one of its shots, with the note."


def _redraw(said) -> str:
    """The one way to change a talker's picture, named where it's refused (video 281)."""
    from app import host, talker

    return REDRAW if said in (host.MADE, talker.SAID) else ""


STEP_BROKE = (
    "Refused: that step hit an error on our side and may not have finished. Try another way."  # noqa: E501
)


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
    if tool in NOTES and len(written := (decision.get("note") or "").strip()) > _most(tool):
        return LONG_NOTE.format(what=NOTES[tool], most=_most(tool), n=len(written))
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
                plan_route.make(body=plan_route.NoteIn(note=note), **me)  # Make a new plan
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
            _cast_in_shots(db, project, me)  # every role the shots need, drawn together
            if no := locks.refusal(project, "cast"):  # the cast and its looks are fixed
                return f"{no} {CAST_LOCKED}"  # what to do (rule 22), said again when it stops
            if again := cast_gate.redrawable(db, project, cast_gate.current(db, project)):
                from app.routes.sheets import SheetIn, queue_sheet  # a look that didn't draw:

                for item in again:  # drawn again, once (QA on #1482), before anything new
                    queue_sheet(db, user, item, SheetIn(), auto=True)
                return f"Drawing again what didn't draw: {', '.join(i.name for i in again)}."
            from app import told_look

            look = decision.get("look") or {}
            name = (look.get("name") or "").strip()
            if name and (why := told_look.prepare(db, user, project, look, storage)):
                return told_look.failed(db, project, run, look, why)
            made, blind = project_assets.make_missing(
                db, user, project, (name, look.get("description") or "")
            )
            if not blind:  # nothing made and nothing to make is no try (video 294: four)
                return ("Making the missing looks." if made else "Refused: every role and "
                        "place the shots show has a look already, or one being drawn.")  # fmt: skip
            why = (f"{project_assets.blind(blind)} make_looks again with `look`: the name, and "
                   "in `description` what they are and look like from the plan (person or "
                   "animal, age, build, what they wear).")  # fmt: skip
            if made:
                return f"Making the other missing looks. {why}"
            return told_look.failed(db, project, run, look, why) if name else f"Refused: {why}"
        if tool == "storyboard":
            _cast_in_shots(db, project, me)
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
            from app import advice, clip_prompts

            storyboard.approve_all(**me)  # the stills it moves on with
            if clip_prompts.to_rewrite(db, project) or not project_clips._clips(db, pid):
                project_clips.write_prompts(body=None, **me)
                return "Writing the clip prompts."
            # none stale: a clip whose problems stop its first take is rewritten instead (video
            # 299: "No clip needs new prompts" while its take was refused for its problems)
            stuck = [r for r in _clips(db, pid, None) if advice.stops(r)]
            for row in stuck:
                project_clips.write_prompts(body=project_clips.RewriteIn(clip_id=row.clip_id),
                                            **me)  # fmt: skip
            if not stuck:
                return "Refused: No clip needs new prompts."
            return f"Rewriting the prompt of {', '.join(r.clip_id for r in stuck)}."
        if tool == "make_take":
            from app import talker

            said = set() if decision.get("clip_id") else talker.clips(db, project)  # the talker's
            rows = [r for r in _clips(db, pid, decision.get("clip_id")) if r.clip_id not in said]
            if not rows:
                clip = decision.get("clip_id")
                clip = re.sub(r"^(clip\s*|c)", "", str(clip or "").strip(), flags=re.I)
                return (f"Refused: there's no clip {clip}." if clip  # "c9", "C9" or "9": clip 9
                        else "Refused: every clip has a take already.")  # fmt: skip
            from app import change, clip_takes
            from app.clip_takes import contradicts
            from app.director import against_notes, chat

            held, asked = 0, watch_cut.redo_findings(db, project, run)  # what the cut's watch found
            rewritten, hows, asked_note = [], [], (decision.get("note") or "").strip()
            fitting: list[str] = []  # prompts too long for their model, rewritten first
            notes = list(enumerate((m["text"] for m in chat(project, (run or {}).get("id"))), 1))
            first = [r for r in rows if not r.picked_take_id]
            waits: dict[str, list[str]] = {}
            if not decision.get("clip_id"):  # first takes: a prompt a note takes from waits
                waits = {r.clip_id: against_notes(r, notes)["against_notes"] for r in first
                         if against_notes(r, notes)}  # fmt: skip
                rows = [r for r in rows if r.clip_id not in waits]
                if not rows:
                    return f"Refused: {_against(waits)}"
            elif (
                first
                and contradicts(first[0].prompt, asked_note)
                and not _rewritten(db, first[0], asked_note)
            ):  # once: a rewrite that kept the thing goes ahead as the director asked
                # 226's clip 4: a first take's note takes away what its prompt shows ("no
                # phone"): the note rewrites the prompt first (Change it…), its take after; a
                # redo's is A7's below
                body = storyboard.ChangeIn(note=asked_note)
                project_clips.change_clip(clip_id=first[0].id, body=body, **me)
                return (f"Rewriting clip {first[0].clip_id.removeprefix('c')}'s prompt with the "
                        "note first; make its take once it's written.")  # fmt: skip
            blocked: dict[str, str] = {}  # prompts with problems: fixed free first, or rewritten
            for row in rows:
                if no := _fixed_first(db, row, me):
                    blocked[row.clip_id] = no
                    continue
                project_clips.prompt_looks_good(clip_id=row.id, **me)  # read: it moves on
                note = project_clips.TakeIn(note=asked_note)
                try:
                    edit, why = None, ""
                    if decision.get("edit_take") and note.note and row.picked_take_id:
                        edit, why = change.editable(db, project, row)  # else a plain redo
                    if why:
                        hows.append(f"{row.clip_id}: {change.NEW_TAKE.format(why=why)}")
                    if row.picked_take_id and (edit or contradicts(row.prompt, note.note)):
                        # A7: "no phone" under a prompt with the phone: appended, both stay and
                        # the take can't win; Change it… rewrites the prompt, then the take.
                        # An Omni edit goes the same way, its rewrite judging the note.
                        body = storyboard.ChangeIn(note=note.note)
                        job = project_clips.change_clip(clip_id=row.id, body=body, **me)
                        rewritten.append(row.clip_id)
                        if how := (row.change or {}).get("how"):
                            hows.append(f"{row.clip_id}: {how}")
                    else:
                        job = project_clips.generate(clip_id=row.id, request=request, body=note,
                                                     **me)  # fmt: skip
                except cast_gate.Waiting:  # its cast or places wait for the OK: the rest go on
                    db.rollback()
                    held += 1
                except HTTPException as no:  # too long for its model: being rewritten to fit
                    if not str(no.detail).startswith(clip_takes.TOO_LONG_START):
                        raise
                    db.rollback()  # its free fix is already saved (clip_takes.fits_prompt)
                    fitting.append(row.clip_id)
                else:
                    if found := asked.get(row.clip_id):  # the take in the cut says why (S6-03)
                        watch_cut.redone(db, project, row, found, job, note.note)
            fit = (f"The prompt of {', '.join(fitting)} is too long for its model, so it's being "
                   "rewritten to fit (free); make its take once it's rewritten.")  # fmt: skip
            if fitting and len(fitting) + held == len(rows):  # nothing was made: say why
                return f"Refused: {fit}"
            if blocked and len(blocked) == len(rows):
                return " ".join(blocked.values())
            rows = [r for r in rows if r.clip_id not in blocked]
            said = _held(f"Making {_n(len(rows) - held - len(fitting), 'take')}.", held, rows,
                         "take")  # fmt: skip
            said += "".join(f" {b.removeprefix('Refused: ')}" for b in blocked.values())
            said += f" {fit}" if fitting else ""
            said += (f" The note changes what {', '.join(rewritten)} shows, so its prompt "
                     "is rewritten with it first." if rewritten else "")  # fmt: skip
            said += "".join(f" {h}" for h in hows)  # an Omni edit, or why a new take instead
            return said + (f" {_against(waits)}" if waits else "")
        if tool == "pick_take":
            (row,) = _clips(db, pid, decision.get("clip_id"))
            was = row.picked_take_id
            project_clips.pick_take(clip_id=row.id, take_id=decision["take_id"], **me)
            take = db.get(ClipTake, decision["take_id"])  # its number, as the page shows it
            from app.director import cut_findings

            known = cut_findings(db, project).get(take.id) or [] if was != take.id else []
            back = (f" It comes back with what a watch of a cut found on it: {'; '.join(known)}."
                    if known else "")  # 233: the dead hold a paid redo had removed  # fmt: skip
            return f"Picked take {take.number} for {row.clip_id}.{back}"
        if tool == "mute":  # free: the found stretches, through the Mute button (#1091)
            (row,) = _clips(db, pid, decision.get("clip_id"))
            spans, clip = to_mute(db, row), f"clip {row.clip_id.removeprefix('c')}"
            if not spans:
                return f"Refused: nothing to mute in {clip}."
            take, done, refused = db.get(ClipTake, row.picked_take_id), 0, []
            for start, end in spans:
                was = take_mute.spans(take)
                try:
                    project_clips.mute(clip_id=row.id, body=project_clips.MuteIn(
                        start=start, end=end), **me)  # fmt: skip
                except HTTPException as no:  # the only copy of a scripted line (video 284)
                    refused.append(no.detail)
                    continue
                mine = [s for s in take_mute.spans(take) if s not in was]  # its own: Unmute
                take.made_with = {**take.made_with, "director_mutes": [
                    *(take.made_with.get("director_mutes") or []), *mine]}  # fmt: skip
                db.commit()
                done += 1
            if not done:
                return f"Refused: {refused[0]}"
            what = "a stretch" if done == 1 else f"{done} stretches"
            kept = f" Kept one: {refused[0]}" if refused else ""
            return f"Muted {what} of {clip} instead of remaking it.{kept}"
        if tool == "unmute":  # free: its own mutes on that clip lifted, a person's stay
            (row,) = _clips(db, pid, decision.get("clip_id"))
            take = db.get(ClipTake, row.picked_take_id) if row.picked_take_id else None
            clip = f"clip {row.clip_id.removeprefix('c')}"
            mine = (take.made_with or {}).get("director_mutes") or [] if take else []
            at = [i for i, s in enumerate(take_mute.spans(take)) if s in mine]
            if not at:
                return f"Refused: nothing you muted is left in {clip}; a person's mutes stay."
            for i in reversed(at):
                project_clips.unmute(clip_id=row.id, index=i, **me)
            take.made_with = {**take.made_with, "director_mutes": []}
            db.commit()
            what = "the stretch" if len(at) == 1 else f"the {len(at)} stretches"
            return f"Unmuted {what} you muted in {clip}. Free; it shows in the next cut."
        if tool == "splice_word":  # free: a clean copy the server found (word_splice)
            from app import word_splice

            (row,) = _clips(db, pid, decision.get("clip_id"))
            said = word_splice.splice(db, project, row, decision.get("word") or "")
            db.commit()
            return said
        if tool == "add_sound":  # asked for, or the style's guide calls for it: MMAudio's sound
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
                                        decision.get("why") or "",
                                        (run or {}).get("id"))  # fmt: skip
        if tool == "locked_line":  # S3-14's card, for a note no card answered as it came
            from app import locked_line

            return locked_line.for_director(db, user, project, decision.get("word"),
                                            decision.get("why") or "", (run or {}).get("id"),
                                            decision.get("value"))  # fmt: skip
        if tool == "host":  # a presenter's host, as Make the host
            from app import host

            return host.make(db, user, project, storage, motion=decision.get("note") or "")
        if tool == "watch_cut":  # its own limit, like a turn (watch_cut.start), never the budget
            return watch_cut.start(db, user, project, run)
        if tool == "review_stills":  # its own look at the stills before any take, own limit
            from app import still_review

            return still_review.start(db, user, project, run)
        if tool == "redraw_still":  # a still the review found off-story: Change it…, priced
            from app import host, still_review, talker

            sid = decision.get("shot_id")
            note = (decision.get("note") or "").strip()
            if talker.shot(db, project, sid or ""):  # the talker's still: their take follows it
                if not note:
                    return "Refused: say what the talker's still should change (a note)."
                return host.redraw(db, user, project, note)
            frame = next((f for f in still_review.frames(db, project) if f.shot_id == sid), None)
            if frame is None:
                return f"Refused: there's no drawn still for shot {sid}."
            if no := still_review.no_sheet(db, project, sid, note):
                return no
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
        if tool == "outfit":  # free: what the story dresses a character in, this video only
            from app.routes import cast

            look = decision.get("look") or {}
            return cast.dress(db, project, (look.get("name") or "").strip(),
                              look.get("description") or "")  # fmt: skip
        if tool == "ask_cast_ok":  # the card: the person approves the whole set at once
            _cast_in_shots(db, project, me)  # asked once, with everyone (261: places, then
            if missing := missing_looks(db, project):  # again with the skeleton)
                return f"Refused: make the missing looks first ({', '.join(missing)})."
            return cast_gate.ask(db, project, (run or {}).get("id"))
        if tool == "treatment":  # the story first (the Director's step), on its own limit
            from app.director import write_treatment

            return write_treatment(db, user, project, run, decision.get("note") or "")
        if tool == "split_clip":  # free: Split the clip, the breakdown's own fix
            return _split(db, project, decision.get("clip_id") or "", me)
        if tool == "edit_cut":  # free: the cut editor's own edit, marked as the director's
            try:
                return _edit_cut(db, project, decision.get("edit") or {}, request, me, run,
                                 decision.get("why") or "")  # fmt: skip
            except HTTPException:
                raise
            except Exception:  # never leave the turn without a result (the run would hang)
                db.rollback()
                log.exception("project %s: edit_cut failed", pid)
                return "Refused: that edit couldn't be made. Name its kind, piece and values."
        if tool == "final_cut":  # free, on the worker: the cut before plays until it's made
            from app.routes import cut

            project_clips.approve_all(**me)  # the picked takes it cuts with
            made = cut.make(request=request, **me)
            n = made.making.number if made.making else (made.number or 1)
            return f"Making Cut {n}{_again(db, pid, n)}."
    except HTTPException as no:
        db.rollback()
        return f"Refused: {no.detail}{_redraw(no.detail)}"
    except ValidationError as no:  # A4: a value past a field's limit, said as it is
        db.rollback()
        e = no.errors()[0]
        return f"Refused: {'.'.join(map(str, e['loc'])) or 'a value'}: {e['msg']}."
    except ValueError:  # pick_take named no single clip
        return "Refused: name one clip."
    except Exception:  # noqa: BLE001 - never leave the turn without a result (the run would hang)
        db.rollback()
        log.exception("project %s: %s failed", pid, tool)
        return STEP_BROKE
    return f"Refused: there's no tool called {tool}."


def _edit_cut(db: Session, project: Project, move: dict, request, me: dict,
              run: dict | None, why: str = "") -> str:  # fmt: skip
    """One edit through the cut editor's route (its dot and its own Undo on the page); the
    turn keeps its id (`run["edit_id"]`) so the chat shows Undo beside it. A person's own
    music choice stays theirs unless the move answers a person's note (`cut_edits`)."""
    from app import cut_edits
    from app.models.clips import CutEdit

    run = run if run is not None else {}
    theirs = (
        db.get(CutEdit, int(move["edit_id"]))
        if move.get("kind") == "undo" and move.get("edit_id") is not None
        else cut_edits._persons_music(db, project)
    )
    noted = _asked_since(db, project, run.get("id"), why, theirs)
    marked = cut_edits.PERSON_ASKED.set(noted)
    try:
        return _edit_cut_now(db, project, move, request, me, run, noted)
    finally:
        cut_edits.PERSON_ASKED.reset(marked)


def _asked_since(db: Session, project: Project, run_id: str | None, why: str, edit) -> bool:
    """The move answers a person's note ("Note 2: quieter music") that's still open and was
    written after `edit`, the person's own music choice it would change (QA on #1415: the
    run's older "Make the hook punchier" never unlocks a removal made since)."""
    from datetime import datetime

    from app.director import NOTE, answered

    if not run_id:
        return False
    notes = [m for m in project.director_chat or [] if m.get("run") == run_id]  # Note 1, 2, …
    done, since = answered(db, run_id, project.id), edit.created_at if edit is not None else None

    def after(m: dict) -> bool:
        at = datetime.fromisoformat(m["at"]).replace(tzinfo=None) if m.get("at") else None
        return since is None or (at is not None and at > since)

    return any(1 <= (n := int(x)) <= len(notes) and n not in done and after(notes[n - 1])
               for x in NOTE.findall(why))  # fmt: skip


def _edit_cut_now(db: Session, project: Project, move: dict, request, me: dict, run: dict,
                  noted: bool) -> str:  # fmt: skip
    from pydantic import ValidationError

    from app.cut_edits import PERSONS_MUSIC
    from app.models.clips import CutEdit
    from app.routes import cut

    run.pop("edit_id", None)
    if move.get("kind") == "undo":
        if move.get("edit_id") is None:
            return "Refused: name the edit to undo (its id in timeline.edits)."
        theirs = db.get(CutEdit, int(move["edit_id"]))
        if theirs and theirs.kind == "music" and not theirs.director and not noted:
            return f"Refused: {PERSONS_MUSIC.format(theirs.said)}"  # undoing it is a change
        out = cut.undo_one(edit_id=int(move["edit_id"]), request=request, **me)
        said = next((e.said for e in out.edits if e.id == move["edit_id"]), "the edit")
        return f"Undid: {said}."
    asked = {k: v for k, v in move.items() if v is not None and k in cut.EditIn.model_fields}
    try:
        out = cut.edit(body=cut.EditIn(**asked), request=request, **me)
    except ValidationError:
        return "Refused: say the edit's kind and its piece."
    made = max(out.edits, key=lambda e: e.id)
    run["edit_id"] = made.id
    row = db.get(CutEdit, made.id)
    if (shows := (move.get("shows") or "").strip()) and (row.data or {}).get("ending"):
        row.data = {**row.data, "shows": shows}  # what the ending was trimmed to show: the
        # next watch checks the cut's last frames show it (a trim moved to keep a word too)
        db.commit()
    return f"{made.said}. Free; it shows in the next cut."


def _cast_in_shots(db: Session, project: Project, me: dict) -> None:
    """Before the storyboard (no still yet): the right cast in each shot and every speaker a
    role, free (Reed's item 9: the director's job), so the looks are made and the cast and
    places OK asked once, with everyone in it."""
    from app.clip_prompts import newest
    from app.routes import breakdown

    bd = newest(db, project)
    if bd is None or db.scalar(
        select(StoryboardFrame.id)
        .where(StoryboardFrame.breakdown_id == bd.id, StoryboardFrame.file_id.is_not(None))
        .limit(1)
    ):
        return  # fmt: skip
    try:
        breakdown.fix_cast(**me)
    except HTTPException:
        pass  # every shot already has it
    from app.breakdown import complete_cast

    if complete_cast(db, project):  # every speaker a role, as opening Cast does: a role with
        db.commit()  # no look is then made by make_looks


def missing_looks(db: Session, project: Project) -> list[str]:
    """The roles, brand characters and places the shots need that have no look yet."""
    from app.routes.project_assets import _missing, missing_copies, missing_places

    again = cast_gate.redrawable(db, project, cast_gate.current(db, project))  # didn't draw
    return [*(s.role for s in _missing(db, project)),
            *(c.name for c in missing_copies(db, project)),
            *(p.name for p in missing_places(db, project)), *(i.name for i in again)]  # fmt: skip


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


def _again(db: Session, project_id: int, number: int) -> str:
    """A cut made again under its number before it's handed over (S3-12: Cut N is the Nth
    handed over), said so: " again (2nd try)" (E2E 233 read "Making Cut 1" four times)."""
    from app.models.clips import FinalVideo

    made = db.scalar(select(func.count()).where(FinalVideo.project_id == project_id,
                                                FinalVideo.number == number))  # fmt: skip
    return f" again ({_nth(made + 1)} try)" if made else ""


def _nth(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _clips(db: Session, project_id: int, clip_id: str | None) -> list[ProjectClip]:
    """One clip ("c2"), or with none named every clip that has no take yet."""
    rows = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project_id)
                      .order_by(ProjectClip.id)).all()  # fmt: skip
    if clip_id:
        return [r for r in rows if r.clip_id == clip_id]
    return [r for r in rows if r.picked_take_id is None]


def _most(tool: str) -> int:
    """The longest note a tool takes: a redo's (a take's Redo note), a motion note's or a
    sound's (its button's)."""
    from app import take_sound, talker
    from app.clip_takes import NOTE_MAX

    return {"host": talker.LONGEST_MOTION, "add_sound": take_sound.LONGEST}.get(tool, NOTE_MAX)


def _fixed_first(db: Session, row: ProjectClip, me: dict) -> str:
    """A clip whose prompt has problems that stop its take (video 299's c3: "Fix this clip's
    problems first", while clip_prompts said no clip needs new prompts) gets the free fix first,
    as its button does: "" when it's fixed (its take goes ahead), else what happens instead."""
    from app import advice
    from app.routes import project_clips

    if not advice.stops(row):
        return ""
    n = row.clip_id.removeprefix("c")
    try:
        out = project_clips.fix_clip(clip_id=row.id, **me)
    except HTTPException:
        out = None
    db.refresh(row)
    if out is not None and out.fixed:
        return ""
    if out is not None and out.fixed is None:
        return f"Fixing clip {n}'s prompt first (free); make its take once it's fixed."
    if out is not None and out.reason:  # an older breakdown, a look not approved: its own why
        return f"Refused: clip {n}: {out.reason}"
    return (
        f"Refused: clip {n}'s prompt has problems its free fix can't clear "
        f"({'; '.join(advice.stops(row))}): rewrite it with clip_prompts."
    )


def _rewritten(db: Session, row: ProjectClip, note: str) -> bool:
    """This clip's prompt was already rewritten with this note (Change it…); a rewrite that
    failed or was cancelled never ran, so it isn't one."""
    from app.models.jobs import Job, JobStatus

    asked = select(Job).where(Job.project_id == row.project_id,
                              Job.input["step"].as_string() == "change",
                              Job.status.not_in((JobStatus.failed,
                                                 JobStatus.cancelled)))  # fmt: skip
    said = note.strip()
    return any(j.input.get("target") == "clip" and j.input.get("target_id") == row.id
               and j.input.get("note") == said for j in db.scalars(asked))  # fmt: skip


def _against(waits: dict[str, list[str]]) -> str:
    """The first takes kept back because a note takes away what their prompt shows."""
    said = "; ".join(f"clip {c.removeprefix('c')} ({', '.join(n)})" for c, n in waits.items())
    return (
        f"Not made yet, their prompt shows what a note takes away: {said}. Where the note "
        "covers the clip, make its take alone with a note saying what to take out (it "
        "rewrites the prompt first); where it doesn't, make it alone as it is."
    )


def _held(said: str, held: int, rows, what: str) -> str:
    """What a stills or takes move did, and how many wait for the cast and places OK."""
    if not held:
        return said
    if held == len(rows):
        return f"Refused: {WAITING.format('They all wait')}"
    return f"{said} {WAITING.format(_n(held, what) + (' waits' if held == 1 else ' wait'))}"


def _n(n: int, what: str) -> str:
    return f"1 {what}" if n == 1 else f"{n} {what}s"
