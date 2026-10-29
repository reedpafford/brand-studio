"""Enhance: Claude suggests marks on the editor's script (it never rewrites it). Marks are
anchored by line + exact quote; we compute the offsets, drop any we can't place or that
add spoken words, and later add the accepted ones as direction lines. The schema allows only
before/after marks, so the script's own words never change."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.cast_roles import cast_roles, plays
from app.models.brands import Brand, BrandScreen
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.models.scripts import ScriptVersion, Suggestion
from app.prompts import check
from app.prompts.schemas import EnhanceResult

HEADING = re.compile(r"(SCENE\b|INT\.|EXT\.|INT/EXT\b)")  # scene headings (uppercase)


def escape(text: str) -> str:
    """Keep user text from closing our tags early."""
    return text.replace("</", "<\\/")


def escape_block(block: str) -> str:
    """A whole `<tag>…</tag>` block (e.g. prompts.reference_block) with only its inside
    escaped, so its own closing tag still closes it."""
    found = re.fullmatch(r"(<(\w+)>\n?)(.*?)(\n?</\2>)", block, re.S)
    return f"{found[1]}{escape(found[3])}{found[4]}" if found else escape(block)


def screens_of(db: Session, brand: Brand) -> list[BrandScreen]:
    live = select(BrandScreen).where(
        BrandScreen.brand_id == brand.id, BrandScreen.deleted_at.is_(None)
    )
    return list(db.scalars(live))


def project_screens(db: Session, project: Project) -> list[BrandScreen]:
    """The brand's screens this project uses: for a product with variants, only the variant
    the brief picked (the first one if none is picked yet)."""
    screens = screens_of(db, db.get(Brand, project.brand_id))
    chosen = project.product_variants or {}
    first: dict[str, str] = {}
    for s in sorted(screens, key=lambda s: s.id):
        if s.product and s.variant:
            first.setdefault(s.product, s.variant)
    return [
        s
        for s in screens
        if not (s.product and s.variant) or s.variant == chosen.get(s.product, first[s.product])
    ]


def screen_name(s: BrandScreen) -> str:
    """'Chicken bag' as is; a name that doesn't say its variant gets it: 'Bag (Chicken)'."""
    return f"{s.name} ({s.variant})" if s.variant.lower() not in s.name.lower() else s.name


def logo_only(s: BrandScreen, brand: Brand) -> bool:
    """A trading screen is never attached (every shot copied its token, QA-Live on video #16):
    the brand's logo goes and the screen is invented; home screens stay real (Current rules 14)."""
    return "trading" in s.tags and "product" not in s.tags and bool(brand.logo_file_id)


def _length(project: Project) -> str:
    if project.planned_seconds:
        return f"{project.planned_seconds} s"
    return "not set (the breakdown decides)"


def project_context(db: Session, project: Project, step: str) -> tuple[list[str], str]:
    """What every script-flow call starts with: the fixed system parts (step rules, then the
    brand; cached together) and the <brief> and <cast> for the user message."""
    brand = db.get(Brand, project.brand_id)
    screens = [
        {
            "id": s.id,
            "name": screen_name(s),
            "tags": s.tags,
            "default_for": s.default_for,
            "balance": s.balance,
            "logo_only": logo_only(s, brand),
        }
        for s in project_screens(db, project)
    ]
    brand_dict = {
        "name": brand.name,
        "tone_notes": brand.tone_notes,
        "never_say": brand.dont_list,
        "legal_line": brand.legal_line,
        "end_line": brand.end_line,
    }
    from app.storyboard import cast_looks

    cast = cast_looks(db, project)  # the same looks the breakdown check accepts
    brief = (
        f"Goal: {project.goal or '-'}\nPlatform: {project.platform or '-'}\n"
        f"Aspect: {project.aspect_ratio}\nPlanned length: {_length(project)}\n"
        f"Format: {project.format or '-'}"
    )
    roles = cast_roles(db, project)  # who plays whom, so a model never has to guess
    cast_lines = "\n".join(
        " | ".join(x for x in (f"char:{c.id}", c.name, plays(roles.get(c.id, [])), c.notes) if x)
        for c in cast
    )
    message = f"<brief>\n{escape(brief)}\n</brief>\n<cast>\n{escape(cast_lines)}\n</cast>"
    look = prompts.system(step, project.look or "house")  # the video's look (ST2)
    return [look, prompts.brand_block(brand_dict, screens)], message


def job_input(db: Session, project: Project, version: ScriptVersion) -> dict:
    """The Claude call for Enhance: fixed system parts (cached) + this project's message."""
    system, context = project_context(db, project, "enhance")
    script = escape(prompts.number_lines(version.text))
    return {
        "step": "enhance",
        "project_id": project.id,
        "script_version": version.version,
        "system": system,
        "prompt": f"{context}\n<script>\n{script}\n</script>",
    }


def draft_job_input(db: Session, script: Script, draft: ScriptDraft) -> dict:
    """Enhance on a library script version: the same call, with the script standing in for
    the project. Its text goes with the job, so marks on older words are never applied."""
    from app.script_preview import stand_in_project

    system, context = project_context(db, stand_in_project(db, script, draft), "enhance")
    numbered = escape(prompts.number_lines(draft.text))
    return {
        "step": "enhance",
        "script_id": script.id,
        "draft_id": draft.id,  # not script_draft_id, which marks a breakdown preview
        "script_text": draft.text,
        "system": system,
        "prompt": f"{context}\n<script>\n{numbered}\n</script>",
    }


def save_suggestions(db: Session, job: Job) -> None:
    """Turn the answer into Suggestion rows. Marks that fail the checks are dropped; the
    problems are kept in the job output for the owner/Director to see."""
    from app.script_preview import stand_in_project

    if draft_id := job.input.get("draft_id"):
        draft = db.get(ScriptDraft, draft_id)
        if draft is None:
            return  # the variation was removed meanwhile
        project = stand_in_project(db, db.get(Script, draft.script_id), draft)
        text, owner = job.input["script_text"], {"script_draft_id": draft.id, "script_version": 0}
    else:
        project = db.get(Project, job.input["project_id"])
        text = db.scalar(
            select(ScriptVersion.text).where(
                ScriptVersion.project_id == project.id,
                ScriptVersion.version == job.input["script_version"],
            )
        )
        owner = {"project_id": project.id, "script_version": job.input["script_version"]}
    result = EnhanceResult.model_validate(job.output)
    brand_screens = {f"screen:{s.id}": s for s in project_screens(db, project)}
    problems = check.enhance(text, result, {k: s.default_for for k, s in brand_screens.items()})
    problems += [
        f"{s.id}: not a single direction line"
        for s in result.suggestions
        if "\n" in s.text.strip() or not s.text.strip() or HEADING.match(s.text.strip())
    ]
    bad = {p.split(":", 1)[0] for p in problems}
    starts = _line_starts(text)
    lines = text.splitlines()
    kept = 0
    for s in result.suggestions:
        if s.id in bad:
            continue
        n = s.anchor.line
        start = starts[n - 1] + lines[n - 1].index(s.anchor.quote)
        screen = brand_screens.get(s.screen_id or "")
        db.add(
            Suggestion(
                **owner,
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


# How each inserted direction line starts (Designer's spec, #69), so later steps read it as a
# shot direction, never as spoken or on-screen words.
TAGS = {
    "camera": "Camera",
    "action": "Movement",
    "reaction": "Reaction",
    "brand_screen": "Brand screen",
}


def tagged(kind: str, text: str) -> str:
    tag = f"[{TAGS[kind]}]" if kind in TAGS else ""
    return f"{tag} {text}" if tag and not text.startswith(tag) else text


def apply(text: str, marks: list[Suggestion]) -> str:
    """Apply accepted marks as new tagged lines ("[Camera] Push in.") before/after the quote's
    line. The script's own lines are never edited (endings included); any other placement is
    ignored."""
    lines = text.splitlines(keepends=True) or [""]
    before: dict[int, list[str]] = {}
    after: dict[int, list[str]] = {}
    for m in marks:
        if m.placement in ("before", "after"):
            side = before if m.placement == "before" else after
            side.setdefault(m.line - 1, []).append(tagged(m.kind, m.text))
    out = []
    for n, line in enumerate(lines):
        out += [f"{t}\n" for t in before.get(n, [])]
        out.append(line)
        added = after.get(n, [])
        if added and not line.endswith(("\n", "\r")):
            out.append("\n")  # last line without an ending: start a new one
        out += [f"{t}\n" for t in added]
    result = "".join(out)
    return result[:-1] if after.get(len(lines) - 1) and not text.endswith("\n") else result
