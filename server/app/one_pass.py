"""The one-pass director (Reed, 10 Nov: "I like our outputs and the creativity from the
director, but like the speed of higgsfield ... ours understanding the context of the whole
script is good - we just have a lot of fluff"). For a new video of any format, one Claude call
(step "one_pass", app/prompts/one_pass.md, with the rules, the craft, the style's and format's
guides and the video model's notes) reads the whole script and returns the ShootingPlan: the
treatment, the voices, who and where, and every clip shot by shot. Code checks it (`checked`:
every spoken line once, in order, by its number), asks once more inside the same job if it
fails, and writes it into the tables the tabs read (`save`: the treatment card, the plan, the
shots, the clips and each clip's prompt, built in app/one_pass_assemble.py). No storyboard, no
stills, no call per clip, no watch of each take: a take is listened to (free), one that
misses a scripted line is made once more with the same prompt, and the cut is watched once.

A Narrated, Zack D, Presenter or Song video is timed to a recorded track, so its narration or
song is made and measured before the plan, and the plan says only where in it each shot
starts (app/one_pass_timed.py, prompts/narrated_one_pass.md and song_one_pass.md); a presenter
is one take beside the B-roll (a host in a corner, or a talker cut between it), or, in UGC,
says the lines in clips of their own. Reel remakes, variations and the owner's Change the line
keep the plan and change only what they touch.

The run is still a director run: its turns, cards, Stop, Carry on, holds and prices are
app/director.py's. But every turn is the server's own step, chosen by `move` (no Claude turn).
A video is stamped at its first run (`pick`) and never changes; a video already started, and
a format left out of `settings.one_pass_engines`, keeps the step-by-step director."""

import json
import math
import re
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import asks, cast_gate, clip_prompts, omni_talker, one_pass_timed, plans, prompts
from app.credits import COUNTED, estimate, past_approved
from app.enhance import escape, escape_block, project_context
from app.models.accounts import User
from app.models.asks import Ask
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.one_pass_assemble import (
    OFF,
    PLAN,
    assemble,
    follow,
    long_lines,
    spoken,
    to_breakdown,
    units,
)
from app.prompts import check
from app.prompts.schemas import Breakdown, ShootingPlan

ENGINE = STEP = "one_pass"
KIND = "write-claude"
RUN = "director_run"  # director.RUN
CARD = "start_card"  # `move`'s step for "ready for Make it": the run's start card comes
STORED = ("make_take", "final_cut", "host")  # steps that read files: the worker's own turn
STILL = "The plan still couldn't be used after one more try: "
PLAN_FAILED = ("It stopped: the plan couldn't be made ({why}). Start it again to try once "
               "more, or change the script first.")  # fmt: skip
STYLE_TOPIC = "The song's style"  # the card a song with no style line asks, once
STYLE_ASK = "What should the song sound like?"
STYLE_WHY = ("Reply with the genre, the voice and the tempo, like “bright pop, warm female "
             "vocal, 110 bpm”. The song is made in it, and the video is timed to the "
             "song.")  # fmt: skip
TWICE = "twice running its answer had this wrong: "  # then the check's own first words
NOT_PLANNED = ("It stopped: planning this change is waiting on the owner's OK, and nothing "
               "can be made without a plan. Press Make it again to plan it.")  # fmt: skip
NO_LOOK = ("It stopped: {} and couldn't be drawn. Upload or pick a look in Cast, then press "
           "Carry on.")  # fmt: skip
CUT_FAILED = "It stopped: the cut couldn't be made ({}). Fix that in Clips, then press Carry on."
NO_HOST = ("It stopped: the presenter's take didn't come out twice running, and nothing was "
           "charged for it. Press Make it again on the presenter in Cast, then Carry "
           "on.")  # fmt: skip
CHAT = "Tell the director what to change in the chat: it plans again only what your note touches."
BUILT = f"This video's clip prompts are built from its plan and are up to date. {CHAT}"
PLANNED = f"The director planned this video's scenes and shots in one pass. {CHAT}"
UNFIT = ("Clip {n} is planned at {s} s, and {model} makes {low}–{high} s a clip. Ask the director "
         "in the chat to keep every clip inside that, then switch the model.")  # fmt: skip
LONG = ("The prompt is too long for {model} ({n:,} of {most:,} characters). Shorten it with "
        "Edit (free), or tell the director in the chat to split this clip in two. Nothing was "
        "charged.")  # fmt: skip


# --- Which videos ----------------------------------------------------------------------------


def on(project) -> bool:
    """This video is made by the one-pass director (its stamp, never re-read from settings)."""
    return project is not None and getattr(project, "engine", None) == ENGINE


def takes(script, text: str) -> bool:
    """A script the one-pass director takes: one whose format is switched on for it
    (`settings.one_pass_engines`) and has words to make: a Dialogue script's spoken lines, a
    narration's words (Narrated, Zack D, Presenter) or a song's sung lines. A reel's remake
    is one of them (its reel reaches the plan call, `_reel`)."""
    from app.script_library import format_id
    from app.settings import get_settings

    settings = get_settings()
    if not (settings.one_pass and script is not None
            and format_id(script) in settings.one_pass_engines):  # fmt: skip
        return False
    if script.kind == "song":
        return bool(check.sung_lines(text))
    return bool(check.narration_text(text) if script.kind == "narrated" else spoken(text))


def eligible(db: Session, project: Project) -> bool:
    """A video that would start on the one-pass director: new (nothing ever queued for it, no
    plan or shots; a Preferred narration or song it starts on is sound, not a plan), from a
    script it `takes`, and not a variation of a video made the earlier way (one of a one-pass
    video is copied with its engine). A reference clip given on the earlier New video form
    keeps that form's path."""
    from app import video_variations
    from app.narration import video_script

    words = plans.script(db, project)
    made = (db.scalar(select(Job.id).where(Job.project_id == project.id).limit(1))
            or clip_prompts.newest(db, project) is not None or project.plan)  # fmt: skip
    return bool(not made and not project.reference_file_id and words is not None
                and takes(video_script(db, project), words.text)
                and not video_variations.source(db, project))  # fmt: skip


def refuse(project) -> None:
    """A press that would plan or re-shoot the old way, on a one-pass video: refused (409),
    saying where the change is made instead."""
    if on(project):
        raise HTTPException(409, PLANNED)


def model_refusal(db: Session, project: Project, model_id: str | None) -> str:
    """Why a one-pass video can't move to this video model (None: its style's own) now, or "":
    a clip its plan made longer or shorter than that model makes would never be made. Its
    plan is changed first, in the chat."""
    from app.breakdown import video_model
    from app.catalogue import catalogue

    row = clip_prompts.newest(db, project) if on(project) else None
    from app.narration import video_kind

    m = catalogue().get(model_id or "") or video_model(None, project.look,
                                                       video_kind(db, project))  # fmt: skip
    for c in (row.data.get("clips") or []) if row and m.duration else []:
        if not m.duration.min <= c["seconds"] <= m.duration.max:
            return UNFIT.format(n=c["id"].removeprefix("c"), s=c["seconds"], model=m.name,
                                low=m.duration.min, high=m.duration.max)  # fmt: skip
    return ""


def pick(db: Session, project: Project) -> None:
    """The video's first run: its engine is stamped, once. A video that isn't `eligible` now
    never becomes one (it has turns from then on)."""
    if not project.engine and eligible(db, project):
        project.engine = ENGINE


def priced(db: Session, draft, video) -> bool:
    """Whether a price is the one-pass director's: a stamped video's, or one for a video
    (or a script with none yet) that would start on it."""
    from app.models.script_library import Script

    if video is not None and video.id is not None:
        return on(video) or (not video.engine and eligible(db, video))
    return takes(db.get(Script, draft.script_id), draft.text or "")


# --- The plan call ---------------------------------------------------------------------------


def model_notes(model_id: str) -> str:
    """The director's planning notes for a video model (app/prompts/models/<id>.md, else
    default.md), without the file's own comment."""
    folder = prompts.HERE / "models"
    path = folder / f"{Path(model_id).name}.md"
    text = (path if path.exists() else folder / "default.md").read_text()
    return re.sub(r"<!--.*?-->\s*", "", text, flags=re.S).strip()


def shooting_plan(db: Session, project: Project) -> dict | None:
    """The plan the video's newest shots were built from, or None."""
    row = clip_prompts.newest(db, project)
    return (row.data or {}).get(PLAN) if row else None


TIMED = {"song": "song_one_pass", "narrated": "narrated_one_pass"}  # a timed video's prompt
UNITS = "units"  # in a plan call's input: the script as it was numbered for it (`units`)
SPLIT = "split"  # there, and kept with the saved plan: the script lines given by the sentence


def numbered(job_input: dict) -> tuple[str, list[int]]:
    """The script as a plan call numbered it, and each numbered row's own script line: the
    script itself, unless a long spoken line was given a sentence a row (`units`)."""
    given = job_input.get(UNITS)
    if given:
        return given["text"], given["lines"]
    return job_input["script"], list(range(1, len(job_input["script"].splitlines()) + 1))


def _assets(db: Session, project: Project) -> dict:
    """Every picture the plan may use (storyboard.assets), less a brand's place with no
    picture in this video's look: nobody draws one (make_looks draws the places made for this
    video), so a plan that named it waited for a person (Reed, 11 Nov: videos 373 and 383)."""
    from app.models.library import LibraryItem
    from app.storyboard import assets

    return {k: v for k, v in assets(db, project).items() if v[1] or not k.startswith("place:")
            or db.get(LibraryItem, int(k[6:])).owner_project_id}  # fmt: skip


def job_input(db: Session, project: Project, run: dict) -> dict:
    """The one call: everything the director reads, and what the free check needs. A video
    timed to a narration or a song reads its own part of the prompt (the job's step stays
    `one_pass`) and the take in use, measured (<song>); the check gets that take's times
    (`audio`)."""
    from app import director, director_song, footage, picks, script_preview
    from app.breakdown import TOKENS, timing, video_model, video_model_block
    from app.cast_roles import video_slots
    from app.storyboard import cast_looks

    version = plans.script(db, project)
    track = one_pass_timed.audio(db, project, version.text)
    system, context = project_context(db, project, TIMED.get(director_song.kind(db, project),
                                                             STEP))  # fmt: skip
    if project.script_draft_id:  # its roles with no look yet, as the breakdown reads them
        from app.models.script_library import ScriptDraft

        draft = db.get(ScriptDraft, project.script_draft_id)
        context = script_preview.with_slots(db, draft.script_id, context, project)
    m, known = video_model(project), _assets(db, project)
    lines = "\n".join(dict.fromkeys(line for line, _ in known.values()))
    again = not director.fresh(db, project, run)[0] and shooting_plan(db, project)
    films = omni_talker.name(db, project) if omni_talker.on(db, project) else ""
    split: list[int] = []  # the spoken lines given a sentence a row: decided once, with the plan
    if not track:
        split = again.get(SPLIT, []) if again else long_lines(version.text, m.duration.max, films)
    rows, origin = units(version.text, split, films)
    text = "\n".join([
        context, f"<assets>\n{escape(lines)}\n</assets>", video_model_block(m),
        model_notes(m.id), f"<script>\n{escape(prompts.number_lines(rows))}\n</script>",
    ]) + picks.context(db, project)  # fmt: skip
    if track:
        from app import audition, host, talker
        from app.song_breakdown import take_for

        text += "\n" + escape_block(prompts.song_block(take_for(db, project).timing))
        track["talks"] = talker.on(db, project)  # their own clips are cut from one take
        if host.presents(db, project):
            who = audition.who(db, project)
            text += "\n" + escape_block(one_pass_timed.host_block(who, host.how(project)))
    reel, sheet = _reel(db, project)
    text += reel
    if films:  # a presenter filmed on Omni: they say the lines themselves, B-roll laid over
        text += "\n" + escape_block(one_pass_timed.talker_block(films, m.duration.max))
    notes = [m["text"] for m in director.chat(project, run["id"])]
    if notes:
        said = "\n".join(f"Note {n}: {t}" for n, t in enumerate(notes, 1))
        text += f"\n<notes>\n{escape(said)}\n</notes>"
    if notes and again:
        was = {k: v for k, v in again.items() if k != SPLIT}
        text += f"\n<plan>\n{escape(json.dumps(was, ensure_ascii=False))}\n</plan>"
    cast = [s.role for s in video_slots(db, project)] + [i.name for i in cast_looks(db, project)]
    seen = {"files": {"reference_images": [sheet]}, "fit_images_to": 1024} if sheet else {}
    data = {"step": STEP, "project_id": project.id, "script_version": version.version, **seen,
            RUN: run, "system": system, "prompt": text, "max_tokens": TOKENS,
            "script": version.text, "cast": cast, "assets": list(known),
            "timing": {k: v for k, v in timing(db, project).items() if k != "target"},
            "limits": {"min": m.duration.min, "max": m.duration.max,
                       "people": m.max_reference_images},
            director.NOTES_READ: list(range(1, len(notes) + 1)),
            **({"audio": track} if track else {}), **({"talker": films} if films else {}),
            **({UNITS: {"text": rows, "lines": origin, SPLIT: split}} if split else {}),
            **({"fresh": True} if not again else {})}  # fmt: skip
    return footage.with_frames(db, project, data)  # a frame of each real clip that fits, first


REMAKE = ("This video remakes the reel in <reference>. Copy it shot by shot: the same shots in "
          "the same order, each with its framing, its camera move and about its length, "
          "swapping only the brand and the cast. The lines are the script's own. A stretch the "
          "reference marks as live action is left out: the script's own ending goes "
          "there.")  # fmt: skip
LOOK_OF = ("This video is made in the look of the reel “{reel}” ({seconds:.0f} s, {shots} shots, "
           "about {pace} cuts every 10 s): its camera, light, colour and cut pace. Never its "
           "words or its story.")  # fmt: skip


def _reel(db: Session, project: Project) -> tuple[str, int | None]:
    """What a reel's video adds to the plan call: a remake's reel, shot by shot (the video's
    own reference, else its reel script's read: rule 17), or for "just its look" the reel's
    measured facts and its contact sheet to look at (routes/reel_video.look_reference). (The
    words to add, the contact sheet's file or None.)"""
    from app.models.script_library import Script, ScriptDraft
    from app.routes.reel_video import look_reference

    script = db.get(Script, project.reel_script_id) if project.reel_script_id else None
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    ref = project.reference_breakdown or (
        script.reference_breakdown if script and draft and draft.script_id == script.id else None
    )
    if ref:
        block = escape_block(prompts.reference_block(ref, project.reference_replace or ""))
        return f"\n{block}\n{REMAKE}", None
    if look := look_reference(db, project):
        sheet = look["contact_sheet_file_id"]
        said = LOOK_OF.format(reel=look["reel"], seconds=look["seconds"], shots=look["shots"],
                              pace=look["cuts_per_10_s"] or "?")  # fmt: skip
        said += " The last image given is its contact sheet." if sheet else ""
        return f"\n<look_reference>\n{escape(said)}\n</look_reference>", sheet
    return "", None


def plan_units() -> Decimal:
    """The plan call beside a usual writing call, for its estimate: 1 on the usual model,
    less on a cheaper one the site sets for it (claude.price_ratio)."""
    from app.claude import price_ratio
    from app.providers.claude import model_for

    return price_ratio(model_for(STEP))


def script_units(db: Session, project: Project, text: str) -> tuple[str, list[int]]:
    """`text` as this video's plan numbers it (`units`, by the lines its plan was given a
    sentence at a time), and each numbered row's own script line."""
    films = omni_talker.name(db, project) if omni_talker.on(db, project) else ""
    return units(text, (shooting_plan(db, project) or {}).get(SPLIT, []), films)


def reworded(db: Session, project: Project, row: BreakdownVersion, text: str) -> set[str]:
    """After the script's words changed under the same plan (the owner's Change the line):
    each spoken shot's words put in again from `text` by the plan's own numbers, never
    re-typed (rule 19). The clips whose prompt doesn't say its shots' words as they are now."""
    from sqlalchemy.orm.attributes import flag_modified

    films = omni_talker.name(db, project) if omni_talker.on(db, project) else ""
    said = spoken(script_units(db, project, text)[0], films)
    plan = (row.data.get(PLAN) or {}).get("clips") or []
    given = [s.get("line") for c in plan for s in c["shots"]]
    shots = [s for scene in row.data["scenes"] for s in scene["shots"]]
    for shot, n in zip(shots, given if len(given) == len(shots) else [], strict=False):
        if shot.get("line") and n in said:
            shot["line"] = said[n][1]
    flag_modified(row, "data")
    words = {s["id"]: s.get("line") for s in shots}
    prompts_ = {r.clip_id: r.prompt or "" for r in db.scalars(select(ProjectClip).where(
        ProjectClip.project_id == project.id))}  # fmt: skip
    return {c["id"] for c in row.data["clips"]
            if any(words.get(i) and f'"{words[i]}"' not in prompts_.get(c["id"], "")
                   for i in c["shot_ids"])}  # fmt: skip


def queue(db: Session, user: User, project: Project, run: dict) -> str:
    """Ask for the plan. Before Make it it's planning, on the video's planning allowance
    (past it, the owner's OK first); after, it's the run's own step, inside its price."""
    from app.director import NOTES_READ
    from app.routes.jobs import enqueue

    data, units = job_input(db, project, run), plan_units()
    if not run.get("ok", True):
        data, wait = asks.before_ok(db, user, project, KIND, data, units, plan=True)
    else:
        price = estimate(db, project.workspace_id, KIND, units, data)
        wait = past_approved(db, project, user, price)
    try:
        enqueue(db, user, KIND, data, project=project, provider="claude", prepaid=not wait,
                wait=wait, units=units)  # fmt: skip
    except HTTPException as no:
        db.rollback()
        return f"Refused: {no.detail}"
    return "Planning the change." if data[NOTES_READ] else "Planning the video."


def checked(job_input: dict, output: dict) -> tuple[dict, list[str]]:
    """The free check on the answer: every spoken line of the script in exactly one shot, by
    its number and in order; each clip inside what the video model makes; a line's shot long
    enough to say it; and everyone a shot shows (and everyone who speaks on camera) either in
    the cast or described in `roles`. An asset id the video doesn't have is just left out. A
    video timed to a narration or a song (`audio`) has no lines or lengths of its own to
    check: its shots are put on the track instead (one_pass_timed.snapped), and a talker's
    plan must show the talker. A presenter filmed on Omni (`talker`) says every line; a B-roll
    clip's `line` is only the line it shows. The plan, and what to fix ([] if fine)."""
    from app.cast_roles import labels, same

    plan = ShootingPlan.model_validate(output)
    limits, pace, track = job_input["limits"], job_input["timing"], job_input.get("audio")
    said = {} if track else spoken(numbered(job_input)[0], job_input.get("talker", ""))
    shows = [
        c.id for c in plan.clips if job_input.get("talker") and c.kind == one_pass_timed.BROLL
    ]  # an Omni talker's B-roll: over their voice
    for s in (s for c in plan.clips if c.id in shows for s in c.shots):
        s.line, s.how = (s.line if s.line in said else None), ""  # the line it shows, unsaid
    used = [s.line for c in plan.clips if c.id not in shows for s in c.shots
            if s.line and not track]  # fmt: skip
    want, fixes = sorted(said), []
    if missing := [n for n in want if n not in used]:
        fixes.append(f"{check._lines(missing)} in no shot")
    if twice := sorted({n for n in used if used.count(n) > 1}):
        fixes.append(f"{check._lines(twice)} in more than one shot")
    if extra := sorted({n for n in used if n not in said}):
        fixes.append(f"{check._lines(extra, 'are not spoken lines', 'is not a spoken line')}"
                     " of the script: give only a spoken line's number")  # fmt: skip
    if not (missing or twice or extra) and used != want:
        fixes.append("the lines are out of order: every line stays where the script has it")
    ids = [c.id for c in plan.clips]
    if not ids or len(set(ids)) != len(ids) or any(not re.fullmatch(r"c\d+", i) for i in ids):
        fixes.append("each clip needs its own id: c1, c2, c3, …")
    if empty := [c.id for c in plan.clips if not c.shots]:
        fixes.append(f"clip {empty[0]}: every clip has shots")
    elif track and ids:
        fixes += one_pass_timed.snapped(plan, track, limits["max"])
        if track.get("talks") and not any(c.kind == one_pass_timed.HOST for c in plan.clips):
            from app.talker import NO_SHOTS

            fixes.append(NO_SHOTS)
    known = [*job_input["cast"], *(r.name for r in plan.roles)]
    who = job_input.get("talker") or ""
    if who and not any(same(who, k) or labels(who, k) for k in known):
        # the presenter under the script's own words for them ("Dad"): the one person their
        # clips show is them (video 370 and 390: four plans in a row failed on the name)
        seen = {p for c in plan.clips if c.kind == one_pass_timed.HOST for s in c.shots
                for p in s.people}  # fmt: skip
        role = next((r for r in plan.roles if len(seen) == 1 and same(r.name, *seen)), None)
        if role:
            for s in (s for c in plan.clips for s in c.shots):
                s.people = [who if same(p, role.name) else p for p in s.people]
            for v in plan.voices:
                v.who = who if same(v.who, role.name) else v.who
            role.name = who
            known.append(who)
    people = [said[n][0] for n in used if n in said and "(" not in said[n][0]]  # on camera
    for c in plan.clips:
        c.assets = [a for a in c.assets if a in job_input["assets"]]
        seconds = sum(s.seconds for s in c.shots)
        if track or not c.shots:
            pass  # its lengths are the track's own
        elif any(s.seconds < 1 for s in c.shots):
            fixes.append(f"clip {c.id}: every clip has shots, each at least 1 whole second")
        elif not limits["min"] <= seconds <= limits["max"]:
            fixes.append(f"clip {c.id} is {seconds} s: this video model makes "
                         f"{limits['min']}–{limits['max']} s a clip")  # fmt: skip
        shown = list(dict.fromkeys(p for s in c.shots for p in s.people))
        people += shown
        if len(shown) > limits["people"]:
            fixes.append(
                f"clip {c.id} names {len(shown)} people: this video model carries "
                f"{limits['people']} pictures a clip; say the others in `extras`"
            )
        for n, s in enumerate(c.shots, 1):
            need = check.line_seconds(said[s.line][1], pace["fast"], pace["pause"]) if (
                s.line in said and c.id not in shows) else 0  # fmt: skip
            if s.seconds < need - 0.5:
                fixes.append(f"clip {c.id} shot {n}: line {s.line} needs about "
                             f"{math.ceil(need)} s, it has {s.seconds}")  # fmt: skip
    lost = [p for p in dict.fromkeys(people)
            if not any(same(p, k) or labels(p, k) for k in known)]  # fmt: skip
    if lost:
        fixes.append(f"{', '.join(lost)}: in a shot, but neither in <cast> nor in `roles`; add "
                     "each to `roles` with what to draw")  # fmt: skip
    return plan.model_dump(), fixes


def again(job_input: dict, fixes: list[str]) -> dict:
    """The one re-ask inside the same job (charged once): the same ask, with what to fix."""
    said = "\n".join(f"- {f}" for f in fixes)
    fix = f"<fix>\nYour last plan can't be used:\n{said}\nWrite the whole plan again.\n</fix>"
    return {**job_input, "prompt": f"{job_input['prompt']}\n{fix}"}


# --- Saving it into the tables the tabs read ---------------------------------------------------


def _who(db: Session, project: Project, plan: ShootingPlan, speakers: list[str]) -> dict:
    """Each person the plan's shots name (and each speaker) -> their asset id: the role or
    look the video has by that name, else a role added as the cast read adds one, with the
    plan's own words for what to draw. Someone neither described nor speaking is an extra:
    said in words, never a role."""
    from app import breakdown
    from app.cast_roles import labels, ref, same, video_slots
    from app.models.script_library import ScriptDraft
    from app.storyboard import cast_looks

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    slots = video_slots(db, project)
    looks = {i.name: f"char:{i.id}" for i in cast_looks(db, project)}
    told = {r.name: r.description.strip() for r in plan.roles}
    out: dict[str, str] = {}
    for name in dict.fromkeys([*(p for c in plan.clips for s in c.shots for p in s.people),
                               *speakers]):  # fmt: skip
        slot = (next((s for s in slots if same(name, s.role)), None)
                or next((s for s in slots if labels(name, s.role)), None))  # fmt: skip
        if slot is None and (look := next((r for n, r in looks.items() if same(name, n)), None)):
            out[name] = look
            continue
        role = next((n for n in told if same(name, n) or labels(name, n)), None)
        if slot is None and draft is not None and (role or name in speakers):
            slot = breakdown._add_role(db, project, draft, role or name)
            slots.append(slot)
        if slot is None:
            continue
        if role and not (slot.description or "").strip():
            slot.description = told[role][:2000]
        out[name] = ref(db, project, slot)
    return out


def _where(db: Session, project: Project, plan: ShootingPlan) -> dict[str, str]:
    """Each place the clips name -> its asset id: the brand's or the video's own by that name,
    else a place made for this video only (rule 12) from the plan's description, its look
    drawn with the cast's (`make_looks`)."""
    from app.cast_roles import same
    from app.routes.cast import _own
    from app.storyboard import _name

    known = _assets(db, project)
    have = {_name(known, r): r for r in known if r.startswith("place:")}
    told = {p.name: p.description.strip() for p in plan.places}
    out: dict[str, str] = {}
    for name in dict.fromkeys(c.place for c in plan.clips if c.place.strip()):
        found = next((r for n, r in have.items() if same(name, n)), None)
        described = next((n for n in told if same(name, n)), None)
        if found is None and described:
            item = _own(project, described[:120], told[described][:2000])
            db.add(item)
            db.flush()
            found = have[described] = f"place:{item.id}"
        if found:
            out[name] = found
    return out


def _structure(clip: dict) -> tuple:
    """What a clip's take shows, less its wording: its lines, shot lengths, people, place."""
    return (clip.get("place"), sorted(clip.get("assets") or []),
            [(s.get("seconds"), s.get("line"), sorted(s.get("people") or []))
             for s in clip.get("shots") or []])  # fmt: skip


def _kept(old: dict | None, new: dict, noted: str) -> dict:
    """A plan made again for a note: each clip the note leaves alone comes back as it was, so
    it isn't made again. A clip is left alone when it's the same, or when the note names other
    clips ("clip 3") and only its wording moved. The plan to save."""
    from app.revision import named

    was = {c["id"]: c for c in (old or {}).get("clips") or []}
    asked = named(noted)
    same = {c["id"] for c in new["clips"] if asked and c["id"] not in asked
            and c["id"] in was and _structure(was[c["id"]]) == _structure(c)}  # fmt: skip
    clips = [was[c["id"]] if c["id"] in same else c for c in new["clips"]]
    return {**new, "clips": clips}


def save(db: Session, job: Job) -> None:
    """The plan lands: its treatment as the chat's card (a treatment's own row, so everything
    that reads the video's story and voices reads it), its roles and places in Cast, its
    shots and clips as the newest breakdown, its scene plan approved, and each new or changed
    clip's prompt written. A clip the plan left as it was keeps its prompt and its take. All
    of it or none: a plan half written is never shown (the job then fails, uncharged)."""
    with db.begin_nested():
        _land(db, job)


def _land(db: Session, job: Job) -> None:
    from app import advice, breakdown, director, video_settings
    from app.db import utcnow

    project = db.get(Project, job.input["project_id"])
    if project is None or project.archived_at is not None:
        return
    text, run, track = job.input["script"], job.input.get(RUN) or {}, job.input.get("audio")
    before = None if job.input.get("fresh") else shooting_plan(db, project)
    noted = " ".join(m["text"] for m in director.chat(project, run.get("id")))
    told = _kept(before, ShootingPlan.model_validate(job.output).model_dump(), noted)
    plan = ShootingPlan.model_validate(told)
    films = job.input.get("talker", "")
    rows, origin = numbered(job.input)  # the script as the plan numbers it (`units`)
    said = spoken(rows, films)
    if split := (job.input.get(UNITS) or {}).get(SPLIT):
        told = {**told, SPLIT: split}  # kept with the plan: its numbers stay its own
    lines = {c.id: [s.line for s in c.shots if s.line in said] for c in plan.clips}
    spans = {c.id: sum(x.seconds for x in c.shots) for c in plan.clips}
    if track:  # a beat is its clip's stretch of the track, and the script lines heard in it
        timed = iter(one_pass_timed.spans(plan, track))
        for c in plan.clips:
            mine = [next(timed) for _ in c.shots]
            lines[c.id] = sorted(one_pass_timed.heard(track, mine[0][0], mine[-1][1]))
            spans[c.id] = max(1, round(mine[-1][1] - mine[0][0]))
    heard = {c: ns if track else list(dict.fromkeys(origin[n - 1] for n in ns))
             for c, ns in lines.items()}  # each beat's own script lines  # fmt: skip
    beats = [{"id": f"b{k}", "name": c.name, "lines": heard[c.id], "purpose": c.purpose,
              "picture": c.summary.strip().rstrip("."),
              "seconds": spans[c.id]}  # its clip's real span on the card
             for k, c in enumerate(plan.clips, 1)]  # fmt: skip
    named = director._names_reed(db, project)
    story = advice.uncited({**told["treatment"], "voices": told["voices"]}, "treatment", named)
    story["beats"] = [advice.uncited(b, "beat", named) for b in beats]
    now = utcnow()
    db.add(Job(workspace_id=project.workspace_id, created_by_id=job.created_by_id,
               kind="director_step", provider="server", credits=0, project_id=project.id,
               brand_id=project.brand_id, status=JobStatus.succeeded, started_at=now,
               finished_at=now, output=story,
               input={"step": "treatment", "project_id": project.id, RUN: run, STEP: job.id,
                      director.NOTES_READ: job.input.get(director.NOTES_READ) or []}))  # fmt: skip
    db.flush()
    speakers = [] if track else [OFF.sub("", said[n][0]) for ns in lines.values() for n in ns]
    who, where = _who(db, project, plan, speakers), _where(db, project, plan)
    bd, removed = breakdown.land(db, project, to_breakdown(
        plan, text if track else rows, who, where, track, films, origin))  # fmt: skip
    if films:  # each of the talker's clips sized to its words, on whole sentences (free)
        m = breakdown.video_model(project)
        bd, sized = omni_talker.pieces(bd, text, m.duration.min, m.duration.max)
        removed += sized
    breakdown.record_length(project, bd)
    plans._set(project, prompts.plan_from_breakdown(bd).model_dump(), STEP, job.id, text)
    plans.approve(project, job.created_by_id)
    order = [s.id for scene in bd.scenes for s in scene.shots]
    song = one_pass_timed.song_part(plan, order, track) if track else None
    if song:  # each clip as long as the model makes it (its shortest clip, cut to the track)
        from app import song_breakdown

        bd = Breakdown.model_validate(song_breakdown.fit(
            {**bd.model_dump(), "song": song}, True, song_breakdown.least(db, project.id),
            song_breakdown.most(db, project.id)))  # fmt: skip
    row = BreakdownVersion(
        project_id=project.id, script_version=job.input["script_version"], source="claude",
        job_id=job.id, created_by_id=job.created_by_id,
        data={**bd.model_dump(), **({"song": song} if song else {}), PLAN: told,
              "plan_version": project.plan["version"]},
        problems=breakdown.problems(db, project, text, bd, song, written=True)
        + removed)  # fmt: skip
    db.add(row)
    db.flush()
    video_settings.follow_lip_sync(db, project, could=True)  # no lip-sync: Sung to B-roll (VS1)
    was = {c["id"]: c for c in (before or {}).get("clips") or []}
    changed = {c["id"] for c in told["clips"] if was.get(c["id"]) != c}
    assemble(db, project, row, changed, job.id, job.created_by_id, remake=True)
    for clip in db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)):
        clip.breakdown_id = row.id  # a clip left as it was moves to the new shots as it is
    if films:
        _opening_still(db, project, row, films)
    from app import footage_shot

    footage_shot.settle(db, project, job.created_by_id)  # a real footage clip: cut, free


def _opening_still(db: Session, project: Project, row: BreakdownVersion, who: str) -> None:
    """A presenter filmed on Omni keeps ONE opening still for all their clips in one place
    (app/one_frame.py: it is what holds their room from clip to clip): the first such clip's,
    drawn once with them at rest, as the talker's own still is (talker.STILL_PROMPT); each
    later clip there opens on it (clip_prompts.assets). A still drawn for an earlier plan
    stays with its clip while the plan still has it."""
    from app import one_frame, talker
    from app.models.storyboards import StoryboardFrame

    shots = {s["id"]: (s, sc) for sc in row.data["scenes"] for s in sc["shots"]}
    follows = one_frame.followers(row.data, True, False)
    had = {f.clip_id: f for f in db.scalars(select(StoryboardFrame).where(
        StoryboardFrame.project_id == project.id))}  # fmt: skip
    for clip in row.data["clips"]:
        first, scene = shots[clip["shot_ids"][0]]
        talks = any(shots[i][0].get("line") for i in clip["shot_ids"])
        if not talks or clip["id"] in follows:
            if (old := had.get(clip["id"])) is not None:
                db.delete(old)
            continue
        if (frame := had.get(clip["id"])) is not None:
            frame.breakdown_id, frame.shot_id = row.id, first["id"]
            continue
        where = f"where the plan puts them, {scene['heading']}: {scene.get('look') or ''}"
        db.add(StoryboardFrame(
            project_id=project.id, breakdown_id=row.id, clip_id=clip["id"], shot_id=first["id"],
            look=project.look or "house", reference_ids=list(first["character_ids"]),
            prompt=talker.STILL_PROMPT.format(who=who, where=where.strip(": ")[:400])
            + one_frame.NEUTRAL))  # fmt: skip
    for clip_id in set(had) - {c["id"] for c in row.data["clips"]}:
        db.delete(had[clip_id])


# --- The run: one server step a turn ---------------------------------------------------------


def alongside(job: Job) -> bool:
    """A job the run doesn't wait for before its next step: the presenter's still and their
    one take of the whole narration, the long job, made while the B-roll is (`move`)."""
    from app import host

    return job.input.get("step") in (host.STILL, host.PIECE)


def _go(tool: str, why: str, clip_id: str | None = None, **more) -> dict:
    return {"tool": tool, "why": why, "clip_id": clip_id, "take_id": None, "note": "", **more}


def state(db: Session, project: Project, run: dict, seen: dict) -> dict:
    """What `move` reads: the video as a director's turn reads it (`seen`: director.video_state
    with its chat), and this run's own: its plan calls, its open notes, and what each clip's
    newest take's listen heard. A video timed to a track brings its song or narration as the
    director reads it (`audio`, with its `tool`)."""
    from app import audition, director, item_checks
    from app.routes.jobs import DECLINE

    busy = [j for j in director._waiting(db, project)
            if j.status != JobStatus.needs_owner_approval]  # fmt: skip
    beside = [j for j in busy if alongside(j)]
    tool = next((k for k in ("song", "narration") if seen.get(k)), None)
    row = clip_prompts.newest(db, project)
    card = db.scalar(select(Ask).where(Ask.project_id == project.id, Ask.topic == STYLE_TOPIC,
                                       Ask.state != "not_needed")
                     .order_by(Ask.id.desc()))  # fmt: skip
    hears = tool and (seen[tool].get("audition") or {}).get("state") == "none"

    mine = db.scalars(select(Job).where(
        Job.project_id == project.id, Job.input["step"].as_string() == STEP,
        Job.input[RUN]["id"].as_string() == run["id"]).order_by(Job.id)).all()  # fmt: skip
    failed = 0
    for j in mine:  # this run's plan calls that failed, since one last worked
        failed = failed + 1 if j.status == JobStatus.failed else 0
    notes = director.chat(project, run["id"])
    closed = director.answered(db, run["id"], project.id)
    kept = any(j.input.get(DECLINE) for j in mine[-1:])  # the owner kept the plan as it is
    clips = []
    for c in seen.get("clips") or []:
        last = c["takes"][-1]["id"] if c["takes"] else 0
        heard = item_checks.latest(db, "words", [last]).get(last) if last else None
        missing = [f["text"] for f in (heard.findings or []) if f.get("kind") == "missing"] if (
            heard and heard.status == "done") else []  # fmt: skip
        clips.append({"clip_id": c["clip_id"], "takes": len(c["takes"]), "missing": missing,
                      "picked": bool(c["picked_take_id"]), "talker": bool(c.get("talker")),
                      "footage": bool(c.get("footage")),
                      "rerolled": (run.get("redos") or {}).get(c["clip_id"], 0)})  # fmt: skip
    last = next((t for t in reversed(director.turns(db, project))
                 if t.input[RUN]["id"] == run["id"] and (t.output or {}).get("tool") != "wait"
                 and "result" in t.input), None)  # fmt: skip
    return {
        "audio": {**seen[tool], "tool": tool} if tool else None, "host": seen.get("host"),
        "host_busy": bool(beside), "host_tries": run.get("hosts", 0),
        "stills": (seen.get("stills") or {}).get("frames", 0) - (seen.get("stills") or {}).get(
            "drawn", 0),  # a talker's one opening still, not drawn yet
        "motion": one_pass_timed.motion(shooting_plan(db, project)),
        "voices": audition.candidates(db, project) if hears else [],
        # the take in use isn't the one the shots are timed to (a new reading since)
        "behind": bool(row and project.song_take_id and (row.data.get("song") or {}).get(
            "take_id") not in (None, project.song_take_id)),
        # a song with no style line: None (not asked yet), "" (asked), else the person's words
        "style": None if card is None else ((card.answer or {}).get("text") or ""),
        "narrations_left": (seen.get("allowed") or {}).get("narrations_left", 0),
        "planned": shooting_plan(db, project) is not None,
        "fresh": director.fresh(db, project, run)[0],
        "open_notes": [n for n in range(1, len(notes) + 1) if n not in closed] if not kept else [],
        "kept": kept, "plan_failed": failed,
        "why_failed": next((TWICE + j.error_detail.removeprefix(STILL).split("; ")[0]
                            if (j.error_detail or "").startswith(STILL)
                            else clip_prompts.cause(j.error or "", j.error_detail or "")
                            for j in reversed(mine) if j.status == JobStatus.failed), ""),
        "ok": bool(run.get("ok", True)), "hold": bool(run.get("hold")),
        "being_made": len(busy) - len(beside), "held": seen.get("held_for_owner") or [],
        "missing_looks": seen.get("missing_looks") or [],
        "cast": {k: (seen.get("cast_ok") or {}).get(k) for k in ("state", "asked", "not_ready")},
        "clips": clips, "cut": seen.get("cut", "none"),
        "edits": bool((seen.get("timeline") or {}).get("changes")),
        "cut_failed": (seen.get("cut_failed") or {}).get("why", ""),
        "watch": {k: (seen.get("watch") or {}).get(k) for k in ("state", "current")},
        "last": (last.output or {}).get("tool") if last else None,
        "refused": last.input["result"].partition("Refused: ")[2] if last else "",
    }  # fmt: skip


def move(s: dict) -> dict:
    """The run's next step, always one (the twin of `director_auto.move`, with no turn left to
    a model): the plan, then the looks, then Make it; after it the cast and places OK, then
    every clip at once; a take that misses a scripted line once more, with the same
    prompt; then the cut, one watch of it, and the delivery."""
    if s["being_made"] or s["held"]:
        return _go("wait", "What was started is still being made.")
    if sound := _audio(s):  # a narration or a song is the clock: made and timed before the plan
        return sound
    if not s["planned"] or s["open_notes"] or s["fresh"]:
        if s["plan_failed"] >= 2:
            return _go("stop", PLAN_FAILED.format(why=s["why_failed"].rstrip(". ")))
        if s["kept"]:
            return _go("stop", NOT_PLANNED)
        # never "Note N" here: a note is answered once its plan lands (`save`), not when asked
        return _go(
            "shoot_plan",
            "Your note changes the plan: only what it touches is planned again."
            if s["open_notes"]
            else "The whole video is planned in one pass.",
        )
    bare = [c for c in s["clips"] if not c["picked"]]
    stale = s["cut"] in ("none", "out of date") or s["edits"]
    if not s["ok"] and not (bare or stale or s["missing_looks"]):
        return _go("deliver", "The plan stays as it is, so nothing was made again and the cut is "
                   "as it was." if s["kept"] else "Nothing needed making again, so the cut is as "
                   "it was.")  # fmt: skip
    if s["missing_looks"] and (s["ok"] or not s["hold"]):
        return _go("make_looks", "Everyone and every place the plan shows gets a look.")
    if not s["ok"]:
        return _go(CARD, "The plan is made: Make it is the go.")
    cast = s["cast"]
    if cast["state"] == "not_ready":
        return _go("stop", NO_LOOK.format("; ".join(cast["not_ready"] or ["A look is missing"])))
    if cast["state"] == "ready":
        if not cast["asked"]:
            return _go("ask_cast_ok", "Every look is drawn: the cast and places are yours to OK.")
        return _go("wait", "The takes wait for the cast and places OK.")
    if s["stills"] and s["last"] != "stills":
        return _go("stills", "The talker's one opening still: each of their clips starts on it.")
    host = s["host"]  # a presenter's one take (in a corner, or talking in their own clips)
    if host and host["state"] in ("none", "failed") and not s["host_busy"]:
        if s["host_tries"] >= 2:
            return _go("stop", NO_HOST)
        return _go("host", "The presenter's take of the whole narration is the long job: it "
                   "starts first, and the B-roll is made beside it.", note=s["motion"])  # fmt: skip
    made = [c for c in bare if not (c["talker"] or c["footage"])]  # those need a take of their own
    if made:
        return _go("make_take", "Every clip is made at once.")
    if again := next((c for c in s["clips"] if c["missing"] and not c["rerolled"]), None):
        return _go("make_take", f"Its take didn't say a scripted line ({again['missing'][0]}): "
                   "made once more, with the same prompt.", again["clip_id"])  # fmt: skip
    if host and host["state"] != "ready":
        return _go("wait", "Every clip has its take: the presenter's own is still being made.")
    if s["cut"] != "made" or s["edits"]:
        if s["last"] == "final_cut":  # it made the cut just now, and it still isn't one
            return _go(
                "stop",
                CUT_FAILED.format(
                    (s["cut_failed"] or s["refused"] or "a clip changed since").rstrip(".")
                ),
            )
        return _go("final_cut", "Every clip has its take: the cut is made.")
    if not s["watch"]["current"]:
        return _go("watch_cut", "The cut is watched once, as a viewer meets it.")
    return _go("deliver", "The cut is made and watched.")


def _audio(s: dict) -> dict | None:
    """The run's next move on its narration or song (director_song.audio_move), or None once
    one is in use (or the video has none)."""
    from app.director_song import audio_move

    audio = s.get("audio")
    if audio is None:
        return None
    seen = {audio["tool"]: audio, "shots": "ready" if s["planned"] else "none",
            "allowed": {"narrations_left": s["narrations_left"]}}  # fmt: skip
    if audio["tool"] == "song" and audio["state"] == "none" and not audio.get("style"):
        if s["style"] is None:  # nothing says how it should sound: the person does, once
            return _go(
                "ask",
                "The song needs its style before it can be made.",
                ask={
                    "kind": "question",
                    "topic": STYLE_TOPIC,
                    "question": STYLE_ASK,
                    "why": STYLE_WHY,
                },
            )
        if not s["style"]:
            return _go("wait", "The song waits for its style.")
    step = audio_move(seen, _go, s["style"] or "", s["voices"])
    if step is None and s["behind"]:  # free: each shot moves to its time in the new take
        return _go(audio["tool"], "The shots move onto the take now in use: nothing is planned "
                   "again.", take_id=audio["used_take_id"])  # fmt: skip
    return step


def step(db: Session, project: Project, run: dict, seen: dict) -> dict:
    return move(state(db, project, run, seen))


READY_FIRST = _go("wait", "The plan is in hand: its start card is next.")
GOING = _go("wait", "Make it is pressed: the clips are next.")


def act(db: Session, job: Job, storage) -> None:
    """A one-pass run's turn, acted on: its own steps (the plan, a wait, a stop, the delivery)
    here, a site action through the director's own tools (each its button's function, with
    its price, holds and refusals). A step refused twice running stops the run, saying why."""
    from app import delivery, director, director_tools

    project = db.get(Project, job.project_id)
    move_, run = dict(job.output or {}), dict(job.input[RUN])
    tool, user = move_.get("tool"), db.get(User, job.input[RUN]["by"])
    if tool == "stop":
        director._end(job, move_["why"], result="Stopped.")
        return db.commit()
    if tool == "wait":
        cast = cast_gate.state(db, project)
        waits = cast["state"] == "ready" and cast["asked"]
        said = (director.CAST_WAIT if waits else director.ON_YOU if asks.waiting(db, project)
                else "Waiting.")  # fmt: skip  # a question parks the run until it's answered
        return director._record(db, job, run, said)
    if tool == "deliver":
        said = delivery_words(db, project, run, move_["why"])
        job.output = {**move_, **said, "note": delivery.note(db, project, job, said)}
        asks.close_run(db, run["id"], "Delivered without it.")
        director._end(job, move_["why"], result=director.DELIVERED)
        return db.commit()
    db.commit()  # the turn is kept whatever its step does
    if tool == "shoot_plan":
        result = queue(db, user, project, run)
    else:
        if tool == "make_take":  # each clip as its looks are now, free: never a paid rewrite
            from app import footage_shot

            follow(db, project, unmade=True)
            clip_prompts.repair(db, project)
            footage_shot.settle(db, project, user.id)  # a real footage clip stays as it is
            db.commit()
        result = director_tools.run(db, user, project, move_, storage, run)
    refused = result.startswith("Refused")
    if tool == "make_take" and "once more" in move_["why"] and not refused:
        clip = move_["clip_id"]
        run["redos"] = {**(run.get("redos") or {}), clip: run["redos"].get(clip, 0) + 1}
    if tool == "watch_cut" and not refused:
        run["watches"] = run.get("watches", 0) + 1
    if tool == "host" and not refused:
        run["hosts"] = run.get("hosts", 0) + 1
    before = next((t for t in reversed(director.turns(db, project)) if t.id < job.id), None)
    if refused and before is not None and (before.output or {}).get("tool") == tool and (
            before.input.get("result") or "").startswith("Refused"):  # fmt: skip
        job = db.get(Job, job.id)
        no = result.removeprefix("Refused: ")
        job.input = {**job.input, RUN: run}
        director._end(job, f"It stopped: {no}", result=f"Refused again: {no}")
        return db.commit()
    director._record(db, job, run, result)


def delivery_words(db: Session, project: Project, run: dict, why: str = "") -> dict:
    """The delivery note's own words, composed from what was made (no model writes it): what
    was made, and two or three next steps. What it cost against the price shown, what it
    redid and every known fault (each take's listen, the watch of the cut) are added by
    `delivery.note`, as on any delivery."""
    from app import director, footage_shot
    from app.director_tools import _n

    rows = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)
                      .order_by(ProjectClip.id)).all()  # fmt: skip
    first = next((t for t in director.turns(db, project) if t.input[RUN]["id"] == run["id"]), None)
    new = [r for r in rows if r.picked_take_id and first is not None
           and db.get(ClipTake, r.picked_take_id).created_at >= first.created_at]  # fmt: skip
    seconds = sum(r.seconds for r in rows)
    story = (director.treatment(db, project) or {}).get("logline", "").strip()
    if len(new) == len(rows):
        made = f"I made the whole video: {_n(len(rows), 'clip')}, {seconds} seconds. {story}"
    elif new:
        again = ", ".join(r.clip_id.removeprefix("c") for r in new)
        made = (f"I made clip{'s' * (len(new) > 1)} {again} again for your note and cut the "
                f"video again. The other clips are as they were.")  # fmt: skip
    else:
        made = why  # nothing was made: the move's own words say why
    again = [c for c, n in (run.get("redos") or {}).items() if n]
    if again:
        made += (f" Clip{'s' * (len(again) > 1)} {', '.join(c.removeprefix('c') for c in again)} "
                 "missed a scripted line on the first take, so I made it once more.")  # fmt: skip
    needs = ("Watch the cut. To change something, tell me which clip and what to change, like "
             "“Redo clip 2 with a wider shot”: only that clip is made again. To go back to an "
             "earlier take, pick it in Clips.")  # fmt: skip
    track, unsure = _track_words(db, project, rows)
    real = [r.clip_id.removeprefix("c") for r in rows if r.clip_id in footage_shot.uses(
        (clip_prompts.newest(db, project) or BreakdownVersion(data={})).data)]  # fmt: skip
    if real:
        track += (
            f" Clip{'s' * (len(real) > 1)} {', '.join(real)} "
            f"{'are' if len(real) > 1 else 'is'} the brand's own footage, cut from it."
        )
    return {"made": f"{made.strip()}{track}", "unsure": unsure, "needs": needs}


MUSIC = " Music is added in post."


def _track_words(db: Session, project: Project, rows: list[ProjectClip]) -> tuple[str, str]:
    """A timed video's own words in its delivery note: the voice and the take it runs to
    (added to what was made), and what to listen for before sharing it: a brand name the
    narration still says wrong or words it adds (director_song.still_wrong), each line whose
    time in the track was a guess, and each clip a voice was muted in (its B-roll is silent
    under the narrator). ("", "") for a video with no track."""
    from app import director_song, take_mute, voices
    from app.song_breakdown import take_for

    audio, take = director_song.state(db, project), take_for(db, project)
    if not audio or take is None:
        return "", ""
    if "style" in audio:
        made = f" It runs to take {take.number} of the song."
        if asked := sorted(check.lip_synced(plans.script(db, project).text)):
            lines = check._lines(asked, "ask", "asks")
            made += (f" {lines[:1].upper()}{lines[1:]} for lip-sync: every clip is B-roll for "
                     "now, so each shows what its line says and nobody sings on "
                     "camera.")  # fmt: skip
    else:
        saved = voices.named(db, project.workspace_id, take.voice, project.brand_id)
        name = (f"{saved.kind} voice" if saved is not None else
                f"{voices.ABOUT.get(take.voice, (take.voice,))[0]} voice")  # fmt: skip
        made = f" It runs to the narration read in the {name} (take {take.number}).{MUSIC}"
    said = [director_song.still_wrong({"narration": audio})] if "style" not in audio else []
    guessed = [x["text"] for x in (take.timing or {}).get("lines") or [] if x.get("heard") == 0]
    if guessed:
        said.append(
            f"The time of “{guessed[0]}”"
            + (f" and {len(guessed) - 1} more" * (len(guessed) > 1))
            + " in the track was a guess, so check its picture lands on it."
        )
    muted = [r.clip_id.removeprefix("c") for r in rows if r.picked_take_id
             and take_mute.spans(db.get(ClipTake, r.picked_take_id))]  # fmt: skip
    if muted:
        said.append(f"A voice was heard in clip{'s' * (len(muted) > 1)} {', '.join(muted)} and "
                    "muted: listen there.")  # fmt: skip
    return made, " ".join(x for x in said if x)


# --- Prices (section E of the plan) ------------------------------------------------------------


def _watch_units(project: Project | None, seconds: float, clips: int) -> int:
    """The watch of the cut at its most: a look a strip, the words and the facts."""
    from app import deep_watch, watch_cut

    w, _, h = ((project.aspect_ratio if project else "") or "9:16").partition(":")
    each = deep_watch.per_strip(int(w), int(h)) if w.isdigit() and h.isdigit() else 8
    frames = math.ceil(watch_cut.count_for(seconds, clips) / each)
    return frames + watch_cut.dense_for(clips) + 1 + 1 + 2  # its ending's, the sound's picture


def _work(db: Session, draft, video) -> dict:
    """What a run still has to make, each part priced as its own press prices it: the plan
    call (this run's own, as charged, once it's made), the looks at their most and at their
    usual price, a take of each clip with none, and the watch of the cut. Before the plan
    there are no clips or places to count: the script's quoted length, and a place a clip. A
    video timed to a narration or a song (`timed`): the track itself (`_audio_price`), its
    B-roll the track's own length with each clip rounded up a second, and no second take
    (nobody speaks in B-roll, so no take can miss a line)."""
    from app import director, host, music, narration, sheets, talker, talker_sound, watch_cut
    from app.clip_takes import takes_price
    from app.credits import CLIP_SECONDS_GUESS
    from app.models.script_library import Script
    from app.models.storyboards import StoryboardFrame
    from app.routes.estimate import _video, quoted_seconds
    from app.storyboard import image_model, still_credits

    script = db.get(Script, draft.script_id)
    ws = script.workspace_id
    timed = script.kind in narration.TIMED and not omni_talker.films(script, video)
    plan = estimate(db, ws, KIND, plan_units())
    place = sheets.sheet_price(db, ws)
    if video is None or video.id is None or shooting_plan(db, video) is None:
        seconds = quoted_seconds(db, draft, video)
        if script.kind == "narrated" and timed:  # its B-roll runs as long as it's read
            seconds = narration.longest(db, draft, video) + math.ceil(narration.FINAL_HOLD)
        elif timed:  # as long as the song it's timed to, else its lyrics sung slowly
            seconds = _song_seconds(db, draft, video) or music.guessed_seconds(
                check.sung_lines(draft.text or ""))  # fmt: skip
        clips = math.ceil(seconds / CLIP_SECONDS_GUESS)
        seconds += clips if timed else 0
        roles = len(sheets.roles_needing_look(db, script, video.look if video else None))
        roles += len(sheets.roles_without_a_look(db, script, draft))
        most, usual = clips * place, math.ceil(clips / 2) * place
        takes, each = _video(db, ws, seconds, video), _video(db, ws, CLIP_SECONDS_GUESS, video)
        takes += talker_sound.planned(db, video, clips)  # an Omni talker's voice, each clip
        stills = 1 if omni_talker.films(script, video) else 0  # and their one opening still
    else:
        from app.routes.project_assets import _missing, missing_copies, missing_places

        rows = db.scalars(select(ProjectClip).where(ProjectClip.project_id == video.id)).all()
        said = talker.clips(db, video)  # cut from the presenter's one take, never made
        bare = [r for r in rows if not r.picked_take_id and r.clip_id not in said]
        stills = db.scalar(select(func.count(StoryboardFrame.id)).where(
            StoryboardFrame.project_id == video.id, StoryboardFrame.file_id.is_(None)))  # fmt: skip
        seconds, clips = sum(r.seconds for r in rows), len(rows)
        roles = len(_missing(db, video)) + len(missing_copies(db, video))
        places = missing_places(db, video)
        most = sum((sheets.press_price(db, p) for p in places), Decimal(0))
        usual = sum((sheets.press_usual(db, p) for p in places), Decimal(0))
        takes = takes_price(db, video, bare)
        each = takes / len(bare) if bare else Decimal(0)
        turns = director.turns(db, video)
        run = turns[-1].input[RUN]["id"] if turns else ""
        if run and not director.over(db, run, video.id):  # this run's own calls, as charged
            mine = select(Job).where(Job.project_id == video.id, Job.status.in_(COUNTED),
                                     Job.input["step"].as_string() == STEP,
                                     Job.input[RUN]["id"].as_string() == run)  # fmt: skip
            plan = sum((j.credits for j in db.scalars(mine)), Decimal(0))
    watch = estimate(db, ws, watch_cut.KIND, Decimal(1), {})
    sound = _audio_price(db, draft, video) if timed else (Decimal(0), Decimal(0))
    if video is not None and video.id and host.on(db, video) and host.rows(db, video):
        talks = host.price(db, video)  # what of the presenter's still and take is left to make
    else:  # the still, and every second of the narration in one take
        talks = host.run_price(db, draft, narration.longest(db, draft, video), video)
    talks += stills * still_credits(db, ws, image_model(video))
    return {"plan": plan, "takes": takes, "clip": Decimal(0) if timed else each, "watch": watch,
            "host": talks,
            "again": Decimal(0) if timed else takes, "audio_most": sound[0], "audio": sound[1],
            "looks_most": roles * sheets.look_price(db, ws) + most,
            "looks_usual": roles * sheets.look_usual(db, ws) + usual,
            "watch_most": watch * _watch_units(video, seconds, clips)}  # fmt: skip


def _song_seconds(db: Session, draft, video) -> int:
    """A song video's length before its plan: the song it uses, else the version's Preferred
    one, else its newest take of these words; 0 with none yet."""
    from app import song_takes
    from app.models.songs import SongTake

    used = video is not None and video.song_take_id and db.get(SongTake, video.song_take_id)
    heard = [t for t in song_takes.takes(db, draft) if t.seconds
             and not song_takes.out_of_date(t, draft)]  # fmt: skip
    take = used or song_takes.preferred(db, draft) or (heard[-1] if heard else None)
    return math.ceil(take.seconds) if take and take.seconds else 0


def _audio_price(db: Session, draft, video) -> tuple[Decimal, Decimal]:
    """A timed video's narration or song still to make, at its most and as it usually goes:
    made once and once more (a brand name read again; `director_song.price` is one made and
    its remakes), else made once. Nothing once the video is timed to a take: it was made
    before Make it, on the planning allowance, so it is in what the video has spent and its
    start card says so (`card_words`), never charged again."""
    from app import director_song

    if video is not None and video.id and video.song_take_id:
        return Decimal(0), Decimal(0)
    one = director_song.price(db, draft) / (1 + director_song.REMAKES)
    return 2 * one, one


def card_words(db: Session, project: Project, expected: bool) -> tuple[str, Decimal]:
    """The start card's own words on a one-pass video: what its price covers (`expected`: the
    owner's estimate, else the most), and what its narration or song already cost before
    Make it, to say beside it (0: none)."""
    from app import director_song

    lines = "once more where a take misses a scripted line, " * (
        director_song.kind(db, project) is None
    )
    covers = (f"the plan, each look still to draw, every clip once, {lines}and one watch of "
              "the cut")  # fmt: skip
    anchor = select(Job.id).where(Job.project_id == project.id, Job.input[asks.START].as_boolean(),
                                  Job.status.in_(COUNTED))  # fmt: skip
    anchor = anchor.order_by(Job.id.desc()).limit(1)
    made = select(Job).where(Job.project_id == project.id, Job.status.in_(COUNTED),
                             Job.id > (db.scalar(anchor) or 0), Job.kind.in_(("speech", "music")),
                             Job.input[asks.BEFORE].as_boolean())  # fmt: skip
    sound = sum((j.credits for j in db.scalars(made)), Decimal(0))
    head = ("That's what this run will probably cost" if expected else
            "That's the most this run can charge")  # fmt: skip
    return f"{head}: {covers}.", sound


def run_price(db: Session, draft, video=None) -> Decimal:
    """A one-pass run's "up to" (rule 36): the plan call, a timed video's narration or song,
    each look still to make at its most, every clip with no take made once, and once more
    where someone speaks in it (its one re-roll), and the watch of the cut at its most. No
    watch of each take, no remakes by a watch, no director's own limit: none of them runs."""
    w = _work(db, draft, video)
    return (w["plan"] + w["audio_most"] + w["looks_most"] + w["takes"] + w["again"]
            + w["host"] + w["watch_most"])  # fmt: skip


def expected(db: Session, draft, video=None) -> Decimal:
    """What a one-pass run will probably cost: the plan, a timed video's narration or song
    made once, each look at its usual price, every clip once and one of them again (none in
    a video where nobody speaks on camera), and the watch at its usual pictures."""
    from app.routes.estimate import WATCH_LOOKS

    w = _work(db, draft, video)
    return (w["plan"] + w["audio"] + w["looks_usual"] + w["takes"] + w["clip"] + w["host"]
            + w["watch"] * WATCH_LOOKS)  # fmt: skip
