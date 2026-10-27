"""Clip prompts: Claude writes one Seedance prompt per clip of the newest breakdown, with its
references (storyboard frame, cast, place, screens, voice samples). Saved per clip with the
problems `check.clip_prompts` finds; the editor can edit them before generating."""

import json
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import cut_in
from app.advice import names, plain
from app.breakdown import video_model, video_model_block
from app.enhance import escape, project_context
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts import check
from app.prompts.schemas import Breakdown, ClipPrompt, ClipPrompts, Reference
from app.storyboard import CHAR, LEFT_OUT, _name, _renumber, _same, left_out, nearest_first
from app.storyboard import assets as picture_assets

# asset id -> (line for the prompt, kind for Seedance, its file ids)
Assets = dict[str, tuple[str, str, list[int]]]


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


def job_input(db: Session, project: Project, bd: BreakdownVersion) -> dict:
    system, _ = project_context(db, project, "clip_prompts")
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
    }


TAGS = re.compile(r"(\[Image)(\d+)\]")


def _pictures(known: Assets) -> dict[str, tuple[str, list[int]]]:
    return {k: (line, files) for k, (line, _, files) in known.items()}


def _cast(bd: Breakdown, clip_id: str, pics: dict) -> list[str]:
    """The clip's characters in the order they first appear, nearest the camera first."""
    clip = next((c for c in bd.clips if c.id == clip_id), None)
    shots = {s.id: s for scene in bd.scenes for s in scene.shots}
    out: list[str] = []
    for sid in clip.shot_ids if clip else []:
        for ref in nearest_first(shots[sid], pics) if sid in shots else []:
            if not any(_same(pics, ref, r) for r in out):
                out.append(ref)
    return out


def _screens(bd: Breakdown, clip_id: str) -> list[str]:
    """The screens the clip's shots show, the one shown last (the payoff) last."""
    clip = next((c for c in bd.clips if c.id == clip_id), None)
    shots = {s.id: s for scene in bd.scenes for s in scene.shots}
    out: list[str] = []
    for sid in clip.shot_ids if clip else []:
        for screen in shots[sid].screen_ids if sid in shots else []:
            out = [s for s in out if s != screen] + [screen]
    return out


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
    images = [r for r in clip.references if r.kind == "image"]
    others = [r for r in clip.references if r.kind != "image"]
    first = [r for r in images if r.id.startswith("frame:")]
    people = [r for r in images if r.id.startswith(CHAR)]
    objects = [r for r in images if r not in first and r not in people]
    cast = [c for c in _cast(bd, clip.clip_id, pics) if pics.get(c, ("", []))[1]]
    missing = [c for c in cast if not any(_same(pics, c, r.id) for r in people)]

    def rank(r: Reference) -> int:
        return next((i for i, c in enumerate(cast) if _same(pics, r.id, c)), len(cast))

    room = len(people) + len(missing)
    if limit := video_model().max_reference_images:
        room = min(room, max(limit - len(first) - len(objects), 0))
    added = [Reference(kind="image", id=c, role=f"{_name(pics, c)}'s look") for c in missing]
    if trim:  # stable: people not in the clip stay last
        people = sorted(people + added, key=rank)[:room]
    elif added := added[: max(room - len(people), 0)]:
        people = sorted(people + added, key=rank)
    new = first + people + objects
    want = [s for s in _screens(bd, clip.clip_id) if s not in {r.id for r in new} and s in pics]
    if limit := video_model().max_reference_images:  # people first; the payoff screen kept
        room = max(limit - len(new), 0)
        want = want[-room:] if room else []
    new += [Reference(kind="image", id=s, role=f"{_name(pics, s)} screen") for s in want]
    if new == images:
        return clip
    moved = {i + 1: new.index(r) + 1 for i, r in enumerate(images) if r in new}
    dropped = {i + 1: _name(pics, r.id) for i, r in enumerate(images) if r not in new}
    prompt = _renumber(clip.prompt, moved, dropped, TAGS)
    for r in (r for r in new if r not in images):
        who, tag = _name(pics, r.id), f"[Image{new.index(r) + 1}]"
        if r.id in want:
            prompt = _add(prompt, "References: ", f"{tag} is the {who} screen, exactly as it is.")
            continue
        prompt = _add(prompt, "References: ", f"{tag} is {who}.")
        prompt = _add(prompt, "Keep: ", f"{who} as in {tag}, the same look as on their sheet.")
    return clip.model_copy(update={"prompt": prompt, "references": new + others})


def clip_problems(db: Session, project: Project, bd: Breakdown, clip: ClipPrompt) -> list[str]:
    """A character in the clip without an approved look is flagged by name (a role not cast
    yet waits for Assets and is never a problem); sheets are attached by `with_cast`."""
    m = video_model()
    problems = check.clip_prompts(
        bd, ClipPrompts(clips=[clip]), m.max_reference_images, m.max_reference_audios
    )
    known = assets(db, project)
    pics = _pictures(known)
    for c in _cast(bd, clip.clip_id, pics):
        if c in pics and (pics[c][1] or pics[c][0].endswith("(no look yet)")):
            continue
        if not any(_same(pics, c, r.id) for r in clip.references):
            problems.append(f"{_name(pics, c)} has no approved look yet. Approve one in Assets.")
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
    and check it again. Free and idempotent: on deploy for clips saved before
    (app.seed refresh). Returns how many clips changed."""
    known, changed = assets(db, project), 0
    breakdowns: dict[int, Breakdown] = {}
    for row in db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id)):
        if row.breakdown_id not in breakdowns:
            data = db.get(BreakdownVersion, row.breakdown_id).data
            breakdowns[row.breakdown_id] = Breakdown.model_validate(data)
        bd = breakdowns[row.breakdown_id]
        was = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, prompt=row.prompt,
                         references=[Reference(**r) for r in row.references])  # fmt: skip
        now = with_cast(db, project, was, bd, known, trim=False)
        problems = clip_problems(db, project, bd, now) + [
            p for p in row.problems or [] if p.startswith(LEFT_OUT)
        ]  # what an earlier trim left out stays said
        if any(p.lower().startswith("more references than") for p in problems):
            now = _cap(with_cast(db, project, was, bd, known), known)  # never a dead end
            kept = {r.id for r in now.references}
            gone = [_name(_pictures(known), r.id) for r in was.references if r.id not in kept]
            limit = video_model().max_reference_images
            problems = clip_problems(db, project, bd, now) + left_out(gone, limit)
        if now == was and problems == (row.problems or []):
            continue
        row.prompt, row.references = now.prompt, [r.model_dump() for r in now.references]
        row.problems = problems
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
    for c in result.clips:
        if c.clip_id not in wanted or (only is not None and c.clip_id not in only):
            continue
        c = with_cast(db, project, c, bd, known)
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
        row.problems, row.kept = clip_problems(db, project, bd, c), []
        row.approved, row.prompt_ok, row.change = False, False, None
        if job.input.get("fix"):  # Fix this clip's prompt: its Before and After
            before = job.input.get("before") or ""
            row.change = {"note": "Fix this clip's prompt", "status": "done", "before": before,
                          "after": c.prompt, "unchanged": before == c.prompt}  # fmt: skip


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
    prompt = "\n".join(lines)
    if prompt == clip.prompt.strip() and seconds == clip.seconds:
        return clip
    return clip.model_copy(update={"prompt": prompt, "seconds": seconds})


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
    data = job_input(db, project, bd)
    clip = row.clip_id
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


def rewrite_price(db: Session, project: Project) -> Decimal:
    """One clip-prompts call, whatever it rewrites; never charged above it (worker)."""
    from app.credits import estimate

    return estimate(db, project.workspace_id, "write-claude", Decimal(1))


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
    data = {**job_input(db, project, bd), "clip_ids": clip_ids}
    return enqueue(db, user, "write-claude", data, project=project, provider="claude")


def follow(db: Session, project: Project, user) -> Job | None:
    """After a breakdown change: stale clip prompts are rewritten by themselves (Reed,
    2026-10-26), like frames. Paid, so only within the video's budget or the editor's week
    (the owner's work too, as for looks Assets makes); past it, or while a take is being
    made, nothing is queued and Clips keeps its Rewrite button. Never blocks the change."""
    from app.credits import fits

    ids = to_rewrite(db, project)
    if not ids or "clip_take" in _waiting(db, project) or not user:
        return None
    if fits(db, project, user, rewrite_price(db, project)):
        return None
    db.commit()  # a refusal rolls back: never take the breakdown change with it
    try:
        return queue_rewrite(db, user, project, ids)
    except HTTPException:
        return None
