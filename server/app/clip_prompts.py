"""Clip prompts: Claude writes one Seedance prompt per clip of the newest breakdown, with its
references (storyboard frame, cast, place, screens, voice samples). Saved per clip with the
problems `check.clip_prompts` finds; the editor can edit them before generating.

Over 400 lines on purpose: writing, saving, repairing and rewriting a clip prompt share the same
cast and picture helpers, so a split would only move code between files (Steward, 2026-10-27)."""

import json
import logging
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import cut_in
from app.advice import names, plain
from app.breakdown import video_model, video_model_block
from app.cast_roles import bare
from app.enhance import escape, project_context
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts import check
from app.prompts.schemas import Breakdown, ClipPrompt, ClipPrompts, Reference
from app.storyboard import (
    CHAR,
    LEFT_OUT,
    _name,
    _renumber,
    _same,
    hero,
    is_logo,
    left_out,
    logo_clip,
    nearest_first,
    newer_sheets,
    older_looks,
    one_logo,
    say_logo,
)
from app.storyboard import assets as picture_assets

log = logging.getLogger(__name__)

# asset id -> (line for the prompt, kind for Seedance, its file ids)
Assets = dict[str, tuple[str, str, list[int]]]
# One call writes at most this many clips or shots: every clip of a long video in one answer
# ran out of room (the output limit, thinking included) and failed the whole run.
BATCH_CLIPS, BATCH_SHOTS = 3, 12
UNWRITTEN = "This clip's prompt wasn't written"


def assets(db: Session, project: Project) -> Assets:
    """Pictures (as for the storyboard), each clip's rendered storyboard frame, and the cast's
    voice samples."""
    out: Assets = {
        k: (line, "image", files) for k, (line, files) in picture_assets(db, project).items()
    }
    frames = db.scalars(
        select(StoryboardFrame).where(
            StoryboardFrame.project_id == project.id, StoryboardFrame.file_id.is_not(None)
        )
    )
    for f in frames:
        key = f"frame:{f.clip_id}"
        out.setdefault(key, (f"{key} | storyboard frame | clip {f.clip_id}", "image", [f.file_id]))
    for char_id in project.cast_ids:
        item = db.get(LibraryItem, char_id)
        if item and item.voice_file_id:
            key = f"voice:{item.id}"
            out[key] = (f"{key} | voice sample | {item.name}", "audio", [item.voice_file_id])
    return out


def batches(bd: Breakdown, clip_ids: list[str] | None = None) -> list[list[str]]:
    """The clips in calls of a few clips each (BATCH_CLIPS clips or BATCH_SHOTS shots at
    most); a long montage clip gets a call of its own."""
    out: list[list[str]] = []
    shots = 0
    for clip in bd.clips:
        if clip_ids is not None and clip.id not in clip_ids:
            continue
        n = len(clip.shot_ids)
        if not out or len(out[-1]) >= BATCH_CLIPS or shots + n > BATCH_SHOTS:
            out.append([])
            shots = 0
        out[-1].append(clip.id)
        shots += n
    return out


def job_input(
    db: Session, project: Project, bd: BreakdownVersion, clip_ids: list[str] | None = None
) -> dict:
    """One job, one price: Claude is asked a few clips at a time (`parts`), so no answer runs
    out of room."""
    system, _ = project_context(db, project, "clip_prompts")
    groups = batches(Breakdown.model_validate(bd.data), clip_ids)
    lines = "\n".join(dict.fromkeys(line for line, _, _ in assets(db, project).values()))
    prompt = "\n".join(
        [
            video_model_block(video_model()),
            f"<assets>\n{escape(lines)}\n</assets>",
            f"<breakdown>\n{escape(json.dumps(bd.data, ensure_ascii=False))}\n</breakdown>",
        ]
    )
    return {
        "step": "clip_prompts",
        "project_id": project.id,
        "breakdown_id": bd.id,
        "system": system,
        "prompt": prompt,
        "max_tokens": 32000,
        "batches": groups,
        "parts": [
            f'<write clips="{", ".join(g)}">Write the prompts for these clips only: '
            f"{', '.join(g)}. The other clips are written separately.</write>"
            for g in groups
        ],
    }


def cause(error: str, detail: str = "") -> str:
    """Why a clip-prompts run (or one clip of it) didn't finish, in plain words."""
    text = f"{error} {detail}"
    if "ran out of room" in text:
        return "the answer ran out of room before it was finished"
    if "unreadable" in text:
        return "the answer came back in the wrong shape"
    if "declined" in text:
        return "Claude declined to write it"
    if "restarted" in text or "Lost contact" in text:
        return "the server restarted or lost contact while it was being written"
    if any(w in text for w in ("RateLimit", "Overloaded", "InternalServerError", "busy")):
        return "Claude was too busy, three tries in a row"
    if "couldn't be saved" in text:
        return "it was written but couldn't be saved"
    return "an unexpected error (the details are in the server log)"


def failed(db: Session, job: Job) -> None:
    """A clip-prompts run that failed says why in plain words (its `error`, which everyone
    sees, and the server log). A free fix that failed stays used: once per prompt version,
    then "Rewrite this clip" at its price (QA on #605)."""
    reason = cause(job.error or "", job.error_detail or "")
    log.warning("job %s: clip prompts didn't finish: %s (%s)", job.id, reason, job.error_detail)
    job.error = f"{reason[0].upper()}{reason[1:]}. Nothing was charged; try again."


TAGS = re.compile(r"(\[Image)(\d+)\]")


def _pictures(known: Assets) -> dict[str, tuple[str, list[int]]]:
    return {k: (line, files) for k, (line, _, files) in known.items()}


def _cast(bd: Breakdown, clip_id: str, pics: dict, lead: str | None = None) -> list[str]:
    """The clip's characters in the order they first appear, nearest the camera first; the
    main character (`lead`) first whenever they're in the clip."""
    clip = next((c for c in bd.clips if c.id == clip_id), None)
    shots = {s.id: s for scene in bd.scenes for s in scene.shots}
    out: list[str] = []
    for sid in clip.shot_ids if clip else []:
        for ref in nearest_first(shots[sid], pics, lead) if sid in shots else []:
            if not any(_same(pics, ref, r) for r in out):
                out.append(ref)
    return sorted(out, key=lambda r: not (lead and _same(pics, r, lead)))


def _screens(bd: Breakdown, clip_id: str) -> list[str]:
    """The screens the clip's shots show, the one shown last (the payoff) last."""
    clip = next((c for c in bd.clips if c.id == clip_id), None)
    shots = {s.id: s for scene in bd.scenes for s in scene.shots}
    out: list[str] = []
    for sid in clip.shot_ids if clip else []:
        for screen in shots[sid].screen_ids if sid in shots else []:
            out = [s for s in out if s != screen] + [screen]
    return out


def _sheet_words(prompt: str, n: int, who: str) -> str:
    """After a sheet change (QA-Live, video #17: Goth GF 2's removed streak came back): the
    person's References sentence and Keep clause as the code writes them, and no look words in
    brackets after their name. The new sheet sets the look. Free; again changes nothing."""
    tag, lines = rf"\[Image{n}\]", []
    for line in bare(prompt, who).splitlines():
        if line.startswith("References: "):
            line = re.sub(rf"{tag} is [^.]*\.", f"[Image{n}] is {who}.", line)
        elif line.startswith("Keep: "):
            same = f"{who} as in [Image{n}], the same look as on their sheet"
            line = re.sub(rf"{re.escape(who)} as in {tag}[^;.]*", same, line)
        lines.append(line)
    return "\n".join(lines)


def _add(prompt: str, start: str, text: str) -> str:
    lines = prompt.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(start):
            lines[i] = f"{line.rstrip()} {text}"
            return "\n".join(lines)
    return prompt


def with_cast(
    db: Session, project: Project, clip: ClipPrompt, bd: Breakdown, known=None, trim=True
) -> ClipPrompt:
    """The clip twin of `storyboard.with_cast` (Reed, 2026-10-26): whatever the AI picked, the
    server attaches the approved sheet of every character in the clip's shots, in the order
    they first appear (nearest the camera first), after the first frame ([Image1]) and before
    the place and screens, within the video model's limit. Every screen the clip's shots show
    is attached too, after them, the payoff screen last (the Director, #556: "screen isn't
    attached" never blocks). Every [ImageN] follows its picture; an added character joins the
    References and Keep lines, an added screen the References line. Free; doing it again
    changes nothing. With trim off (an edit, or a saved clip) nothing already picked is
    dropped."""
    known = known if known is not None else assets(db, project)
    pics = _pictures(known)
    images: list[Reference] = []  # every logo-only screen as the one logo, once
    for r in (r for r in clip.references if r.kind == "image"):
        r = r.model_copy(update={"id": one_logo(pics, r.id)})
        images += [] if any(o.id == r.id for o in images) else [r]
    others = [r for r in clip.references if r.kind != "image"]
    first = [r for r in images if r.id.startswith("frame:")]
    people = [r for r in images if r.id.startswith(CHAR)]
    objects = [r for r in images if r not in first and r not in people]
    lead = hero(db, project, bd, pics)
    cast = [c for c in _cast(bd, clip.clip_id, pics, lead) if pics.get(c, ("", []))[1]]
    missing = [c for c in cast if not any(_same(pics, c, r.id) for r in people)]

    def rank(r: Reference) -> int:
        return next((i for i, c in enumerate(cast) if _same(pics, r.id, c)), len(cast))

    room = len(people) + len(missing)
    if limit := video_model().max_reference_images:
        room = min(room, max(limit - len(first) - len(objects), 0))
    added = [Reference(kind="image", id=c, role=f"{_name(pics, c)}'s look") for c in missing]
    if trim:  # stable: people not in the clip stay last
        people = sorted(people + added, key=rank)[:room]
    else:  # an edit keeps everyone; the main character still moves first
        added = added[: max(room - len(people), 0)]
        people = sorted(people + added, key=rank)
    new = first + people + objects
    want = [one_logo(pics, s) for s in _screens(bd, clip.clip_id)]
    want = [s for s in dict.fromkeys(want) if s not in {r.id for r in new} and s in pics]
    if limit := video_model().max_reference_images:  # people first; the payoff screen kept
        room = max(limit - len(new), 0)
        want = want[-room:] if room else []
    new += [Reference(kind="image", id=s, role=_name(pics, s) + " screen" * (not is_logo(pics, s)))
            for s in want]  # fmt: skip
    was = [r for r in clip.references if r.kind == "image"]
    if new == was:
        return clip
    ids, before = [r.id for r in new], [one_logo(pics, r.id) for r in was]
    moved = {i + 1: ids.index(r) + 1 for i, r in enumerate(before) if r in ids}
    dropped = {i + 1: _name(pics, r.id) for i, r in enumerate(was) if before[i] not in ids}
    prompt = _renumber(clip.prompt, moved, dropped, TAGS)
    for r in (r for r in new if r.id not in before):
        who, tag = _name(pics, r.id), f"[Image{new.index(r) + 1}]"
        if r.id in want:  # rule 14: a logo is only the logo, the trading screen is invented
            n, real = new.index(r) + 1, f"{tag} is the {who} screen, exactly as it is."
            prompt = _add(
                prompt, "References: ", logo_clip(n, who) if is_logo(pics, r.id) else real
            )
            continue
        prompt = _add(prompt, "References: ", f"{tag} is {who}.")
        prompt = _add(prompt, "Keep: ", f"{who} as in {tag}, the same look as on their sheet.")
    return clip.model_copy(update={"prompt": prompt, "references": new + others})


def clip_problems(db: Session, project: Project, bd: Breakdown, clip: ClipPrompt) -> list[str]:
    """A character in the clip without an approved look is flagged by name, a role not cast
    yet included (Reed, 2026-10-27); sheets are attached by `with_cast`."""
    m, known = video_model(), assets(db, project)
    pics = _pictures(known)
    seen = bd.model_copy(deep=True)  # every logo-only screen is the one logo `with_cast` attached
    for shot in (s for scene in seen.scenes for s in scene.shots):
        shot.screen_ids = list(dict.fromkeys(one_logo(pics, s) for s in shot.screen_ids))
    problems = check.clip_prompts(
        seen, ClipPrompts(clips=[clip]), m.max_reference_images, m.max_reference_audios
    )
    for c in _cast(bd, clip.clip_id, pics):
        if c in pics and pics[c][1]:
            continue
        if not any(_same(pics, c, r.id) for r in clip.references):
            problems.append(f"{_name(pics, c)} has no approved look yet. Approve one in Assets.")
    frame = db.scalar(select(StoryboardFrame).where(StoryboardFrame.project_id == project.id,
                      StoryboardFrame.clip_id == clip.clip_id, StoryboardFrame.file_id.is_not(None))
                      .order_by(StoryboardFrame.id))  # fmt: skip  # the one `assets` attaches
    first = any(r.id == f"frame:{clip.clip_id}" for r in clip.references)
    if frame and first and (older := older_looks(db, known, frame)):
        problems.append(f"Advice: Its first frame was drawn from an older look of "
                        f"{', '.join(older)}. Redraw that still on Storyboard.")  # fmt: skip
    for ref in clip.references:
        if ref.id not in known:
            problems.append(f"{clip.clip_id}: unknown reference {ref.id}")
        elif known[ref.id][1] != ref.kind:
            kind = {"image": "a picture", "audio": "a sound"}.get(ref.kind, f"a {ref.kind}")
            problems.append(f"{clip.clip_id}: {ref.id} is attached as {kind} but isn't one")
    return plain(problems, names(known))


def _cap(clip: ClipPrompt, known: Assets) -> ClipPrompt:
    """Over the video model's limit even with the nearest people only: the last pictures go,
    and the prompt names them instead."""
    limit = video_model().max_reference_images
    images = [r for r in clip.references if r.kind == "image"]
    if not limit or len(images) <= limit:
        return clip
    pics = _pictures(known)
    dropped = {i + 1: _name(pics, r.id) for i, r in enumerate(images) if i >= limit}
    prompt = _renumber(clip.prompt, {}, dropped, TAGS)
    keep = images[:limit] + [r for r in clip.references if r.kind != "image"]
    return clip.model_copy(update={"prompt": prompt, "references": keep})


def repair(db: Session, project: Project) -> int:
    """Give every clip of the video its characters' sheets (`with_cast`, nothing dropped),
    put its shape right (`repair_shape`: shot times, "No one speaks." and the rest) and check
    it again. Runs whenever Clips is opened. Free and idempotent. Returns how many clips
    changed."""
    known, changed = assets(db, project), 0
    breakdowns: dict[int, Breakdown] = {}
    for row in db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)):
        if not row.prompt:  # not written yet: it keeps its free fix
            continue
        if row.breakdown_id not in breakdowns:
            data = db.get(BreakdownVersion, row.breakdown_id).data
            breakdowns[row.breakdown_id] = Breakdown.model_validate(data)
        bd = breakdowns[row.breakdown_id]
        was = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, prompt=row.prompt,
                         references=[Reference(**r) for r in row.references or []])  # fmt: skip
        now = repair_shape(with_cast(db, project, was, bd, known, trim=False), bd)
        images = [r.id for r in now.references if r.kind == "image"]
        now = now.model_copy(update={"prompt": say_logo(known, now.prompt, images, clip=True)})
        newer = newer_sheets(db, known, images, row.job_id)  # a sheet changed since it was written
        for n, r in ((n, r) for n, r in enumerate(images, 1) if r in newer):
            now = now.model_copy(update={"prompt": _sheet_words(now.prompt, n, _name(known, r))})
        cuts = {i.shot_id for i in cut_in.inserts(db, project, row)}  # none on a logo-only screen
        if cleared := bool((row.real_images or {}).keys() - cuts):
            row.real_images = {k: v for k, v in row.real_images.items() if k in cuts}
        problems = clip_problems(db, project, bd, now) + [
            p for p in row.problems or [] if p.startswith(LEFT_OUT)
        ]  # what an earlier trim left out stays said
        if any(p.lower().startswith("more references than") for p in problems):
            now = repair_shape(_cap(with_cast(db, project, was, bd, known), known), bd)
            kept = {r.id for r in now.references}
            gone = [_name(_pictures(known), r.id) for r in was.references if r.id not in kept]
            limit = video_model().max_reference_images
            problems = clip_problems(db, project, bd, now) + left_out(gone, limit)
        if now == was and problems == (row.problems or []):
            changed += cleared
            continue
        row.same_fix = row.free_fix_used  # a code repair never gives back a used free fix
        row.prompt, row.references = now.prompt, [r.model_dump() for r in now.references]
        row.seconds, row.problems = now.seconds, problems
        changed += 1
    return changed


def save_clip_prompts(db: Session, job: Job) -> None:
    """Claude's new prompts, written into the clips they're for (Reed, 2026-10-26: Clips never
    dead-ends): matched by clip id, a clip gets its new prompt, references and problems for the
    new breakdown, and its takes stay as earlier takes (each keeps the prompt it was made
    from). Only the clips the job is for (`clip_ids`, e.g. the stale ones) change; a clip the
    new breakdown no longer has is removed (its take files stay in storage); a new one is
    added. Approval and "Looks good" are cleared on every rewritten clip."""
    project = db.get(Project, job.input["project_id"])
    bd_row = db.get(BreakdownVersion, job.input["breakdown_id"])
    bd = Breakdown.model_validate(bd_row.data)
    result = ClipPrompts.model_validate(job.output)
    only = job.input.get("clip_ids")  # None: every clip
    mine = select(ProjectClip).where(ProjectClip.project_id == project.id)
    rows = {r.clip_id: r for r in db.scalars(mine)}
    wanted = {c.id for c in bd.clips}
    for clip_id, row in rows.items():
        if clip_id not in wanted:  # gone from the breakdown: its takes' files stay
            row.picked_take_id = None
            db.flush()
            db.execute(delete(ClipTake).where(ClipTake.clip_id == row.id))
            db.delete(row)
    known = assets(db, project)
    gone = _unwritten(job)
    written = {c.clip_id for c in result.clips}
    for c in result.clips:
        if c.clip_id not in wanted or (only is not None and c.clip_id not in only):
            continue
        try:  # one clip that can't be saved never loses the others
            c = repair_shape(with_cast(db, project, c, bd, known), bd)  # free, at once
            problems = clip_problems(db, project, bd, c)
        except Exception:
            log.exception("job %s: saving clip %s's prompt failed", job.id, c.clip_id)
            gone[c.clip_id] = "it was written but couldn't be saved"
            written.discard(c.clip_id)
            continue
        row = rows.get(c.clip_id)
        if row is None:
            row = ProjectClip(project_id=project.id, clip_id=c.clip_id)
            db.add(row)
        else:
            for take in db.scalars(select(ClipTake).where(ClipTake.clip_id == row.id)):
                take.prompt = take.prompt if take.prompt is not None else row.prompt
        row.same_fix = bool(job.input.get("fix"))  # the free fix landing: still counted
        if row.real_images and row.breakdown_id not in (None, bd_row.id):
            was = db.get(BreakdownVersion, row.breakdown_id)
            row.real_images = cut_in.still_shown(was.data if was else {}, bd_row.data,
                                                 row.real_images)  # fmt: skip
        row.breakdown_id, row.job_id, row.seconds = bd_row.id, job.id, c.seconds
        row.prompt, row.references = c.prompt, [r.model_dump() for r in c.references]
        row.problems, row.kept = problems, []
        row.approved, row.prompt_ok, row.change = False, False, None
        if job.input.get("fix"):  # Fix this clip's prompt: its Before and After
            before = job.input.get("before") or ""
            row.change = {"note": "Fix this clip's prompt", "status": "done", "before": before,
                          "after": c.prompt, "unchanged": before == c.prompt}  # fmt: skip
    for clip in bd.clips:  # never a dead end: a clip left unwritten gets a free one-click fix
        if clip.id in written or (only is not None and clip.id not in only):
            continue
        reason = gone.get(clip.id, "the answer left it out")
        log.warning("job %s: clip %s's prompt wasn't written: %s", job.id, clip.id, reason)
        row = rows.get(clip.id)
        if row is not None and row.prompt:  # its earlier prompt stays (stale: Rewrite this clip)
            continue
        if row is None:
            row = ProjectClip(project_id=project.id, clip_id=clip.id, prompt="", references=[])
            db.add(row)
        row.breakdown_id, row.job_id, row.seconds = bd_row.id, job.id, clip.seconds
        row.problems = [f"{UNWRITTEN}: {reason}."]  # the card names the way out (free, then priced)
        row.kept, row.approved, row.prompt_ok = [], False, False
        row.free_fix_used = bool(job.input.get("fix"))  # once per version, then priced (QA)


def _unwritten(job: Job) -> dict[str, str]:
    """clip id -> why its part of the run failed (the provider's `failed_parts`)."""
    groups = job.input.get("batches") or []
    out: dict[str, str] = {}
    for part in (job.output or {}).get("failed_parts") or []:
        for clip_id in groups[part["part"]] if part["part"] < len(groups) else []:
            out[clip_id] = cause(part["error"])
    return out


def _line(lines: list[str], start: str) -> int:
    return next((i for i, x in enumerate(lines) if x.startswith(start)), -1)


def repair_shape(clip: ClipPrompt, bd: Breakdown) -> ClipPrompt:
    """The clip prompt's shape put right in code, free (spec one-click-fixes.md §5): the
    breakdown's seconds, [Image1] named the first frame, the same audio line first and last,
    and a Summary and a Keep line where they're missing. The spoken lines are never
    touched. The same clip when nothing needs it."""
    from app.prompts.check import AUDIO_LINE, CAST

    planned = next((c for c in bd.clips if c.id == clip.clip_id), None)
    shots = {s.id: s for scene in bd.scenes for s in scene.shots}
    lines = clip.prompt.strip().splitlines() or [""]
    if AUDIO_LINE.match(lines[0]) and (len(lines) < 2 or lines[-1] != lines[0]):
        lines.append(lines[0])
    images = [r for r in clip.references if r.kind == "image"]
    first = "[Image1] is the first frame."
    if images and images[0].id.startswith("frame:") and first not in clip.prompt:
        if (at := _line(lines, "References: ")) >= 0 and "is the first frame." in lines[at]:
            # only its tag was deleted: the sentence gets it back, never half of it (QA-2)
            lines[at] = re.sub(r"(\[[^\]]*\]\s*)?is the first frame\.", first, lines[at], count=1)
            lines[at] = re.sub(r"^References:\s+", "References: ", lines[at])
        elif at >= 0:
            lines[at] = lines[at].replace("References: ", f"References: {first} ", 1)
        else:
            lines.insert(1, f"References: {first}")
    if _line(lines, "Summary: ") < 0 and planned:
        what = " ".join(shots[i].action for i in planned.shot_ids if i in shots)
        lines.insert(max(_line(lines, "References: "), 0) + 1, f"Summary: {what}".strip())
    if len(lines) < 2 or not lines[-2].startswith("Keep: "):
        who = list(dict.fromkeys(CAST.findall(clip.prompt)))
        tags = {w: re.search(rf"(\[Image\d+\]) (?:is|are) {re.escape(w)}", clip.prompt)[1]
                for w in who}  # fmt: skip
        held = "; ".join(f"{w} as in {tags[w]}, the same look in every shot" for w in who)
        lines.insert(
            len(lines) - 1, f"Keep: {held or 'every person and screen as in their pictures'}."
        )
    seconds = planned.seconds if planned else clip.seconds
    lines = _quiet(_retime(lines, seconds))
    prompt = "\n".join(lines)
    if prompt == clip.prompt.strip() and seconds == clip.seconds:
        return clip
    return clip.model_copy(update={"prompt": prompt, "seconds": seconds})


SHOT = re.compile(r"^(Shot \d+ \| )(\d+)[-–](\d+)( s\..*)$")


def _retime(lines: list[str], seconds: int) -> list[str]:
    """Shots back to back from 0 to the clip's length, each keeping its length (at least 1 s);
    the longest give a second each when they run over, the last takes up any gap. Unchanged
    when the shots can't fit (more shots than seconds) or a time isn't whole seconds."""
    at = [i for i, x in enumerate(lines) if x.startswith("Shot ")]
    found = [SHOT.match(lines[i]) for i in at]
    if not at or not all(found):
        return lines
    lengths = [max(int(m[3]) - int(m[2]), 1) for m in found]
    while sum(lengths) > seconds and max(lengths) > 1:
        lengths[lengths.index(max(lengths))] -= 1
    if sum(lengths) > seconds:
        return lines
    lengths[-1] += seconds - sum(lengths)
    out, start = list(lines), 0
    for i, m, n in zip(at, found, lengths, strict=True):
        if (int(m[2]), int(m[3])) != (start, start + n):  # a right one stays as written
            out[i] = f"{m[1]}{start}-{start + n}{m[4]}"
        start += n
    return out


def _quiet(lines: list[str]) -> list[str]:
    """Every shot without a spoken line ends with "No one speaks." (the check's rule)."""
    from app.prompts.check import QUOTED

    at = [i for i, x in enumerate(lines) if SHOT.match(x)]
    end = next((i for i, x in enumerate(lines) if x.startswith("Keep: ")), len(lines))
    out = list(lines)
    for a, b in zip(at, [*at[1:], max(end, at[-1] + 1)] if at else [], strict=True):
        shot = "\n".join(lines[a:b])
        if not QUOTED.search(shot) and "No one speaks." not in shot:
            last = max(i for i in range(a, b) if lines[i].strip())
            out[last] = f"{lines[last].rstrip()} No one speaks."
    return out


def fixing(db: Session, row: ProjectClip) -> Job | None:
    """The free fix already on its way for this clip, if one is."""
    jobs = db.scalars(select(Job).where(Job.project_id == row.project_id, Job.status.in_(WAITING)))
    return next(
        (j for j in jobs if j.input.get("fix") and j.input.get("clip_ids") == [row.clip_id]), None
    )


def queue_fix(db: Session, user, project: Project, row: ProjectClip, problems: list[str]) -> Job:
    """Fix this clip's prompt with Claude, free (charged to no budget or week; its dollars
    are in Usage): one clip, told which problems to clear, never its spoken lines."""
    from app.job_brand import brand_for

    bd = newest(db, project)
    waiting = _waiting(db, project)
    if "clip_take" in waiting:
        raise HTTPException(409, "Wait for the clips being made to finish first.")
    if "clip_prompts" in waiting:
        raise HTTPException(409, "Clip prompts are already being written for this project.")
    clip = row.clip_id
    data = job_input(db, project, bd, [clip])
    fix = ("Rewrite only this clip's prompt, keeping every spoken line word for word, and "
           f"clear these problems: {'; '.join(problems)}")  # fmt: skip
    data = {**data, "prompt": f"{data['prompt']}\n<fix clip=\"{clip}\">\n{escape(fix)}\n</fix>",
            "clip_ids": [clip], "fix": True, "before": row.prompt}  # fmt: skip
    job = Job(workspace_id=project.workspace_id, created_by_id=user.id, approved_by_id=user.id,
              kind="write-claude", provider="claude", input=data, project_id=project.id,
              brand_id=brand_for(db, project, data), credits=0, status="queued")  # fmt: skip
    db.add(job)
    row.free_fix_used = True
    db.commit()
    return job


WAITING = ("queued", "running", "needs_owner_approval")


def newest(db: Session, project: Project) -> BreakdownVersion | None:
    return db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )


def is_stale(db: Session, row: ProjectClip, latest_bd: BreakdownVersion | None) -> bool:
    """Made from an older breakdown, or the breakdown is for an older script version."""
    from app.routes.scripts import latest

    working = latest(db, db.get(Project, row.project_id))
    return (
        not latest_bd
        or row.breakdown_id != latest_bd.id
        or bool(working and latest_bd.script_version != working.version)
    )


def to_rewrite(db: Session, project: Project, clip_id: str | None = None) -> list[str]:
    """The clips a rewrite is for: one clip, or every stale clip and any clip the newest
    breakdown has that doesn't exist yet. [] when there's nothing to rewrite."""
    bd = newest(db, project)
    if bd is None:
        return []
    rows = list(db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)))
    ids = [c.id for c in Breakdown.model_validate(bd.data).clips]
    if clip_id is not None:
        return [clip_id] if clip_id in ids else []
    have = {r.clip_id for r in rows}
    stale = {r.clip_id for r in rows if is_stale(db, r, bd)}
    return [i for i in ids if i in stale or i not in have] if rows else []


def calls(db: Session, project: Project, clip_ids: list[str] | None = None) -> int:
    """How many Claude calls writing these clips' prompts takes (a few clips each)."""
    bd = newest(db, project)
    return max(len(batches(Breakdown.model_validate(bd.data), clip_ids)) if bd else 0, 1)


def rewrite_price(db: Session, project: Project, clip_ids: list[str] | None = None) -> Decimal:
    """A Claude call's price per call it takes (QA-Live 6: 66 shots cost $1.02 against a
    3-credit price). The charge is the real cost, never above this (worker)."""
    from app.credits import estimate

    return estimate(db, project.workspace_id, "write-claude", Decimal(calls(db, project, clip_ids)))


def _waiting(db: Session, project: Project) -> set[str]:
    jobs = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    return {j.input.get("step") for j in jobs}


def queue_rewrite(db: Session, user, project: Project, clip_ids: list[str] | None) -> Job:
    """The clip-prompts call (paid) for `clip_ids` (None: every clip)."""
    from app.routes.jobs import enqueue

    bd = newest(db, project)
    if bd is None:
        raise HTTPException(409, "Make a breakdown first.")
    waiting = _waiting(db, project)
    if "clip_take" in waiting:  # a take on its way would land on a rewritten or removed clip
        raise HTTPException(409, "Wait for the clips being made to finish first.")
    if "clip_prompts" in waiting:
        raise HTTPException(409, "Clip prompts are already being written for this project.")
    data = {**job_input(db, project, bd, clip_ids), "clip_ids": clip_ids}
    units = max(len(data["batches"]), 1)  # one price per Claude call
    return enqueue(db, user, "write-claude", data, units=units, project=project, provider="claude")


def follow(db: Session, project: Project, user) -> Job | None:
    """After a breakdown change: stale clip prompts are rewritten by themselves (Reed,
    2026-10-26), like frames. Paid, so only within the video's budget or the editor's week
    (the owner's work too, as for looks Assets makes); past it, or while a take is being
    made, nothing is queued and Clips keeps its Rewrite button. Never blocks the change."""
    from app.credits import fits

    ids = to_rewrite(db, project)
    if not ids or "clip_take" in _waiting(db, project) or not user:
        return None
    if fits(db, project, user, rewrite_price(db, project, ids)):
        return None
    db.commit()  # a refusal rolls back: never take the breakdown change with it
    try:
        return queue_rewrite(db, user, project, ids)
    except HTTPException:
        return None
