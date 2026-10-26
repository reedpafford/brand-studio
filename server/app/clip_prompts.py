"""Clip prompts: Claude writes one Seedance prompt per clip of the newest breakdown, with its
references (storyboard frame, cast, place, screens, voice samples). Saved per clip with the
problems `check.clip_prompts` finds; the editor can edit them before generating."""

import json

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

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
from app.prompts.schemas import Breakdown, ClipPrompt, ClipPrompts
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


def clip_problems(db: Session, project: Project, bd: Breakdown, clip: ClipPrompt) -> list[str]:
    m = video_model()
    problems = check.clip_prompts(
        bd, ClipPrompts(clips=[clip]), m.max_reference_images, m.max_reference_audios
    )
    known = assets(db, project)
    for ref in clip.references:
        if ref.id not in known:
            problems.append(f"{clip.clip_id}: unknown reference {ref.id}")
        elif known[ref.id][1] != ref.kind:
            kind = {"image": "a picture", "audio": "a sound"}.get(ref.kind, f"a {ref.kind}")
            problems.append(f"{clip.clip_id}: {ref.id} is attached as {kind} but isn't one")
    return plain(problems, names(known))


def save_clip_prompts(db: Session, job: Job) -> None:
    """Replace the project's clips with Claude's new prompts."""
    project = db.get(Project, job.input["project_id"])
    bd_row = db.get(BreakdownVersion, job.input["breakdown_id"])
    bd = Breakdown.model_validate(bd_row.data)
    result = ClipPrompts.model_validate(job.output)
    old = select(ProjectClip.id).where(ProjectClip.project_id == project.id)
    db.execute(update(ProjectClip).where(ProjectClip.id.in_(old)).values(picked_take_id=None))
    db.execute(delete(ClipTake).where(ClipTake.clip_id.in_(old)))  # the files stay in storage
    db.execute(delete(ProjectClip).where(ProjectClip.project_id == project.id))
    for c in result.clips:
        db.add(
            ProjectClip(
                project_id=project.id,
                breakdown_id=bd_row.id,
                job_id=job.id,
                clip_id=c.clip_id,
                seconds=c.seconds,
                prompt=c.prompt,
                references=[r.model_dump() for r in c.references],
                problems=clip_problems(db, project, bd, c),
            )
        )
