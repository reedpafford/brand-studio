"""Generating a project's clips (Seedance, one take per run) and stitching the picked takes
into the finished video (ffmpeg, free)."""

import logging
import re
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cast_gate, looks, model_map, p_video, screen_figures, video_settings
from app.advice import names, stops
from app.clip_prompts import MODERATED, assets, prompt_version
from app.credits import estimate, fits
from app.db import utcnow
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import WAITING, Job, JobStatus
from app.models.library import LibraryItem
from app.models.projects import Project
from app.references import LONG_SIDE
from app.sheets import require_cast_sheets, require_looks, require_sheet

log = logging.getLogger(__name__)
RESOLUTION = "480p"  # clips are planned at 480p; a model without it uses its own lowest
KEYS = {"image": "reference_images", "video": "reference_videos", "audio": "reference_audios"}


def take_input(db: Session, project: Project, clip: ProjectClip, note: str = "",
               drop: tuple[str, ...] = (), check: bool = True) -> dict:  # fmt: skip
    """The Seedance job for one clip: its prompt as written (it already says which picture is
    which), the project's aspect ratio, and its references by file id in the clip's order.
    `drop`: references left out for a look-alike retry ("frame:", then "char:"), each of their
    [ImageN] said in words instead and the rest renumbered (`LOOKALIKE`)."""
    from app.breakdown import would_show

    fits_model(db, project, clip)
    known = assets(db, project)
    breakdown = db.get(BreakdownVersion, clip.breakdown_id).data
    shots = next((c["shot_ids"] for c in breakdown["clips"] if c["id"] == clip.clip_id), [])
    require_cast_sheets(db, breakdown, shots, known)
    require_looks(would_show(db, project, breakdown, shots), known)
    model = model_map.of_clip(project, clip)  # its own (the director's), else the video's
    unsent = model_map.unsent(looks.drawn(project), model.id, _shots(breakdown, shots))
    drop = tuple(dict.fromkeys(drop + unsent))  # photoreal Seedance: described, not attached
    files: dict[str, list[int]] = {key: [] for key in KEYS.values()}
    exact: list[int] = []
    images = [r["id"] for r in clip.references if r["kind"] == "image"]  # never a logo as a chart
    prompt = _in_words(db, clip.prompt, images, drop, known) if drop else clip.prompt
    images = [i for i in images if not i.startswith(drop)] if drop else images
    for ref in clip.references:
        if drop and ref["id"].startswith(drop):
            continue
        if ref["id"] not in known:
            raise HTTPException(
                409, "A picture on this clip is no longer part of this video. Edit the prompt."
            )
        _, kind, file_ids = known[ref["id"]]
        if not file_ids and ref["id"].startswith(("char:", "place:")):
            require_sheet(db.get(LibraryItem, int(ref["id"].split(":")[1])))
        if not file_ids:
            name = names(known).get(ref["id"], "A picture on this clip")
            raise HTTPException(422, f"{name} has no picture yet. Add one in Cast & places.")
        files[KEYS[kind]].append(file_ids[0])
        if ref["id"].startswith(("screen:", "prop:")):
            exact.append(file_ids[0])  # Reed: screens and products show exactly, never lossy
    attached = [r["id"] for r in clip.references or []]
    shown = cast_gate.refs(db, project, breakdown, shots, attached, known)
    if check:  # then the cast and places OK (a price read needs none)
        require_speakers(db, project, clip, _shots(breakdown, shots))
        cast_gate.require(db, project, shown, known)
    resolution = model_map.resolution(model)
    speaks = on_camera_speech(db, project, clip, _shots(breakdown, shots))
    own = not speaks and own_sound(db, project, clip)
    take, sent = p_video.fit(model.id, {
        "prompt": _with_note(in_english(prompt), note),
        "duration": clip.seconds,
        "resolution": resolution,
        "aspect_ratio": project.aspect_ratio,
        "generate_audio": speaks or own,
    }, {k: v for k, v in files.items() if v})  # fmt: skip
    take, sent = model_map.fit(model, take, sent)  # Omni: its own inputs
    return {
        "step": "clip_take",
        "project_id": project.id,
        "project_clip_id": clip.id,
        "clip_prompt": clip.prompt,  # kept with the take, so picking it back restores it
        **({OWN_SOUND: True} if own else {}),  # its sound is its room and effects, no line
        **({"note": note} if note else {}),  # its Redo note, kept for a look-alike's retries
        "model": model.id,
        "made_with": {  # VS1: what the take is made with; OR3: its prompt's version
            **video_settings.made_with(
                db, project, images, model.id, (clip.song_slice or {}).get("sung_shots")
            ),
            **({"prompt_version": v} if (v := prompt_version(clip)) else {}),
            "cast": cast_gate.stamp(
                db, project, shown, known
            ),  # as approved: a change makes it old
        },
        "brand_id": project.brand_id,
        "fit_images_to": LONG_SIDE[resolution],
        "exact_file_ids": exact,
        "input": take,
        "files": sent,
        "screen_figures": screen_figures.for_job(
            db, [r["id"] for r in clip.references], _shots(breakdown, shots)
        ),
    }


LOOKALIKE = ("frame:", "char:")  # left out in turn when a take is refused as a look-alike


def _in_words(db: Session, prompt: str, images: list[str], drop: tuple[str, ...],
              known: dict) -> str:  # fmt: skip
    """A clip prompt with its dropped pictures said in words: a character's [ImageN] becomes
    their name and sheet description, the opening still "the opening shot"; the pictures it
    keeps are numbered again in order."""
    from app.clip_prompts import TAGS_N

    kept = [i for i in images if not i.startswith(drop)]
    said = names(known)

    def word(m: re.Match) -> str:
        n = int(m.group(1))
        if not 1 <= n <= len(images):
            return m.group(0)
        ref = images[n - 1]
        if ref in kept:
            return f"[Image{kept.index(ref) + 1}]"
        if ref.startswith("char:"):
            item = db.get(LibraryItem, int(ref.split(":")[1]))
            told = (item.notes or item.short_description or "").strip() if item else ""
            who = said.get(ref) or (item.name if item else "the character")
            return f"{who} ({told.rstrip('.')})" if told else who
        return "the opening shot"

    return TAGS_N.sub(word, prompt)


def _shots(breakdown: dict, ids: list[str]) -> list[dict]:
    by_id = {s["id"]: s for scene in breakdown["scenes"] for s in scene["shots"]}
    return [by_id[i] for i in ids if i in by_id]


VOICE_OVER = re.compile(r"v\.?o\b|narrator|voice-?over|off.?screen", re.I)  # a speaker nobody sees


def on_camera_speech(db: Session, project: Project, clip: ProjectClip, shots: list[dict]) -> bool:
    """Whether someone speaks or sings on camera in this clip, so its take keeps sound (Reed,
    3 Nov: B-roll won't all need sound; sound effects are added on request afterwards). A
    narrated video's clips and a song's B-roll shots are silent; a song's sung shots and a
    story's spoken lines are not."""
    from app.narration import video_kind

    kind = video_kind(db, project)
    if kind == "narrated":
        return False
    if kind == "song" or clip.song_slice:
        return bool((clip.song_slice or {}).get("sung_shots"))
    return any(s.get("line") and s.get("speaker") and not VOICE_OVER.search(s["speaker"])
               for s in shots)  # fmt: skip


NO_SHEET = ("{who} speaks on camera in this clip, but no one in its shots has a character "
            "sheet, so every take would invent their face. Give them a look first in Cast (an "
            "approved still of them can be their picture), then add them to these shots. "
            "Nothing was charged.")  # fmt: skip
LABELLED_OFF = re.compile(r"^\s*[^:]{1,60}\([^)]*\)\s*:")  # "MOM (O.S.):": heard, maybe unseen


def require_speakers(db: Session, project: Project, clip: ProjectClip, shots: list[dict]) -> None:
    """Someone speaks on camera in the clip, so a character sheet reaches it: a clip whose
    shots list nobody and that attaches no sheet has nothing to hold the speaker's face (video
    233: Maya's look never reached a shot, and each clip's first frame made its own Maya,
    three faces in 17 s). Refused before any charge. A line the script labels with a
    parenthetical ("(O.S.)", "(ON PHONE)") may be heard over an empty frame: left alone."""
    if (any(s.get("character_ids") for s in shots) or not on_camera_speech(db, project, clip, shots)
            or any(r["id"].startswith("char:") for r in clip.references or [])):  # fmt: skip
        return
    from app.cast_roles import labels, video_slots
    from app.routes.scripts import latest
    from app.storyboard import cast_looks

    words = latest(db, project)
    lines = words.text.splitlines() if words else []
    cast = [s.role for s in video_slots(db, project)] + [i.name for i in cast_looks(db, project)]
    for s in shots:
        said = [lines[n - 1] for n in s.get("script_lines") or [] if 0 < n <= len(lines)]
        if (s.get("line") and s.get("speaker") and not VOICE_OVER.search(s["speaker"])
                and any(labels(s["speaker"], c) for c in cast)  # one of this video's characters
                and not any(LABELLED_OFF.match(x) for x in said)):  # fmt: skip
            who = s["speaker"].strip().title() if s["speaker"].isupper() else s["speaker"].strip()
            raise HTTPException(409, NO_SHEET.format(who=who))


OWN_SOUND = "own_sound"  # in a take's job input: made with its own sound, though nobody speaks
QUIET = re.compile(r"^Audio: no one speaks \(no voices, narration or dialogue\), only silence\b")


def own_sound(db: Session, project: Project, clip: ProjectClip) -> bool:
    """A story video's clip with no line is made with its own sound: the room and the effects
    its prompt writes (226: the wind, the bouquet's thump, the car and the ding were written,
    then made silent, so its last 14 s were digital silence). A story's cut plays its takes'
    own sound, so a silent take is a silent stretch. The clip prompt writes that sound from the
    style's guide, and "only silence" where the guide wants the shot silent; a narrated or song
    video's B-roll stays silent under its voice (sound effects there are `add_sound`'s)."""
    from app import plans

    if clip.song_slice or plans.fmt(db, project) != "dialogue":
        return False
    return not QUIET.match((clip.prompt or "").lstrip())


def fits_model(db: Session, project: Project, clip: ProjectClip) -> None:
    """A clip longer than the video model makes is refused before any charge (QA #1013),
    never sent cut short: the breakdown's Split fix makes it into clips it can, between its
    shots and at its sentence breaks. One sentence can't be split: it's made shorter, or the
    video's model one that makes longer clips. A UGC
    talker's clip is never made: it's cut from the talker's take (app/talker.py)."""
    from app import talker

    if talker.says(db, project, clip):
        raise HTTPException(409, talker.SAID)
    m = model_map.of_clip(project, clip)
    most = m.fixed_seconds or m.duration.max
    if clip.seconds <= most:
        return
    from app import breakdown_fix, plans

    bd = db.get(BreakdownVersion, clip.breakdown_id or 0)
    version = plans.script(db, project)
    lo = m.duration.min if m.duration else 1  # Omni has one fixed length, no range
    parts = breakdown_fix.split_into(bd.data, version.text if version else "", clip.clip_id,
                                     lo, most) if bd else 1  # fmt: skip
    offered = bd is not None and clip.clip_id in breakdown_fix.too_long(bd.problems or [])
    then = ("Split it in the breakdown (free), then make it" if parts > 1 and offered else
            "Make its shot shorter in the breakdown, or switch the video model in Settings to "
            "one that makes longer clips (free)")  # fmt: skip
    raise HTTPException(409, f"This clip is {clip.seconds} s, but {m.name} makes at most "
                        f"{most} s a clip. {then}. Nothing was charged.")  # fmt: skip


ENGLISH = ("Language: every spoken line is in American English, and any text on screen is in "
           "English.")  # fmt: skip
SAID_AMERICAN = "every spoken line is in American English"  # the clip prompt's own (the Director)


def in_english(prompt: str) -> str:
    """Every take is asked for in English (Reed, 2026-10-27: takes came out in another language
    after "Change this…"): one fixed line right after the References line, so the prompt still
    opens and closes on the same audio line. Free; the saved prompt is unchanged."""
    lines = prompt.splitlines()
    if ENGLISH in lines or SAID_AMERICAN in prompt:  # said once, in American English (Reed)
        return prompt
    at = next((i for i, x in enumerate(lines) if x.startswith("References: ")), 0)
    return "\n".join([*lines[: at + 1], ENGLISH, *lines[at + 1 :]])


BUSY = ("The video service was busy and couldn't finish this. Nothing was charged; press {} "
        "to try again.")  # fmt: skip
REFUSED = "The video model thinks this clip looks too much like someone else's character or video."


SENSITIVE = ("The video model flagged this take as sensitive. Nothing was charged. Its check is "
             "a little random, so making it again may pass; if it keeps failing, change the "
             "wording.")  # fmt: skip


def moderated(detail: str) -> str:
    """What the video model's content check read a take as: the prompt refused ("flagged for:
    sexual", ContentModerationError), or "sensitive" for E005's "flagged as sensitive" (a
    take, at random); "" when it didn't refuse it that way. Seedance's copyright E005 says
    what to do itself."""
    if "copyright" in detail.lower():
        return ""
    if said := re.search(r"flagged for:?\s*([a-z][a-z ,/-]*[a-z])", detail, re.I):
        return said.group(1).lower()
    if "ContentModeration" in detail:
        return "unsafe content"
    return "sensitive" if re.search(r"flagged as sensitive|E005", detail, re.I) else ""


def refused(db: Session, job: Job) -> None:
    """Seedance's copyright refusal ("…may be related to copyright restrictions") in plain
    words with a next step (rules 4 and 22), never "Ask the owner". Refused takes aren't
    counted (credits.COUNTED), so nothing is charged. A busy service ("Service is temporarily
    unavailable") says to try again (Producer, rule 22)."""
    row = db.get(ProjectClip, job.input.get("project_clip_id") or 0)
    if re.search(r"service is (temporarily|currently) unavailable", job.error_detail or "", re.I):
        took = row and db.scalar(select(ClipTake.id).where(ClipTake.clip_id == row.id).limit(1))
        job.error = BUSY.format("Make another take" if took else "Make clip")  # its button
        return
    if term := moderated(job.error_detail or ""):  # Reed's c4: "flagged for: sexual", 4 times
        job.error = (
            f"{MODERATED}{term}. Nothing was charged. Change the wording, then make it again."
        )
        if term == "sensitive":  # at random: make it again, or reword it once it keeps failing
            job.error = SENSITIVE
            videos = select(Job).where(Job.project_id == job.project_id, Job.kind == "video",
                                       Job.id < job.id).order_by(Job.id.desc())  # fmt: skip
            last = row and next((j for j in db.scalars(videos)
                                 if j.input.get("project_clip_id") == row.id), None)  # fmt: skip
            if not last or last.error != SENSITIVE:
                return
        if row and row.prompt == job.input.get("clip_prompt"):  # the prompt it was made from
            said = (f"{MODERATED}{term}. Keep the story and the spoken lines; remove what "
                    f"reads as {term}.")  # fmt: skip
            row.problems = [p for p in row.problems or [] if not p.startswith(MODERATED)] + [said]
            row.free_fix_used = False  # Fix this clip's prompt rewords it, free, once per refusal
        return
    if "copyright" not in (job.error_detail or "").lower():
        return
    char = next((r["id"] for r in (row.references if row else None) or []
                 if r["id"].startswith("char:")), None)  # fmt: skip
    item = db.get(LibraryItem, int(char.split(":")[1])) if char else None
    lead = item.name if item else "the main character"
    job.error = (f"{REFUSED} Try another look for {lead}, or use Change this… on the opening "
                 "shot. Nothing was charged.")  # fmt: skip


BUSY_SAID = re.compile(r"service is (temporarily|currently) unavailable|^No answer within", re.I)
RETRY_WAIT = timedelta(seconds=30)  # a busy service gets a moment before the one retry


def why_failed(job: Job) -> str:
    """ "busy" (the service was busy or didn't answer), "refused" (its content check or
    copyright refusal: never charged), or "" for anything else."""
    detail = job.error_detail or ""
    if BUSY_SAID.search(detail):
        return "busy"
    return "refused" if moderated(detail) or "copyright" in detail.lower() else ""


def retry(db: Session, job: Job) -> None:
    """P3 (flows.md 1b): a take refused or not finished because the service was busy is
    tried again once on its own. A busy service gets a short wait; a refusal read as
    something ("flagged for: sexual") is reworded first by the free fix, then retried
    (`after_fix`). A look-alike refusal steps down instead (`_again_without`: without the
    still, then without the sheets). No other second automatic retry, never on a video
    that's gone, and never past the video's limit, budget or the editor's week. The failed
    take isn't counted, so the credits are held once and come back if the retry fails too."""
    from app.clip_prompts import fix_job, is_stale, newest

    why = why_failed(job)
    if not why or job.input.get("discard") or not job.project_id:
        return
    if _lookalike(job):
        return _again_without(db, job)
    if job.auto:  # one automatic retry, but for a look-alike's steps
        return
    if db.scalar(select(Job.id).where(Job.retry_of_id == job.id)):
        return
    project = db.get(Project, job.project_id)
    row = db.get(ProjectClip, job.input.get("project_clip_id") or 0)
    if not row or project.archived_at is not None or row.prompt != job.input.get("clip_prompt"):
        return
    term = moderated(job.error_detail or "")
    if why == "refused" and term and term != "sensitive":
        if row.free_fix_used or is_stale(db, row, newest(db, project)):
            return
        user = db.get(User, job.created_by_id)
        fix = fix_job(db, user, project, row, stops(row))
        fix.input = {**fix.input, "then_take": job.id}
        row.free_fix_used = True
        return
    _again(db, job, job.input, wait=why == "busy")


def _lookalike(job: Job) -> bool:
    return "copyright" in (job.error_detail or "").lower() and not job.input.get("discard")


def _again_without(db: Session, job: Job) -> None:
    """A take refused as a look-alike (Seedance's copyright check, the Producer): made again
    without the opening still, then without the sheets, the characters said in words, its Redo
    note kept; after that it stops and says so plainly. A refused take isn't charged: only the
    one that's made counts, against the cap and the price like any take."""
    step = job.input.get("lookalike", 0)
    project = db.get(Project, job.project_id)
    row = db.get(ProjectClip, job.input.get("project_clip_id") or 0)
    if step >= len(LOOKALIKE) or not row or project.archived_at is not None:
        if step >= len(LOOKALIKE):
            job.error = GAVE_UP
        return
    if db.scalar(select(Job.id).where(Job.retry_of_id == job.id)):
        return
    try:
        data = take_input(db, project, row, job.input.get("note", ""), drop=LOOKALIKE[: step + 1])
    except HTTPException as exc:
        log.info("clip %s: no look-alike retry: %s", row.id, exc.detail)
        return
    from app.routes.jobs import BY_DIRECTOR

    mark = {BY_DIRECTOR: True} if job.input.get(BY_DIRECTOR) else {}  # the director's still
    _again(db, job, {**data, "lookalike": step + 1, **mark}, wait=False)


GAVE_UP = (
    "The video model kept refusing this clip as looking like someone else's character, even "
    "with the characters described in words. Change the character's look (the hair, the "
    "outfit) or the opening shot, then make it again. Nothing was charged."
)


def after_fix(db: Session, row: ProjectClip, failed_id: int) -> None:
    """The free rewording of a refused take landed: its one retry, from the new prompt, if
    nothing else stops it."""
    failed = db.get(Job, failed_id)
    project = db.get(Project, row.project_id)
    if not failed or stops(row) or project.archived_at is not None:
        return
    if db.scalar(select(Job.id).where(Job.retry_of_id == failed.id)):
        return
    try:
        again = take_input(db, project, row)
    except HTTPException as exc:  # e.g. a look unapproved since: the editor decides
        log.info("clip %s: no automatic retry: %s", row.id, exc.detail)
        return
    _again(db, failed, again, wait=False)


def once_more(db: Session, job: Job) -> None:
    """A failed host still or piece, or a take's added sound: tried again once on its own
    (never charged twice); after that Make again makes it (rule 22)."""
    if job.auto or db.scalar(select(Job.id).where(Job.retry_of_id == job.id)):
        return
    _again(db, job, job.input, wait=bool(BUSY_SAID.search(job.error_detail or "")))


def _again(db: Session, job: Job, data: dict, wait: bool) -> None:
    project = db.get(Project, job.project_id)
    user = db.get(User, job.created_by_id)
    if not user or fits(db, project, user, job.credits):
        return  # it would go over: nothing more runs on its own
    if wait:
        data = {**data, "wait_until": (utcnow() + RETRY_WAIT).isoformat()}
    db.add(Job(workspace_id=job.workspace_id, created_by_id=job.created_by_id, kind=job.kind,
               provider=job.provider, input=data, project_id=job.project_id,
               brand_id=job.brand_id, credits=job.credits, approved_by_id=job.approved_by_id,
               status="queued", retry_of_id=job.id, auto=True))  # fmt: skip
    db.flush()


def retried(db: Session, row: ProjectClip) -> str | None:
    """Why the clip's newest take came from an automatic retry ("refused" or "busy"); None
    once a person has made a newer take."""
    query = select(ClipTake).where(ClipTake.clip_id == row.id).order_by(ClipTake.number.desc())
    take = db.scalar(query.limit(1))
    job = db.get(Job, take.job_id) if take else None
    return (why_failed(db.get(Job, job.retry_of_id)) or None) if job and job.auto else None


def still_wanted(db: Session, job: Job) -> bool:
    """An automatic retry still fits its clip when it starts: the video isn't archived and the
    prompt is the one it was made from (Flow-QA: an edit during a busy wait)."""
    row = db.get(ProjectClip, job.input.get("project_clip_id") or 0)
    project = db.get(Project, job.project_id) if job.project_id else None
    if row is None and job.input.get("step") in ("host_still", "host_piece", "take_sound"):
        return bool(project and project.archived_at is None)  # not a take: only its video
    return bool(row and project and project.archived_at is None
                and row.prompt == job.input.get("clip_prompt"))  # fmt: skip


def retrying(db: Session, row: ProjectClip) -> str | None:
    """Why this clip's take is being tried again on its own ("refused" or "busy"), while it is."""
    jobs = db.scalars(select(Job).where(Job.project_id == row.project_id, Job.status.in_(WAITING)))
    for j in jobs:
        if j.auto and j.input.get("project_clip_id") == row.id and still_wanted(db, j):
            return why_failed(db.get(Job, j.retry_of_id)) or None
        if j.input.get("then_take") and j.input.get("clip_ids") == [row.clip_id]:
            return "refused"
    return None


def take_warning(db: Session, row: ProjectClip) -> str | None:
    """Said before the next take is paid for, once its last two takes were both refused that
    way (Kel retried 7 times)."""
    videos = select(Job).where(Job.project_id == row.project_id, Job.kind == "video")
    last = [j for j in db.scalars(videos.order_by(Job.id.desc()))
            if j.input.get("project_clip_id") == row.id][:2]  # fmt: skip
    if len(last) == 2 and all(
        j.status == JobStatus.failed and (j.error or "").startswith(REFUSED) for j in last
    ):
        return ("The last two takes of this clip were refused: the video model thought they "
                "looked too much like someone else's character or video. Change the look or "
                "the opening shot first, or this take may be refused too.")  # fmt: skip
    return None


# A note that takes away or swaps something ("no phone", "without the hat", "instead of the
# car"): the thing it names, to look for in the prompt (226 c4, A7 in session 35's costs)
TAKES_AWAY = re.compile(
    r"\b(?:no|without|remove|replace|instead of)\s+"  # never "not": "not wide enough"
    r"(?:the |a |an |any |his |her |their |its )?([a-z][a-z-]{2,})",
    re.I,
)


def contradicts(prompt: str, note: str) -> bool:
    """A redo note that takes away or swaps something the clip's prompt shows: appended under
    the prompt, both would stand ("phone lighting up in his hand", then "no phone"), so the
    prompt is rewritten with it instead (Change it…)."""
    words = set(re.findall(r"[a-z-]+", (prompt or "").lower()))
    found = [m[1].lower() for m in TAKES_AWAY.finditer(note or "")]
    return any(w in words or w.removesuffix("s") in words or f"{w}s" in words for w in found)


def _with_note(prompt: str, note: str) -> str:
    """A Redo note ("what's wrong") goes into this take only, before the closing audio line
    so the prompt still opens and closes on the same line."""
    if not note:
        return prompt
    lines = prompt.rstrip().splitlines()
    keep = "The spoken lines stay exactly as written above; nobody else speaks."
    return "\n".join([*lines[:-1], f"Change from the last take: {note} {keep}", lines[-1]])


def take_credits(db: Session, project: Project, clip: ProjectClip) -> Decimal:
    """What one more take costs: the estimate `enqueue` charges, and the director's watch of
    it that rides along while watches are on (`take_watch.rides`)."""
    from app import take_watch

    m = model_map.of_clip(project, clip)
    job = {"model": m.id, "input": {"resolution": model_map.resolution(m)}}
    units = Decimal(model_map.seconds(m, clip.seconds))  # Omni: its fixed length
    take = estimate(db, project.workspace_id, "video", units, job)
    return take + take_watch.rides(db, project, clip)


def save_take(db: Session, job: Job) -> None:
    """A new take: numbered, and picked (the newest take is picked when it arrives)."""
    clip = db.get(ProjectClip, job.input["project_clip_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if not clip or not file_ids:
        return
    count = db.scalar(select(func.count(ClipTake.id)).where(ClipTake.clip_id == clip.id))
    take = ClipTake(clip_id=clip.id, number=count + 1, job_id=job.id, file_id=file_ids[0],
                    prompt=job.input.get("clip_prompt"),
                    look=looks.drawn(db.get(Project, clip.project_id)),
                    made_with=job.input.get("made_with") or {})  # fmt: skip
    db.add(take)
    db.flush()
    # The prompt was edited while this take was being made (Reed, rule 21): the take is used,
    # read as "Out of date", and the edit stays in hand; it's never put back, nor a take bought.
    edited = (take.made_with or {}).get("prompt_version") not in (None, prompt_version(clip))
    pick(clip, take, keep_prompt=edited)
    from app import take_watch  # rule 11: the director watches and hears it as it lands

    take_watch.queue_safely(db, job, take, clip)


def pick(clip: ProjectClip, take: ClipTake, keep_prompt: bool = False) -> None:
    """Use this take; its prompt comes back with it (Undo of a change note), unless the
    prompt in hand is to stay (`keep_prompt`: edited while the take was being made)."""
    clip.picked_take_id, clip.file_id, clip.approved = take.id, take.file_id, False
    if keep_prompt:
        return
    if take.prompt is not None:
        clip.prompt = take.prompt
    v = (take.made_with or {}).get("prompt_version")  # OR3: its version is the one in hand
    if back := [e for e in clip.prompt_history or [] if e["v"] == v]:
        clip.prompt_history = [back[0], *(e for e in clip.prompt_history if e["v"] != v)]
