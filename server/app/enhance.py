"""Enhance: Claude suggests marks on the editor's script (it never rewrites it). Marks are
anchored by line + exact quote; we compute the offsets, drop any we can't place, and later
apply the accepted ones to make a new version."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.models.brands import Brand, BrandScreen
from app.models.jobs import Job
from app.models.library import LibraryItem
from app.models.projects import Project
from app.models.scripts import ScriptVersion, Suggestion
from app.prompts import check
from app.prompts.schemas import EnhanceResult


def escape(text: str) -> str:
    """Keep user text from closing our tags early."""
    return text.replace("</", "<\\/")


def screens_of(db: Session, brand: Brand) -> list[BrandScreen]:
    return list(db.scalars(select(BrandScreen).where(BrandScreen.brand_id == brand.id)))


def job_input(db: Session, project: Project, version: ScriptVersion) -> dict:
    """The Claude call for Enhance: fixed system parts (cached) + this project's message."""
    brand = db.get(Brand, project.brand_id)
    screens = [
        {"id": s.id, "name": s.name, "tags": s.tags, "default_for": s.default_for}
        for s in screens_of(db, brand)
    ]
    brand_dict = {
        "name": brand.name,
        "tone_notes": brand.tone_notes,
        "never_say": brand.never_say,
        "legal_line": brand.legal_line,
    }
    cast = [db.get(LibraryItem, i) for i in project.cast_ids]
    brief = (
        f"Goal: {project.goal or '-'}\nPlatform: {project.platform or '-'}\n"
        f"Aspect: {project.aspect_ratio}\nPlanned length: {project.planned_seconds} s\n"
        f"Format: {project.format or '-'}"
    )
    cast_lines = "\n".join(f"char:{c.id} | {c.name} | {c.notes}" for c in cast if c)
    message = (
        f"<brief>\n{escape(brief)}\n</brief>\n<cast>\n{escape(cast_lines)}\n</cast>\n"
        f"<script>\n{escape(prompts.number_lines(version.text))}\n</script>"
    )
    return {
        "step": "enhance",
        "project_id": project.id,
        "script_version": version.version,
        "system": [prompts.system("enhance"), prompts.brand_block(brand_dict, screens)],
        "prompt": message,
    }


def save_suggestions(db: Session, job: Job) -> None:
    """Turn the answer into Suggestion rows. Marks that fail the checks are dropped; the
    problems are kept in the job output for the owner/Director to see."""
    project = db.get(Project, job.input["project_id"])
    version = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.project_id == project.id,
            ScriptVersion.version == job.input["script_version"],
        )
    )
    result = EnhanceResult.model_validate(job.output)
    brand_screens = {f"screen:{s.id}": s for s in screens_of(db, db.get(Brand, project.brand_id))}
    problems = check.enhance(
        version.text, result, {k: s.default_for for k, s in brand_screens.items()}
    )
    bad = {p.split(":", 1)[0] for p in problems}
    starts = _line_starts(version.text)
    lines = version.text.splitlines()
    kept = 0
    for s in result.suggestions:
        if s.id in bad:
            continue
        n = s.anchor.line
        start = starts[n - 1] + lines[n - 1].index(s.anchor.quote)
        screen = brand_screens.get(s.screen_id or "")
        db.add(
            Suggestion(
                project_id=project.id,
                script_version=version.version,
                job_id=job.id,
                key=s.id,
                kind=s.kind,
                line=n,
                quote=s.anchor.quote,
                start=start,
                end=start + len(s.anchor.quote),
                placement=s.placement,
                text=s.text,
                screen_id=screen.id if screen else None,
                reason=s.reason,
            )
        )
        kept += 1
    job.output = {**job.output, "kept": kept, "dropped": problems}


def _line_starts(text: str) -> list[int]:
    starts, pos = [], 0
    for line in text.splitlines(keepends=True):
        starts.append(pos)
        pos += len(line)
    return starts or [0]


def apply(text: str, marks: list[Suggestion]) -> tuple[str, list[str]]:
    """Apply accepted marks. Lines are added before/after the quote's line; `replace` swaps
    the quote (a cut removes it, and the line if nothing is left). Marks whose spans overlap
    an earlier-applied one are skipped and reported."""
    edits = []  # (position, end, new text, key)
    lines_end = _line_ends(text)
    starts = _line_starts(text)
    for m in marks:
        line_start, line_end = starts[m.line - 1], lines_end[m.line - 1]
        if m.placement == "before":
            edits.append((line_start, line_start, f"{m.text}\n", m.key))
        elif m.placement == "after":
            edits.append((line_end, line_end, f"\n{m.text}", m.key))
        else:
            start, end = m.start, m.end
            if not m.text and text[line_start:line_end].strip() == m.quote.strip():
                start, end = line_start, min(line_end + 1, len(text))  # drop the whole line
            edits.append((start, end, m.text, m.key))
    skipped, taken = [], []
    for edit in sorted(edits, key=lambda e: (e[0], e[1])):
        if any(edit[0] < t[1] and t[0] < edit[1] for t in taken):
            skipped.append(edit[3])
        else:
            taken.append(edit)
    for start, end, new, _ in sorted(taken, key=lambda e: (e[0], e[1]), reverse=True):
        text = text[:start] + new + text[end:]
    return text, skipped


def _line_ends(text: str) -> list[int]:
    ends, pos = [], 0
    for line in text.splitlines(keepends=True):
        pos += len(line)
        ends.append(pos - (len(line) - len(line.rstrip("\r\n"))))
    return ends or [0]
