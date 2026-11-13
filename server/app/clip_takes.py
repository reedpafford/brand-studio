"""Generating a project's clips (Seedance, one take per run) and stitching the picked takes
into the finished video (ffmpeg, free)."""

import logging
import math
import re
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cast_gate, looks, model_map, p_video, screen_figures, video_settings, voice_carry
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
from app.sheets import require_cast_sheets, require_looks, require_sheet, seedream_drew

log = logging.getLogger(__name__)
RESOLUTION = "480p"  # clips are planned at 480p; a model without it uses its own lowest
KEYS = {"image": "reference_images", "video": "reference_videos", "audio": "reference_audios"}


def take_input(db: Session, project: Project, clip: ProjectClip, note: str = "",
               drop: tuple[str, ...] = (), check: bool = True) -> dict:  # fmt: skip
    """The Seedance job for one clip: its prompt as written (it already says which picture is
    which), the project's aspect ratio, and its references by file id in the clip's order.
    `drop`: references left out for a look-alike retry ("frame:", then "char:"), each of their
    [ImageN] said in words instead and the rest renumbered (`LOOKALIKE`)."""
    from app import footage_shot, one_pass
    from app.breakdown import would_show

    if footage_shot.of_clip(db, clip):  # cut from the brand's real clip, never made
        raise HTTPException(409, footage_shot.NOT_MADE)
    fits_model(db, project, clip)
    known = assets(db, project)
    breakdown = db.get(BreakdownVersion, clip.breakdown_id).data
    shots = next((c["shot_ids"] for c in breakdown["clips"] if c["id"] == clip.clip_id), [])
    require_cast_sheets(db, breakdown, shots, known)
    require_looks(would_show(db, project, breakdown, shots), known)
    model = model_map.of_clip(project, clip)  # its own (the director's), else the video's
    images = [r["id"] for r in clip.references if r["kind"] == "image"]  # never a logo as a chart
    drawn = seedream_drew(db, known, images) if model.provider == "kie" else ()
    unsent = model_map.left_out(looks.drawn(project), model.id, _shots(breakdown, shots), images,
                                drawn)  # fmt: skip
    drop = tuple(dict.fromkeys(drop + unsent))  # photoreal Seedance: described, not attached
    if one_pass.on(project):  # a picture since deleted from the brand (a product photo, a real
        # clip) is left out, its own sentence gone, never the old file and never a refusal
        # with no way on (Reed, 13 Nov: deleting or updating an image must be read)
        drop += tuple(r["id"] for r in clip.references if r["id"] not in known)
    if real_refused(db, clip):  # a sheet of this clip's taken for a real person: never sent again
        drop = tuple(dict.fromkeys(drop + LOOKALIKE))
    files: dict[str, list[int]] = {key: [] for key in (*KEYS.values(), "image")}
    exact: list[int] = []
    # A one-pass clip's own start frame (a talker's opening still, the last frame of the clip
    # before it) is sent as the model's start frame, alone: it already shows who and where
    # (Reed, 11 Nov: "If he is meant to have a hat, the starting frame should have a hat")
    start = next((i for i in images if i.startswith("frame:") and not _out(i, drop)), None) if (
        model.first_frame and one_pass.on(project)) else None  # fmt: skip
    prompt = clip.prompt
    if start:  # its other pictures are never sent: not "an older look" of them after (`UNSENT`)
        unsent += tuple(i for i in images if i != start)
        drop = tuple(dict.fromkeys(drop + unsent))
        prompt = "\n".join(x for x in prompt.splitlines()
                           if not x.startswith(("References:", "Keep:")))  # fmt: skip
    prompt = _in_words(db, prompt, images, drop, known) if drop else prompt
    images = [i for i in images if not _out(i, drop)]
    for ref in clip.references:
        if _out(ref["id"], drop) or (ref["kind"] == "video" and files[KEYS["video"]]):
            continue  # one reference video a take (the brand's real clip, app/footage.py)
        if ref["id"] not in known:
            raise HTTPException(
                409, "A picture on this clip is no longer part of this video. Edit the prompt."
            )
        _, kind, file_ids = known[ref["id"]]
        if not file_ids and ref["id"].startswith(("char:", "place:")):
            require_sheet(db.get(LibraryItem, int(ref["id"].split(":")[1])))
        if not file_ids:
            name = names(known).get(ref["id"], "A picture on this clip")
            where = ("the brand's library, under Products (a photo, or the app's screens)"
                     if ref["id"].startswith("prop:") else "Cast & places")  # fmt: skip
            raise HTTPException(422, f"{name} has no picture yet. Add one in {where}.")
        files["image" if ref["id"] == start else KEYS[kind]].append(file_ids[0])
        if ref["id"].startswith(("screen:", "prop:")):
            exact.append(file_ids[0])  # Reed: screens and products show exactly, never lossy
    attached = [r["id"] for r in clip.references or []]
    shown = cast_gate.refs(db, project, breakdown, shots, attached, known)
    if check:  # then the cast and places OK (a price read needs none)
        require_speakers(db, project, clip, _shots(breakdown, shots), breakdown, known)
        cast_gate.require(db, project, shown, known)
    resolution = model_map.resolution(model)
    speaks = on_camera_speech(db, project, clip, _shots(breakdown, shots))
    own = not speaks and own_sound(db, project, clip)
    take, sent = p_video.fit(model.id, {
        "prompt": _with_note(in_english(prompt), note),
        "duration": model_map.billed(model, clip.seconds),  # as charged and recorded
        "resolution": resolution,
        "aspect_ratio": project.aspect_ratio,
        "generate_audio": speaks or own,
    }, {k: v for k, v in files.items() if v})  # fmt: skip
    take, sent = model_map.fit(model, take, sent)  # Omni: its own inputs
    if voice_carry.hears(model):  # each speaker's voice from an earlier clip, when it's kept
        voice_carry.send(db, project, _shots(breakdown, shots), take, sent)
    if check:  # never a take its model refuses for its length (a 422, video 245)
        fits_prompt(db, project, clip, model, take.get("prompt") or "", note)
        not_again(db, clip, model.id, take, sent)
    return {
        "step": "clip_take",
        UNSENT: list(unsent),  # said in words, never sent (`clip_prompts.older_take`)
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


def real_refused(db: Session, clip: ProjectClip) -> bool:
    """A take of this clip was refused for a sheet that "may contain real person": its takes
    carry no still and no sheets from then on, and are never "from an older look" for it."""
    return bool(db.scalar(select(Job.id).where(
        Job.project_id == clip.project_id, Job.status == JobStatus.failed,
        Job.input["project_clip_id"].as_integer() == clip.id,
        Job.error_detail.ilike(f"%{REAL}%")).limit(1)))  # fmt: skip


def _out(ref: str, drop: tuple[str, ...]) -> bool:
    """The reference is left out: a kind ("char:") or that one reference ("char:12")."""
    return any(ref == d or (d.endswith(":") and ref.startswith(d)) for d in drop)


# A picture's own sentence in a clip prompt's References line (clip_prompts.md): the opening
# still's two ("[Image1] is the first frame. It sets…"), a place's one ("[Image4] is the lot.")
SAYS_WHAT = re.compile(
    r"\[Image(\d+)\] is (?:the first frame\.(?:\s*It sets[^.]*\.)?|[^.\[]*\.)\s*"
)


def _in_words(db: Session, prompt: str, images: list[str], drop: tuple[str, ...],
              known: dict) -> str:  # fmt: skip
    """A clip prompt with its dropped pictures said in words: a character's [ImageN] becomes
    their name, with their sheet description the first time; a dropped opening still's or
    place's own sentences ("[Image1] is the first frame. It sets…", "[Image4] is the lot.") go,
    and any other mention is the place's name or "the opening shot"; the pictures it keeps are
    numbered again."""
    from app.clip_prompts import TAGS_N

    kept = [i for i in images if not _out(i, drop)]
    said, told_of = names(known), set()

    def unsaid(m: re.Match) -> str:
        n = int(m.group(1))
        gone = 1 <= n <= len(images) and images[n - 1] not in kept
        ref = images[n - 1] if gone else ""
        return "" if gone and (ref.startswith(("frame:", "place:")) or ref not in known) else (
            m.group(0))  # fmt: skip

    prompt = SAYS_WHAT.sub(unsaid, prompt)

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
            first = ref not in told_of  # described once: each later mention is their name
            told_of.add(ref)  # (392's c3: said at every mention, it ran past Seedance's limit)
            return f"{who} ({told.rstrip('.')})" if told and first else who
        if ref.startswith("place:"):
            return said.get(ref) or "the place"
        return "the opening shot" if ref.startswith("frame:") else said.get(ref) or "it"

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


NO_SHEET = ("{who} speaks on camera in this clip, but their character sheet is in no shot of "
            "this video, so every take would invent their face. Give them a look in Cast (an "
            "approved still of them can be their picture), then plan the shots again. Nothing "
            "was charged.")  # fmt: skip
LABELLED_OFF = re.compile(r"^\s*[^:]{1,60}\([^)]*\)\s*:")  # "MOM (O.S.):": heard, maybe unseen


def require_speakers(db: Session, project: Project, clip: ProjectClip, shots: list[dict],
                     breakdown: dict, known: dict) -> None:  # fmt: skip
    """One of this video's characters speaks on camera in the clip, but their sheet can never
    reach a take: they're in no shot of the whole breakdown, or have no look in this video
    (video 233: Maya was in no shot's `character_ids`, so each clip's first frame made its own
    Maya, three faces in 17 s). Refused before any charge. A line over an insert (the bowl, a
    hand, the back of a head) whose speaker is in another shot goes ahead, as does a line the
    script labels with a parenthetical ("(O.S.)", "(ON PHONE)")."""
    if not on_camera_speech(db, project, clip, shots):
        return
    from app.cast_roles import labels, pick, video_slots
    from app.routes.scripts import latest
    from app.storyboard import cast_looks

    words = latest(db, project)
    lines = words.text.splitlines() if words else []
    seen = {r for sc in breakdown.get("scenes", []) for s in sc.get("shots", [])
            for r in s.get("character_ids") or []}  # fmt: skip
    cast = [(slot.role, {f"slot:{slot.id}", *(f"char:{c}" for c in (
        slot.library_item_id, (project.slot_cast or {}).get(str(slot.id)), pick(db, project, slot))
        if c)}) for slot in video_slots(db, project)]  # fmt: skip
    cast += [(i.name, {f"char:{i.id}"}) for i in cast_looks(db, project)]
    for s in shots:
        said = [lines[n - 1] for n in s.get("script_lines") or [] if 0 < n <= len(lines)]
        if (not s.get("line") or not s.get("speaker") or VOICE_OVER.search(s["speaker"])
                or any(LABELLED_OFF.match(x) for x in said)):  # fmt: skip
            continue
        theirs = [refs for name, refs in cast if labels(s["speaker"], name)]
        looked = [r for refs in theirs for r in refs if known.get(r) and known[r][-1]]
        if theirs and not (set(looked) & seen):  # in no shot, or with no look at all
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
    video's B-roll stays silent under its voice (sound effects there are `add_sound`'s), as
    does an Omni talker's, laid over their picture while they talk (omni_talker.cutaways)."""
    from app import omni_talker, plans

    if clip.song_slice or plans.fmt(db, project) != "dialogue" or omni_talker.on(db, project):
        return False
    return not QUIET.match((clip.prompt or "").lstrip())


# A line spoken off camera, by its script label: "(O.S.)", "(O.C.)", "(V.O.)", "(OFF)", "(ON
# PHONE)", "(PRE-LAP)", "(FILTERED)". Its take still keeps its sound; only its lips don't move.
OFF_CAMERA = re.compile(r"\((?:[^)]*?\b)?(?:v\.?\s?o|o\.?\s?[sc]|off|on (?:the )?(?:phone|radio|"
                        r"tv|speaker)|pre-?lap|filtered)\b", re.I)  # fmt: skip


def lips_on_camera(db: Session, project: Project, clip: ProjectClip, shots: list[dict]) -> bool:
    """Whether someone's lips move on camera in this clip (`on_camera_speech`, less a line
    whose script label marks it off camera: the breakdown keeps only the speaker's name)."""
    if not on_camera_speech(db, project, clip, shots):
        return False
    from app.prompts.check import SPEAKER
    from app.routes.scripts import latest

    words = latest(db, project)
    lines = words.text.splitlines() if words else []

    def off(shot: dict) -> bool:  # its script line's own label: "MOM (O.S.):"
        said = [SPEAKER.match(lines[n - 1]) for n in shot.get("script_lines") or []
                if 0 < n <= len(lines)]  # fmt: skip
        return any(m and OFF_CAMERA.search(m[0]) for m in said)

    return any(s.get("line") and s.get("speaker") and not VOICE_OVER.search(s["speaker"])
               and not off(s) for s in shots)  # fmt: skip


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
    most = m.duration.max
    if clip.seconds <= most:
        return
    from app import breakdown_fix, plans

    bd = db.get(BreakdownVersion, clip.breakdown_id or 0)
    version = plans.script(db, project)
    lo = m.duration.min if m.duration else 1
    parts = breakdown_fix.split_into(bd.data, version.text if version else "", clip.clip_id,
                                     lo, most) if bd else 1  # fmt: skip
    offered = bd is not None and clip.clip_id in breakdown_fix.too_long(bd.problems or [])
    then = ("Split it in the breakdown (free), then make it" if parts > 1 and offered else
            "Make its shot shorter in the breakdown, or switch the video model in Settings to "
            "one that makes longer clips (free)")  # fmt: skip
    raise HTTPException(409, f"This clip is {clip.seconds} s, but {m.name} makes at most "
                        f"{most} s a clip. {then}. Nothing was charged.")  # fmt: skip


SAME_INVALID = ("The service refused this take's request as invalid ({reason}), so the same "
                "request would be refused again. Change the prompt or its pictures first. "
                "Nothing was charged.")  # fmt: skip


SAME_REFUSED = ("This same prompt for clip {} was {} before, so it would be again. "
                "Change the prompt first. Nothing was charged.")  # fmt: skip


def not_again(db: Session, clip: ProjectClip, model_id: str, take: dict, sent: dict) -> None:
    """A take whose last try was refused as an invalid request (a 400 or 422) is never sent
    again unchanged: the director's "try again" sent the same 422 (video 245). Nor does the
    director send a prompt the service refused for this clip on its content again as it was
    (video 345: E006 "The input was invalid", the same prompt three times): it rewords it."""
    from app.routes.jobs import DIRECTOR_TOOL

    takes = db.scalars(select(Job).where(Job.project_id == clip.project_id,
                                         Job.input["project_clip_id"].as_integer() == clip.id,
                                         Job.input["step"].as_string() == "clip_take")
                       .order_by(Job.id.desc())).all()  # fmt: skip

    def same(job: Job, whole: bool) -> bool:  # its pictures changed: it may go
        asked = job.input.get("input") or {}
        said = asked == take if whole else _words(asked.get("prompt")) == _words(take.get("prompt"))
        return (job.input.get("model") == model_id and said
                and (job.input.get("files") or {}) == (sent or {}))  # fmt: skip

    last = takes[0] if takes else None
    if last and last.status == JobStatus.failed and why_failed(last) == "invalid" and same(
            last, True):  # fmt: skip
        raise HTTPException(409, SAME_INVALID.format(reason=invalid(last.error_detail or "")))
    if not DIRECTOR_TOOL.get():  # a person may try again: the free reword comes on its own
        return
    for job in takes:
        if job.status == JobStatus.failed and why_failed(job) == "refused" and same(job, False):
            raise HTTPException(409, SAME_REFUSED.format(  # which clip: a run may stop on it
                clip.clip_id.removeprefix("c"), refused_how(job.error_detail)))  # fmt: skip


def _words(prompt) -> str:
    """A prompt as the model reads it: spaces and line breaks don't make it another one."""
    return " ".join(str(prompt or "").split())


FIT = "fit"  # in a free fix's input: it shortens the prompt to its model's limit
UNSENT = "unsent"  # in a take's input: the references its model was never sent
ROOM = 800  # characters a prompt is written under its limit: what a take adds (its language
# line, a Redo note of 500 at most in its own words: about 700) and a little over (video 271:
# 3,441 for "under 3,400"), so any Redo note fits
SLACK = 100  # a rewrite runs a little long
TOO_LONG_START = "The prompt is too long for "  # how its refusal starts (director_tools)
FITTING = ("The prompt is too long for {model} ({n:,} of {most:,} characters), so it's being "
           "rewritten to fit, free. Make the take once it's rewritten. "
           "Nothing was charged.")  # fmt: skip
WRITING = ("The prompt is too long for {model} ({n:,} of {most:,} characters); it's rewritten to "
           "fit once the clip prompts being written now are done. Make the take then. Nothing "
           "was charged.")  # fmt: skip
STILL_LONG = ("The prompt is still too long for {model} ({n:,} of {most:,} characters) after "
              "two rewrites. Shorten it with Edit (free), or put this clip on a model that takes "
              "longer prompts. Nothing was charged.")  # fmt: skip


FITTED = "fitted"  # in a fit's input once its shorter prompt is saved


def failed_fits(db: Session, clip: ProjectClip) -> int:
    """The clip's rewrites to fit that were done but never saved (QA on #1453: one saved for a
    first take, then too long with a remake's note, never spends a try)."""
    fits = db.scalars(select(Job).where(Job.project_id == clip.project_id,
                                        Job.input[FIT].as_boolean()))  # fmt: skip
    return sum(j.input.get("clip_ids") == [clip.clip_id] and j.status not in WAITING
               and not j.input.get(FITTED) for j in fits)  # fmt: skip


def fits_prompt(db: Session, project: Project, clip: ProjectClip, model, sent: str,
                note: str = "") -> None:  # fmt: skip
    """A prompt longer than its model takes (Seedance 2.0: 4000 characters) is never sent: the
    provider refuses it the same way every time. It's rewritten to fit, free, by the clip's
    own fix (clip_prompts.fix_job: its Keep, Shot and spoken lines kept), never cut short, and
    the take is refused until then, saying so; after two that failed, a person shortens it. The
    rewrite leaves room for what the take adds, any Redo note included (video 271: a fit to
    3,441 characters was still too long with the director's note, twice)."""
    from app.clip_prompts import fix_job, fixing
    from app.credits import lock

    most = model.prompt_max
    if not most or len(sent) <= most:
        return
    said = {"model": model.name, "n": len(sent), "most": most}
    from app import one_pass

    if one_pass.on(project):  # its prompts are built in code: never a rewrite by a model
        raise HTTPException(409, one_pass.LONG.format(**said))
    lock(db, Project, project.id)  # two presses at once queue one fix
    if fixing(db, clip):
        raise HTTPException(409, FITTING.format(**said))
    jobs = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    writing = ("clip_prompts", "narrated_clip_prompts")  # a rewrite of every clip: after it
    if any(j.input.get("step") in writing and not j.input.get("fix") for j in jobs):
        raise HTTPException(409, WRITING.format(**said))
    if failed_fits(db, clip) >= 2:
        raise HTTPException(409, STILL_LONG.format(**said))
    added = len(sent) - len(clip.prompt or "") - _noted(note)  # its language line and such
    room = most - added - _noted("x" * NOTE_MAX) - SLACK  # asked: room for any Redo note
    keep = next((x for x in (clip.prompt or "").splitlines() if x.startswith("Keep: ")), "")
    told = (f"Shorten this clip's prompt to under {room} characters ({model.name} takes at most "
            f"{most}; it's {len(sent)}): say each shot's description in fewer words. Keep every "
            "shot, in order, with its start as written (\"Shot N | a–b s.\"), every spoken or "
            f"quoted line word for word, and the Keep: line as it is ({len(keep)} of those "
            "characters: it's put back as it is if changed). Never drop a shot or a line "
            "someone says.")  # fmt: skip
    fix = fix_job(db, db.get(User, project.created_by_id), project, clip, [], told=told)
    fix.input = {**fix.input, FIT: True, "fit_max": most - added - _noted(note)}  # this take
    db.commit()  # the fix stands whatever the refusal below rolls back
    raise HTTPException(409, FITTING.format(**said))


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

# The service refused the request for what it asks or shows (its content or safety check), by
# whatever code: Replicate's E006 "The input was invalid" over Omni's "Request blocked due to
# safety violations" or "prohibited content guidelines" (video 345, jobs 3357 and 3359), E005
# "flagged as sensitive" and its copyright refusal, "ContentModerationError: flagged for: sexual",
# HeyGen's content_policy_violation (docs/prompting/heygen-avatar-iv.md). The same request is
# refused the same way, and a failed run isn't billed ("For all models, if a run fails, we don't
# charge you": replicate.com/docs/topics/billing, Failed and canceled runs). Straight from
# Google (app/providers/google.py) the same codes come bare, with its other "generation
# blocked" ones and "Input blocked: …" (aistudio.google.com/docs/api-errors, /safety-settings).
FILTERED = "safety|prohibited_content|jailbreak|blocklist|image_safety|image_prohibited_content"
BLOCKED = FILTERED + "|content_blocked|recitation|image_recitation|image_other|spii|language"
REFUSAL = re.compile(r"\bE00[56]\b|flagged (?:as|for)|ContentModeration|content[_ ]policy|"
                     r"safety violation|prohibited content|Input blocked:|"
                     rf"\"code\"\s*:\s*\"(?:{BLOCKED})\"", re.I)  # fmt: skip
# Omni's safety filter: its inner "code": "safety" or "prohibited_content" (video 345). A bare
# E006 ("The input was invalid": a bad picture, say) is only refused.
SAFETY_FILTER = re.compile(rf'"code"\s*:\s*"(?:{FILTERED})"', re.I)
REFUSED_SAID = "This prompt was {}. Change the prompt before trying again. Nothing was charged."


def refusal(detail: str) -> str:
    """The provider's own words for refusing a request on its content ("Request blocked due to
    safety violations (harmful content)"), without its codes, ids or "Please retry"; "" when
    it wasn't refused that way. The raw detail stays in `error_detail`."""
    if not REFUSAL.search(detail or ""):
        return ""
    said = re.findall(r'"(?:message|detail)"\s*:\s*"((?:[^"\\]|\\.)*)"', detail)
    said = said[-1] if said else re.split(r"(?:Error|\bE\d{3,4})\s*:\s*", detail)[-1]
    said = re.sub(r"https?://\S+|\((?=[^)]*\d)[A-Za-z0-9]{4,}\)|\bE\d{3,4}\b:?", "", said)
    said = re.sub(r"\s*Please [^.]*(?:\.|$)|['\")]+$", "", said)  # its "try again" isn't ours
    said = re.sub(r"\s+", " ", said).strip(" .:-")[:200]
    return said[:1].upper() + said[1:] if said else "its content check"


def refused_how(detail: str | None) -> str:
    """How it was refused, with the service's own words, for the owner and the director alike:
    "blocked by the service's safety filter (it said: …)" or "refused by the service (it said:
    …)". A failed run isn't billed, blocked or not (replicate.com/docs/topics/billing)."""
    said = refusal(detail or "") or "it may be related to copyright"
    how = ("blocked by the service's safety filter" if SAFETY_FILTER.search(detail or "")
           else "refused by the service")  # fmt: skip
    return f"{how} (it said: {said})"


def last_refused(db: Session, row: ProjectClip) -> dict:
    """The clip's newest take when the service refused it: how, and the prompt it was sent
    in full, so the director sees what tripped it (video 345: a script line carried into a
    B-roll prompt, blocked 6 times); {} otherwise."""
    job = db.scalar(select(Job).where(Job.project_id == row.project_id,  # its video's only
                                      Job.input["project_clip_id"].as_integer() == row.id,
                                      Job.input["step"].as_string() == "clip_take")
                    .order_by(Job.id.desc()).limit(1))  # fmt: skip
    if job is None or job.status != JobStatus.failed or why_failed(job) != "refused":
        return {}
    sent = (job.input.get("input") or {}).get("prompt", "")
    return {"refused": {"how": refused_how(job.error_detail), "prompt": sent}}


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
        if term == "sensitive":  # at random: made again once, then reworded if it keeps failing
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


# The provider refused the request itself as invalid, before running it (a 400 or 422: "input.
# prompt: String length must be less than or equal to 4000"): never billed, and the same
# request is refused the same way every time.
# Google also says so after it starts (video 398's clip 1, six times: "There was a problem
# processing your request. You will only be charged for tokens successfully generated",
# code INVALID_ARGUMENT, with no usage): nothing was made, and it's the same every time.
INVALID = re.compile(r"(?:Replicate|Google) (?:400|422)\b|Input validation failed"
                     r'|"code": "INVALID_ARGUMENT"', re.I)  # fmt: skip


def invalid(detail: str) -> str:
    """The provider's own reason for refusing a request as invalid, plainly ("input.prompt:
    String length must be less than or equal to 4000"), or "" when it wasn't that."""
    if not INVALID.search(detail or ""):
        return ""
    found = (re.search(r'"detail"\s*:\s*"((?:[^"\\]|\\.)*)"', detail)
             or re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', detail))  # Google's  # fmt: skip
    reason = found.group(1) if found else detail.split(":", 1)[-1]
    reason = reason.replace("\\n", " ").replace("\\'", "'")  # as the worker's repr() wrote it
    return re.sub(r"\s+", " ", reason).strip(" -")[:300]


def why_failed(job: Job) -> str:
    """ "busy" (the service was busy or didn't answer), "refused" (its content check or
    copyright refusal: never charged), "invalid" (the request itself refused before it ran:
    never charged, never sent again as it is), or "" for anything else."""
    detail = job.error_detail or ""
    if BUSY_SAID.search(detail):
        return "busy"
    if refusal(detail) or "copyright" in detail.lower():  # its content: before a 400's "invalid"
        return "refused"
    return "invalid" if invalid(detail) else ""


def retry(db: Session, job: Job) -> None:
    """P3 (flows.md 1b): a take refused or not finished because the service was busy is
    tried again once on its own. A busy service gets a short wait; a refusal read as
    something ("flagged for: sexual") is reworded first by the free fix, then retried
    (`after_fix`). A look-alike refusal steps down instead (`_again_without`: without the
    still, then without the sheets). "Flagged as sensitive" (E005, at random) is made again
    once as it is; any other refusal (E006, the safety filter) never is: its prompt changes
    first (video 345), but for a talker's own piece on Omni 1.2, which is asked of Omni 1.1
    (`_on_omni_1_1`). No other second automatic retry, never on a video that's gone, and
    never past the video's limit, budget or the editor's week. The failed take isn't counted,
    so the credits are held once and come back if the retry fails too."""
    from app import director
    from app.clip_prompts import fix_job, is_stale, newest
    from app.routes.jobs import BY_DIRECTOR

    why = why_failed(job)
    if why in ("", "invalid") or job.input.get("discard") or not job.project_id:
        return  # an invalid request is refused the same way again: never retried as it is
    if job.input.get(BY_DIRECTOR):
        video = db.get(Project, job.project_id)
        if director.ended(db, video) == director.STOPPED and not director.active(db, video):
            return  # the director's take, and its run was stopped while it was out
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
    if why == "refused" and term != "sensitive":  # never the same again (345: E006 3 times)
        if older := _on_omni_1_1(db, project, row, job):  # but a talker's own line: on Omni 1.1
            _again(db, job, older, wait=False)
        return
    _again(db, job, job.input, wait=why == "busy")


def _on_omni_1_1(db: Session, project: Project, row: ProjectClip, job: Job) -> dict | None:
    """A talker's piece Omni 1.2 refused for what it says, as Omni 1.1 is asked for it (Reed, 12
    Nov, when Google blocked "Click the link below" as prohibited content: "On the CTA - use
    omni 1.1 for the same line if it fails"): the same prompt and opening still, three pictures
    at most. Straight from Google its clip is the piece's own length, up to the next of 4, 6, 8
    or 10 s ("its in increments of 2 from 4 to 10"); on Replicate it takes no length and comes
    back 10 s, and the cut trims a talker's piece to its words. None for a piece longer than
    1.1 makes, or any other clip: its prompt changes first, as before."""
    from app import model_map, omni_talker, p_video
    from app.catalogue import get_model
    from app.clip_prompts import newest

    files = job.input.get("files") or {}
    old = get_model(model_map.OMNI_1_1)
    plan = omni_talker._plan(bd.data if (bd := newest(db, project)) else {})
    asked = job.input["input"]
    most = old.fixed_seconds or old.duration.max
    if (job.input.get("model") != model_map.OMNI or not omni_talker.on(db, project)
            or row.clip_id not in {c for c, mine in plan if omni_talker._talks(mine)}
            or len(files.get("reference_images") or []) > old.max_reference_images
            or asked.get("resolution") not in old.price.usd
            or int(asked.get("duration") or 0) > most):  # fmt: skip
        return None
    if not old.fixed_seconds:  # 4, 6, 8 or 10 s: the piece's own length, up to the next of them
        step, least = old.duration.step, old.duration.min
        asked = {**asked, "duration": max(least, step * math.ceil(asked["duration"] / step))}
    take, sent = p_video.fit(old.id, asked, files)
    made = {**(job.input.get("made_with") or {}), "model": old.id}
    return {**job.input, "model": old.id, "input": take, "files": sent, "made_with": made}


REAL = "may contain real person"  # Seedance, of a reference picture (video 392: a sheet)


def _lookalike(job: Job) -> bool:
    detail = (job.error_detail or "").lower()
    return ("copyright" in detail or REAL in detail) and not job.input.get("discard")


def _again_without(db: Session, job: Job) -> None:
    """A take refused as a look-alike (Seedance's copyright check, the Producer), or for a
    reference picture that "may contain real person": made again
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
        # a sheet taken for a real person: straight to the characters in words
        step = len(LOOKALIKE) - 1 if REAL in (job.error_detail or "").lower() else step
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
    (never charged twice); after that Make again makes it (rule 22). Never one refused on its
    content but "sensitive" (at random): it would be refused the same way."""
    refused = why_failed(job) == "refused" and moderated(job.error_detail or "") != "sensitive"
    if job.auto or refused or db.scalar(select(Job.id).where(Job.retry_of_id == job.id)):
        return
    _again(db, job, job.input, wait=bool(BUSY_SAID.search(job.error_detail or "")))


def _again(db: Session, job: Job, data: dict, wait: bool) -> None:
    from app.catalogue import get_model, provider_for
    from app.credits import estimate

    project = db.get(Project, job.project_id)
    user = db.get(User, job.created_by_id)
    credits, provider = job.credits, job.provider
    if data.get("model") != job.input.get("model") and (m := get_model(data["model"])):
        seconds = m.fixed_seconds or data["input"]["duration"]  # Omni 1.1: its own price and road
        credits = estimate(db, job.workspace_id, job.kind, Decimal(seconds), data)
        if provider in ("google", "replicate"):
            provider = provider_for(m.id, "replicate")
    if not user or fits(db, project, user, credits):
        return  # it would go over: nothing more runs on its own
    data = {k: v for k, v in data.items() if k != "busy"}  # its own busy waits start afresh
    if wait:
        data = {**data, "wait_until": (utcnow() + RETRY_WAIT).isoformat()}
    db.add(Job(workspace_id=job.workspace_id, created_by_id=job.created_by_id, kind=job.kind,
               provider=provider, input=data, project_id=job.project_id,
               brand_id=job.brand_id, credits=credits, approved_by_id=job.approved_by_id,
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
    if job.input.get("step") == "song_timing":  # a take's timing read again (song_takes):
        return project is None or project.archived_at is None  # a script's take, or its video's
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


NOT_SEEN = ("Audio:", "Language:", "Style:")  # a clip prompt's sound, language and style lines
FIXED = ("No one speaks.", "No subtitles.")  # every wordless shot's own words, never a picture
NOT_A_THING = {"one", "else", "more", "other", "others", "longer", "matter", "way", "need"}


def contradicts(prompt: str, note: str) -> bool:
    """A redo note that takes away or swaps something the clip's prompt shows: appended under
    the prompt, both would stand ("phone lighting up in his hand", then "no phone"), so the
    prompt is rewritten with it instead (Change it…). Only what's seen counts (Summary,
    Setting, the shots, Keep, References; never `NOT_SEEN`): the Audio lines and the fixed
    "No one speaks." / "No subtitles." name music, voices and subtitles in every prompt (QA on
    #1410: "No music, please." isn't in the picture), and "no one else" takes away no thing."""
    shown = "\n".join(x for x in (prompt or "").splitlines() if not x.startswith(NOT_SEEN))
    for said in FIXED:
        shown = shown.replace(said, "")
    words = set(re.findall(r"[a-z-]+", shown.lower()))
    found = [w for m in TAKES_AWAY.finditer(note or "") if (w := m[1].lower()) not in NOT_A_THING]
    return any(w in words or w.removesuffix("s") in words or f"{w}s" in words for w in found)


NOTE_MAX = 500  # a Redo note's characters at most (project_clips.TakeIn)


def _noted(note: str) -> int:
    """The characters a Redo note adds to a take's prompt."""
    return len(_with_note("a\nb", note)) - 3


def _with_note(prompt: str, note: str) -> str:
    """A Redo note ("what's wrong") goes into this take only, before the closing audio line
    so the prompt still opens and closes on the same line."""
    if not note:
        return prompt
    lines = prompt.rstrip().splitlines()
    keep = "The spoken lines stay exactly as written above; nobody else speaks."
    return "\n".join([*lines[:-1], f"Change from the last take: {note} {keep}", lines[-1]])


def take_credits(db: Session, project: Project, clip: ProjectClip, edit: bool = False) -> Decimal:
    """What one more take costs: the estimate `enqueue` charges, and the director's watch of
    it that rides along while watches are on (`take_watch.rides`). `edit`: an edit of its take
    (Omni's, `change.editable`), at the edit's price on the same seconds; an Omni talker's
    piece, with its voice separated from its room (talker_sound). A clip of real footage is cut
    from it, free; a take given a reference video is at its model's dearer rate (app/footage)."""
    from app import footage_shot, take_watch, talker, talker_sound

    if talker.says(db, project, clip):  # cut from the talker's one HeyGen take (video 281)
        from app import host

        return host.price(db, project, 1)
    if footage_shot.of_clip(db, clip):
        return Decimal(0)
    m = model_map.of_clip(project, clip)
    job = {"model": m.id, "edit": edit, "input": {"resolution": model_map.resolution(m)},
           "video_in": any(r["kind"] == "video" for r in clip.references or [])}  # fmt: skip
    seconds = model_map.billed(m, clip.seconds)  # as it's asked for on its own model
    take = estimate(db, project.workspace_id, "video", Decimal(seconds), job)
    split = talker_sound.price(db, project.workspace_id)
    return (take + take_watch.rides(db, project, clip)
            + (split if talker_sound.splits(db, project, clip) else 0))  # fmt: skip


def takes_price(db: Session, project: Project, clips) -> Decimal:
    """One more take of each clip, the talker's clips once together: one HeyGen take of the
    whole narration makes them all (QA on #1457)."""
    from app import talker

    rows = list(clips)
    said = [c for c in rows if talker.says(db, project, c)]
    each = sum((take_credits(db, project, c) for c in rows if c not in said), Decimal(0))
    return each + (take_credits(db, project, said[0]) if said else Decimal(0))


def save_take(db: Session, job: Job) -> None:
    """A new take: numbered, and picked (the newest take is picked when it arrives)."""
    clip = db.get(ProjectClip, job.input["project_clip_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if not clip or not file_ids:
        return
    count = db.scalar(select(func.count(ClipTake.id)).where(ClipTake.clip_id == clip.id))
    clip.left_out = None  # it has a take: its place in the cut is back
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
    from app import take_watch, talker_sound  # rule 11: the director watches and hears it

    take_watch.queue_safely(db, job, take, clip)
    talker_sound.queue_safely(db, job, take, clip)  # an Omni talker's: its voice from its room


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
