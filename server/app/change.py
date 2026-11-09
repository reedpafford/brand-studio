"""Change it in plain English (change-notes.md §1): a note rewrites a still's or a clip's
prompt (a small Claude call), then the still, or a new take, is made from the new prompt. The
note never changes what's said (`check.redo_note`, before anything is charged). If the prompt
comes back the same, nothing is made and nothing is charged. The old still or take stays with
the prompt it was made from, so picking it back is the Undo. A nearly-right Omni take is edited
instead of made again (`editable`)."""

import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import advice, clip_prompts, clip_takes, model_map, prompts, storyboard
from app.credits import estimate
from app.enhance import escape
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import WAITING, Job
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts import check
from app.prompts.schemas import Breakdown, ChangedPrompt, ClipPrompt, Frame, Reference

Row = StoryboardFrame | ProjectClip
# Omni's edit (docs/prompting/omni-1.2.md §9; Reed, 9 Nov): only what the note says changes
KEEP = ("Keep the people, their dialogue and voices, the timing and the camera move the same; "
        "keep everything else the same.")  # fmt: skip
SAYS = re.compile(r"\b(?:say|says|said|saying|lines?|words?|dialogue|voices?|accent|pronounc\w*|"
                  r"louder|quieter|speak\w*|talk\w*|tone|sing\w*|lyrics?)\b", re.I)  # fmt: skip
TIMED = re.compile(r"\b(?:faster|slower|quicker|longer|shorter|pauses?|timing|seconds?|pace|"
                   r"speed|sooner|earlier|later|extend\w*|trim\w*)\b", re.I)  # fmt: skip
EDITING = "An edit of take {n}: only what the note says changes; the acting, timing and voice stay."
NEW_TAKE = {
    "says": "A new take, not an edit: the note changes what's said or how it's said.",
    "timed": "A new take, not an edit: the note changes the timing, which an edit keeps.",
    "long": "A new take, not an edit: the take is over {most} s, longer than Omni can edit.",
    "length": "A new take, not an edit: the clip's length changed since this take.",
    "pictures": "A new take, not an edit: the change attaches a picture, which an edit can't take.",
}


def _target(row: Row) -> str:
    return "frame" if isinstance(row, StoryboardFrame) else "clip"


def _has_take(db: Session, row: ProjectClip) -> bool:
    return bool(db.scalar(select(func.count(ClipTake.id)).where(ClipTake.clip_id == row.id)))


def _seconds(db: Session, take: ClipTake) -> int:
    """How long a take is: what it was asked for (an edit keeps its source's length)."""
    return int((db.get(Job, take.job_id).input.get("input") or {}).get("duration") or 0)


def editable(db: Session, project: Project, row: ProjectClip,
             note: str = "") -> tuple[ClipTake | None, str]:  # fmt: skip
    """Omni's edit of the take in use (Reed, 9 Nov: "Change this…" on a nearly-right Omni take
    edits it; it can't change what's said): (the take, its line) when it's edited; (None, why)
    when it's Omni's but the note needs a new take; (None, "") for any other take."""
    take = db.get(ClipTake, row.picked_take_id) if row.picked_take_id else None
    made = db.get(Job, take.job_id) if take is not None and take.job_id else None
    model = model_map.of_clip(project, row)
    if made is None or model.edit is None or made.input.get("model") != model.id:
        return None, ""
    seconds = _seconds(db, take)
    why = ("says" if SAYS.search(note) else "timed" if TIMED.search(note)
           else "long" if seconds > model.edit.max_seconds
           else "length" if seconds != model_map.billed(model, row.seconds) else "")  # fmt: skip
    if why:
        return None, NEW_TAKE[why].format(most=model.edit.max_seconds)
    return take, EDITING.format(n=take.number)


def _edit(db: Session, data: dict, take: ClipTake, note: str) -> dict:
    """A take's job (`clip_takes.take_input`: its checks, its records) made an edit of `take`:
    the take as `video`, the note and what stays as its prompt, and no pictures."""
    kept = {k: v for k, v in data.items()
            if k not in ("fit_images_to", "exact_file_ids", "screen_figures")}  # fmt: skip
    prompt = f"{note.strip().rstrip('.')}. {KEEP}" if note.strip() else KEEP
    return {**kept, "edit": True, "edit_of": take.id, "files": {"video": [take.file_id]},
            "input": {"prompt": prompt, "duration": _seconds(db, take),
                      "resolution": data["input"]["resolution"]}}  # fmt: skip


def _draw(db: Session, project: Project, row: Row, before: str = "", check: bool = True,
          note: str = "", edit: ClipTake | None = None) -> tuple[str, dict, int]:  # fmt: skip
    """The job that makes the still, the new take, or the edit of `edit`: (kind, input,
    units). `check` False: only its price is read, so a cast waiting for the OK doesn't stop
    the price showing."""
    if isinstance(row, StoryboardFrame):
        data = storyboard.render_input(db, project, row, check=check)
        return "image", {**data, "was_prompt": before or row.prompt}, 1
    data = clip_takes.take_input(db, project, row, check=check)
    if edit:  # billed on the take's own seconds, which it keeps
        data = _edit(db, data, edit, note)
        return "video", data, data["input"]["duration"]
    return "video", data, model_map.billed(model_map.of_clip(project, row), row.seconds)


def clip_of(db: Session, frame: StoryboardFrame) -> ProjectClip | None:
    """The clip a still is the first frame of, in the same breakdown."""
    return db.scalar(select(ProjectClip).where(
        ProjectClip.project_id == frame.project_id, ProjectClip.clip_id == frame.clip_id,
        ProjectClip.breakdown_id == frame.breakdown_id).limit(1))  # fmt: skip


def take_after(db: Session, frame: StoryboardFrame) -> ProjectClip | None:
    """A still whose clip already has a take: changing the still makes the clip again from it
    (S-gaps-08 2: "a new still and a new take"), so the take in the cut never shows an old
    still. None before the first take: then only the still is drawn."""
    clip = clip_of(db, frame)
    return clip if clip is not None and _has_take(db, clip) else None


def _then(db: Session, project: Project, row: Row, check: bool = True, note: str = "") -> Decimal:
    """What making it again costs once the prompt is rewritten (0 for a clip with no take):
    a still's redraw, and its clip's new take (or its take's edit) when it has one. Checked
    (the press): refused up front while its cast or places wait for the OK."""
    if isinstance(row, StoryboardFrame) or _has_take(db, row):
        edit = None if isinstance(row, StoryboardFrame) else editable(db, project, row, note)[0]
        kind, data, units = _draw(db, project, row, check=check, note=note, edit=edit)
        made = estimate(db, project.workspace_id, kind, Decimal(units), data)
        if isinstance(row, StoryboardFrame):
            clip = take_after(db, row)
            return made + (_then(db, project, clip, check) if clip is not None else Decimal(0))
        from app import take_watch

        return made + take_watch.rides(db, project, row)  # its watch, while watches are on
    return Decimal(0)


def credits(db: Session, project: Project, row: Row) -> Decimal:
    """Change it · N: rewriting the prompt, plus the still or the new take (a clip with no
    take yet only has its prompt rewritten)."""
    write = estimate(db, project.workspace_id, "write-claude", Decimal(1))
    return write + _then(db, project, row, check=False)


def start(db: Session, user: User, project: Project, row: Row, note: str) -> Job:
    """Check the note, then queue the rewrite. 422 (nothing charged) for a note that changes
    the dialogue; 409 while this one is being made, or past an editor's week."""
    from app.routes.jobs import enqueue

    note = note.strip()
    if not note:
        raise HTTPException(422, "Say what should change.")
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    if wrong := check.redo_note(note, bd, row.clip_id):
        raise HTTPException(422, " ".join(wrong))
    target = _target(row)
    if target == "clip":
        clip_takes.fits_model(db, project, row)
    key = "frame_id" if target == "frame" else "project_clip_id"
    pending = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(WAITING)))
    for job in pending:
        mine = job.input.get("step") == "change" and job.input.get("target_id") == row.id
        if job.input.get(key) == row.id or (mine and job.input.get("target") == target):
            raise HTTPException(409, "This one is still being made.")
    then = _then(db, project, row, note=note)
    data = {
        "step": "change",
        "project_id": project.id,
        "target": target,
        "target_id": row.id,
        "note": note,
        "before": row.prompt,
        "system": [prompts.system("change")],
        "prompt": (
            f"<kind>{'still' if target == 'frame' else 'clip'}</kind>\n"
            f"<prompt>\n{escape(row.prompt)}\n</prompt>\n<note>\n{escape(note)}\n</note>"
        ),
        "max_tokens": 16000,  # the whole prompt comes back: a 24 s clip ran out of room at 4000
        "then": str(then),  # the redraw it starts: shown with it while it waits (rule 36)
    }
    if target == "frame" and take_after(db, row) is not None:
        data["then_take"] = True  # the clip is made again once the still lands (paid here)
    # The whole price is checked in one locked step, against the video's budget.
    job = enqueue(db, user, "write-claude", data, project=project, provider="claude", hold=then)
    was = {"was_take_id": row.picked_take_id} if target == "clip" else {"was_file_id": row.file_id}
    how = editable(db, project, row, note)[1] if target == "clip" and _has_take(db, row) else ""
    row.change = {"note": note, "job_id": job.id, "status": "changing", **was,
                  **({"how": how} if how else {})}  # fmt: skip
    db.commit()
    return job


def fit(db: Session, project: Project, row: ProjectClip, after: str,
        note: str) -> tuple[ClipPrompt, list[str]]:  # fmt: skip
    """A clip's rewritten prompt with its cast attached and its shape put right in code (free),
    and the problems it would have."""
    bd = Breakdown.model_validate(db.get(BreakdownVersion, row.breakdown_id).data)
    clip = ClipPrompt(clip_id=row.clip_id, seconds=row.seconds, prompt=after,
                      references=[Reference(**r) for r in row.references])  # fmt: skip
    clip = clip_prompts.with_cast(db, project, clip, bd, trim=False, note=note)
    clip = clip_prompts.repair_shape(clip, bd)  # what code can fix, free, first
    return clip, clip_prompts.clip_problems(db, project, bd, clip)


def use(db: Session, row: ProjectClip, clip: ClipPrompt, problems: list[str],
        by_id: int | None) -> None:  # fmt: skip
    """The rewritten prompt in hand: a new version (Versions keeps the one before)."""
    row.prompt_ok = False  # a prompt written again needs reading again
    clip_prompts.before_change(db, row)
    row.prompt, row.references = clip.prompt, [r.model_dump() for r in clip.references]
    row.seconds, row.problems, row.approved = clip.seconds, problems, False
    clip_prompts.log_prompt(db, row, by_id)  # OR3: Versions


UNFINISHED = "That change didn't finish, so nothing was charged. Try again."


def change_failed(db: Session, job: Job) -> None:
    """A rewrite that failed (Reed's c5: the answer ran out of room) or couldn't be saved: the
    still or clip says so, with its note kept for Try again, never "Changing…" for ever. A
    failed job isn't counted (credits.COUNTED), so nothing was charged."""
    job.error = UNFINISHED
    model = StoryboardFrame if job.input.get("target") == "frame" else ProjectClip
    row = db.get(model, job.input.get("target_id") or 0, populate_existing=True)  # read fresh
    if row and (row.change or {}).get("job_id") == job.id and row.change["status"] == "changing":
        row.change = {**row.change, "status": "failed", "error": UNFINISHED}


def save_changed(db: Session, job: Job) -> None:
    """The rewrite is back: the same prompt makes nothing and costs nothing; a new one is
    saved (the old one stays with its still or take) and the still or a new take is made."""
    from app.routes.jobs import enqueue

    i = job.input
    model = StoryboardFrame if i["target"] == "frame" else ProjectClip
    row = db.get(model, i["target_id"], populate_existing=True)  # read fresh: Undo's pick
    if row is None or row.project_id != i["project_id"]:
        return
    before, after = i["before"], ChangedPrompt.model_validate(job.output).prompt.strip()
    change = {**(row.change or {}), "note": i["note"], "job_id": job.id, "before": before,
              "after": after}  # fmt: skip
    if row.prompt != before:  # edited by hand while the note was read: never overwrite it
        row.change = {**change, "status": "failed",
                      "error": "The prompt was edited meanwhile. Try the note again."}  # fmt: skip
        return
    if " ".join(after.split()) == " ".join(before.split()):
        job.credits = Decimal(0)  # nothing is made, so nothing is charged
        row.change = {**change, "status": "unchanged", "unchanged": True}
        return
    project = db.get(Project, row.project_id)
    if isinstance(row, ProjectClip) and row.picked_take_id:  # an older take: keep its prompt
        take = db.get(ClipTake, row.picked_take_id)
        take.prompt = take.prompt if take.prompt is not None else before
    row.prompt, row.approved = after, False
    row.change = {**change, "status": "done", "unchanged": False}
    bd, edit = db.get(BreakdownVersion, row.breakdown_id), None
    if isinstance(row, StoryboardFrame):
        frame = Frame(clip_id=row.clip_id, shot_id=row.shot_id, prompt=after,
                      reference_ids=row.reference_ids)  # fmt: skip
        frame = storyboard.with_cast(db, project, frame, Breakdown.model_validate(bd.data),
                                     note=i["note"])  # "use the real bag": attached  # fmt: skip
        row.prompt, row.reference_ids = frame.prompt, frame.reference_ids
        row.problems = storyboard.frame_problems(db, project, frame, row.breakdown_id)
    else:
        had = {r["id"] for r in row.references or []}
        use(db, row, *fit(db, project, row, after, i["note"]), job.created_by_id)
        if not _has_take(db, row):
            return  # before any take, a change only rewrites the prompt
        edit, how = editable(db, project, row, i["note"])
        if edit and {r["id"] for r in row.references} - had:  # "use the real bag": attached
            edit, how = None, NEW_TAKE["pictures"]
        row.change = {**row.change, **({"how": how} if how else {})}
        if stops := advice.stops(row):  # never pay for a take from a prompt with a problem
            fix = stops[0].rstrip(".")
            row.change = {**row.change, "status": "failed", "error": f"The new prompt has a "
                          f"problem to fix first ({fix}). Nothing was charged for a take: press "
                          "Fix this clip's prompt (free), then Another take."}  # fmt: skip
            return
    db.commit()  # the new prompt is a paid answer: a refused still (it rolls back) keeps it
    try:
        kind, data, units = _draw(db, project, row, before, note=i["note"], edit=edit)
        if i.get("then_take"):
            data["then_take"] = True  # storyboard.save_still makes the clip's new take
        user = db.get(User, job.created_by_id)
        made = enqueue(db, user, kind, data, units=units, project=project,
                       provider="replicate", prepaid=True)  # fmt: skip
        row.change = {**row.change, "made_job_id": made.id}
        if not isinstance(row, StoryboardFrame):  # a cut watch's redo names this take
            from app import watch_cut

            watch_cut.relink(db, row, job.id, made.id)
    except HTTPException as e:  # e.g. a sheet unapproved meanwhile: the new prompt stays
        row.change = {**row.change, "status": "failed", "error": e.detail}
