"""Breakdown: Claude turns the working script into scenes, shots and clips. The answer is
checked (`check.breakdown`) and saved with its problems so the editor sees what to fix."""

import re
from inspect import signature

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import prompts
from app.catalogue import CatalogueModel, catalogue
from app.enhance import escape, escape_block, project_context, project_screens
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.scripts import ScriptVersion
from app.prompts import check
from app.prompts.schemas import Breakdown


def video_model() -> CatalogueModel:
    """The video model clips are planned for (one per project, FIT row 23: the default)."""
    return next(m for m in catalogue().values() if m.kind == "video" and m.default)


def video_model_block(m: CatalogueModel) -> str:
    return (
        f"<video_model>{m.name}: {m.duration.min}–{m.duration.max} s per clip, up to "
        f"{m.max_reference_images} reference images (prefer "
        f"{m.recommended_reference_images or m.max_reference_images} or fewer), "
        f"{m.max_reference_audios} audios</video_model>"
    )


def _places(db: Session, project: Project) -> str:
    items = db.scalars(
        select(LibraryItem).where(
            LibraryItem.workspace_id == project.workspace_id,
            LibraryItem.kind == Kind.place,
            LibraryItem.archived.is_(False),
        )
    )
    lines = [
        f"place:{p.id} | {p.name} | {p.notes}"
        for p in items
        if any(b.id == project.brand_id for b in p.brands)
    ]
    return "\n".join(lines)


def recent_payoffs(
    db: Session, brand_id: int, exclude: int | None = None, n: int = 5, viewer: int | None = None
) -> list[tuple[str, list[str]]]:
    """Where the brand's latest videos' montages landed (Reed, 2026-10-27: a video's payoffs
    never repeat one of the same brand's): up to `n` other videos with a montage in their
    newest breakdown, newest first, as (video name, its last 3 montage actions in plain
    words). Library drafts don't count, nor a video whose script is still private to another
    person (`viewer`: whose prompt this is), so the model never sees someone's private work.
    Free."""
    from app.advice import names, plain
    from app.models.script_library import Script, ScriptDraft
    from app.storyboard import assets

    newest = (
        select(BreakdownVersion.project_id, func.max(BreakdownVersion.id).label("id"))
        .group_by(BreakdownVersion.project_id)
        .subquery()
    )
    rows = db.execute(
        select(Project, BreakdownVersion)
        .join(newest, newest.c.project_id == Project.id)
        .join(BreakdownVersion, BreakdownVersion.id == newest.c.id)
        .where(Project.brand_id == brand_id, Project.archived_at.is_(None))
        .order_by(BreakdownVersion.id.desc())
    )
    out = []
    for project, row in rows:
        if len(out) == n:
            break
        draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
        script = db.get(Script, draft.script_id) if draft else None
        private = script is not None and not script.published and script.created_by_id != viewer
        if project.id == exclude or private:
            continue
        shots = [s for scene in Breakdown.model_validate(row.data).scenes for s in scene.shots]
        if landed := check.payoff(shots):
            called = names(assets(db, project))
            out.append((project.name, plain([s.action for s in landed], called)))
    return out


def payoffs_block(payoffs: list[tuple[str, list[str]]]) -> str:
    """One line a video, about 300 characters at most; "" when there are none."""
    lines = [f'"{name}": {"; ".join(actions)}'[:300] for name, actions in payoffs]
    return f"<recent_payoffs>\n{escape(chr(10).join(lines))}\n</recent_payoffs>" if lines else ""


def job_input(db: Session, project: Project, version: ScriptVersion) -> dict:
    system, context = project_context(db, project, "breakdown")
    if project.script_draft_id:  # from the library: its unlocked slots, cast at Assets
        from app import script_preview
        from app.models.script_library import ScriptDraft

        draft = db.get(ScriptDraft, project.script_draft_id)
        context = script_preview.with_slots(db, draft.script_id, context, project)
    parts = [context, f"<places>\n{escape(_places(db, project))}\n</places>"]
    viewer = project.created_by_id
    if block := payoffs_block(recent_payoffs(db, project.brand_id, project.id, viewer=viewer)):
        parts.append(block)
    parts.append(video_model_block(video_model()))
    if project.reference_breakdown:
        ref = prompts.reference_block(project.reference_breakdown, project.reference_replace)
        parts.append(escape_block(ref))
    parts.append(f"<script>\n{escape(prompts.number_lines(version.text))}\n</script>")
    return {
        "step": "breakdown",
        "project_id": project.id,
        "script_version": version.version,
        "system": system,
        "prompt": "\n".join(parts),
        "max_tokens": 32000,
    }


def problems(db: Session, project: Project, script: str, bd: Breakdown) -> list[str]:
    shown = project_screens(db, project)
    screens = {f"screen:{s.id}": s.default_for for s in shown}
    m = video_model()
    brand = db.get(Brand, project.brand_id)
    # The Director's check takes the brand's end line (#107); older checks don't yet.
    params = signature(check.breakdown).parameters
    extra = {"end_line": brand.end_line} if "end_line" in params else {}
    if "brand" in params:
        extra["brand"] = brand.name
    if "kinds" in params:  # a moment takes any screen of the same kind (home)
        extra["kinds"] = check.kinds_of(shown)
    if "approved" in params:  # a video from the library is made from an approved version
        extra["approved"] = project.script_draft_id is not None
    if "recent" in params:  # montage variety: the brand's other videos' payoffs
        recent = recent_payoffs(db, project.brand_id, project.id, viewer=project.created_by_id)
        extra["recent"] = [a for _, actions in recent for a in actions]
    found = check.breakdown(script, bd, screens, m.duration.min, m.duration.max, **extra)
    from app.advice import names, plain
    from app.storyboard import assets

    found += unknown_ids(db, project, bd) + cast_problems(db, project, script, bd)
    return plain(found, {**unknown_names(db, project, bd), **names(assets(db, project))})


def cast_problems(db: Session, project: Project, script: str, bd: Breakdown) -> list[str]:
    """Shots that show the wrong person for a role their lines name. They stop stills until
    fixed ("Put the right cast in each shot", free) or kept anyway."""
    from app.advice import CAST
    from app.cast_roles import mismatches

    def who(ref: str) -> str:
        item = db.get(LibraryItem, int(ref[5:])) if ref.startswith("char:") else None
        return item.name if item else "no look yet"

    out = []
    for shot, missing, wrong in mismatches(db, project, script, bd):
        roles = " and ".join(role for role, _ in missing)
        should = " and ".join(who(c) for _, c in missing if c.startswith("char:"))
        shown = " and ".join(f"{who(c)} ({role})" for role, c in wrong)
        out.append(
            f"{CAST}shot {shot.id}: the script has {roles} here, but the shot shows {shown}"
            + (f" instead of {should}" if should else "")
        )
    return out


def cta_screen(db: Session, project: Project, bd: Breakdown) -> tuple[Breakdown, list[str]]:
    """The end line's shot (the call to action) shows the brand's real screen, on the phone the
    hero holds up (Reed, 2026-10-27; the Director, #556): with no screen, it gets the brand's
    balance screen (else its home screen) and the hero, the person in the most shots. Free,
    in code; said as advice. Doing it again changes nothing."""
    from app.advice import names
    from app.enhance import screen_name
    from app.storyboard import assets

    brand = db.get(Brand, project.brand_id)
    shots = [s for scene in bd.scenes for s in scene.shots]
    if check.cta_screen(shots, brand.end_line, brand.name) == []:
        return bd, []
    shot = [
        s for s in shots if s.line and check.ends_on(brand.end_line, s.line, brand.name) != "no"
    ][-1]
    screens = project_screens(db, project)
    home = [s for s in screens if "home" in s.tags or "home" in screen_name(s).lower()]
    screen = next((s for s in screens if s.balance), None) or next(iter(home), None)
    if screen is None:
        return bd, []
    people = [c for s in shots for c in s.character_ids]
    hero = max(dict.fromkeys(people), key=people.count) if people else None
    shot.screen_ids = [f"screen:{screen.id}"]
    if hero and hero not in shot.character_ids:
        shot.character_ids = [*shot.character_ids, hero]
    who = names(assets(db, project)).get(hero or "", "the hero")
    note = f"Advice: Shot {shot.id} now shows the {screen_name(screen)} screen on {who}'s phone."
    return bd, [note]


def unknown_ids(db: Session, project: Project, bd: Breakdown) -> list[str]:
    """Characters, places and screens a shot names that aren't this project's (cast, the
    brand's places, the brand's screens). Clips use these ids to attach pictures."""
    from app.storyboard import assets

    known = assets(db, project)
    return [
        f"shot {shot.id}: unknown {asset}"
        for scene in bd.scenes
        for shot in scene.shots
        for asset in [*shot.character_ids, shot.place_id, *shot.screen_ids]
        if asset and asset not in known
    ]


def _called(db: Session, ref: str, workspace_id: int) -> str:
    """A name the video doesn't have, as people call it ("Mia"), even a deleted look's or
    another video's, or what it is ("an unnamed character"); only ever a name from this
    workspace."""
    from app.advice import UNNAMED, called

    return called(db, {ref}, workspace_id).get(ref) or UNNAMED.get(ref.partition(":")[0], "a name")


def land(
    db: Session, project: Project, bd: Breakdown, also: set[str] = frozenset()
) -> tuple[Breakdown, list[str]]:
    """A breakdown as it is saved, however it came (the AI, a library plan, an edit, a fix, a
    cast swap), so "a character that isn't part of this video" never sticks (Kel's empty
    chair, Reed 2026-10-27): each speaker is the role; someone the video doesn't have (or
    `also` allows) becomes the role that picked them (a deleted look) or the script's role
    for the shot's speaker, made if it's missing (a per-video role, like FRIEND, whose look
    Assets makes); anyone else is taken out; and the end line's shot shows the brand's screen
    (cta_screen). Each change is said as advice."""
    from app.breakdown_fix import drop_unknown
    from app.cast_roles import picked, short
    from app.storyboard import assets, script_slots

    bd = as_roles(db, project, bd)
    known = {**assets(db, project), **dict.fromkeys(also)}
    slots = script_slots(db, project)
    looks = {f"char:{picked(project, s)}": s for s in slots if picked(project, s)}
    notes = []
    for shot in (s for scene in bd.scenes for s in scene.shots):
        for ref in [r for r in shot.character_ids if r not in known]:
            slot = looks.get(ref) or _role(db, project, slots, shot.speaker)
            if slot is None:
                continue
            new = f"slot:{slot.id}"
            shot.character_ids = list(
                dict.fromkeys(new if r == ref else r for r in shot.character_ids)
            )
            known[new] = ("", [])
            notes.append(f"Advice: Shot {shot.id} now shows {short(slot.role) or slot.role}, "
                         "a role in this video.")  # fmt: skip
    bd, removed = drop_unknown(bd, known, lambda ref: _called(db, ref, project.workspace_id))
    bd, shown = cta_screen(db, project, bd)  # the end line's shot shows the brand's screen
    return bd, notes + removed + shown


OFF_SCREEN = re.compile(r"\((?:V\.?\s?O|O\.?\s?[SC])\b", re.I)  # "NATE (V.O.):", "(O.S.)"


def show_roles(db: Session, project: Project, bd: Breakdown, text: str) -> dict[str, list[str]]:
    """Each of the video's roles is in the shots that show them (Reed, 2026-10-27, "Marriage
    Rejection": the groom was never in his own shots, so no sheet was attached and the video
    model invented him): the shots they speak in on screen (the script's label has no V.O. or
    O.S.), and the shots whose action names them. In place; {shot id: names added}. Free."""
    from app.cast_roles import labels, named, ref, short, video_slots

    slots = [s for s in video_slots(db, project) if short(s.role)]
    lines, added = text.splitlines(), {}
    for shot in (s for scene in bd.scenes for s in scene.shots):
        said = [check.SPEAKER.match(lines[n - 1]) for n in shot.script_lines
                if 0 < n <= len(lines)]  # fmt: skip
        off = any(m and OFF_SCREEN.search(m[0]) for m in said)
        for slot in slots:
            who = ref(db, project, slot)
            if {who, f"slot:{slot.id}"} & set(shot.character_ids):
                continue
            speaks = bool(shot.speaker) and labels(shot.speaker, slot.role) and not off
            if speaks or named(slot.role, shot.action):
                shot.character_ids = [*shot.character_ids, who]
                added.setdefault(shot.id, []).append(short(slot.role))
    return added


def complete_cast(db: Session, project: Project) -> list[str]:
    """Every speaker in the video's script is a role, and every role is in its shots
    (`show_roles`), so Assets makes and asks for their looks and frames and clips get their
    sheets. A screen shot that gains a person has "Use the real image" turned off (it was only
    offered as a shot with nobody in it). Free and idempotent: when Assets opens, and on
    deploy. One plain line per change."""
    from app.models.clips import ProjectClip
    from app.models.script_library import Script, ScriptDraft
    from app.routes.scripts import latest

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    script = db.get(Script, draft.script_id) if draft else None
    if script is None:
        return []
    out = [f"{script.title}: added {name} to the cast" for name in add_speakers(db, script)]
    row = db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )
    words = latest(db, project)
    if row is None or words is None:
        return out
    bd = Breakdown.model_validate(row.data)
    if not (added := show_roles(db, project, bd, words.text)):
        return out
    notes = [f"Advice: Shot {sid} now shows {' and '.join(names)}." for sid, names in added.items()]
    row.data = bd.model_dump()
    row.problems = problems(db, project, words.text, bd) + notes
    off = 0
    for clip in db.scalars(select(ProjectClip).where(ProjectClip.breakdown_id == row.id)):
        if gone := [k for k, on in (clip.real_images or {}).items() if on and k in added]:
            clip.real_images = {k: v for k, v in clip.real_images.items() if k not in gone}
            off += len(gone)
    out.append(f"{project.name}: " + " ".join(n.removeprefix("Advice: ") for n in notes))
    if off:
        shots = "1 shot" if off == 1 else f"{off} shots"
        out.append(f"{project.name}: turned off Use the real image on {shots} with a person")
    return out


def add_speakers(db: Session, script) -> list[str]:
    """The script's speakers the cast read missed (or that it never had: a script from
    before the cast read), added to its cast as roles. Their names."""
    from app import script_cast_read

    slots = script_cast_read._slots(db, script)
    new = script_cast_read.speaker_slots(db, script, slots)
    for position, slot in enumerate(new, len(slots) + 1):
        slot.position = position
    db.flush()
    return [s.role for s in new]


def _role(db: Session, project: Project, slots: list, speaker: str | None):
    """The script's role for a shot's speaker, added to the script when it has none yet (the
    cast read missed them); None without a speaker or a library script."""
    from app.cast_roles import short
    from app.models.script_library import ScriptCastSlot, ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if not speaker or draft is None:
        return None
    want = speaker.strip().lower()
    found = next((s for s in slots if want in (s.role.lower(), short(s.role).lower())), None)
    if found is None:
        found = ScriptCastSlot(script_id=draft.script_id, role=speaker.strip().title()[:120],
                               position=len(slots) + 1, kind="Helper")  # fmt: skip
        db.add(found)
        db.flush()
        slots.append(found)
    return found


def unknown_names(db: Session, project: Project, bd: Breakdown, known=None) -> dict[str, str]:
    """What people call each name a shot has that the video doesn't ({ref: "Nate"}), so Edit
    shot can say "Remove Nate from this shot" (spec one-click-fixes.md §2). Free."""
    from app.storyboard import assets

    known = assets(db, project) if known is None else known
    refs = [r for scene in bd.scenes for shot in scene.shots
            for r in [*shot.character_ids, shot.place_id, *shot.screen_ids]]  # fmt: skip
    return {r: _called(db, r, project.workspace_id) for r in dict.fromkeys(refs)
            if r and r not in known}  # fmt: skip


def record_length(project: Project, bd: Breakdown) -> None:
    """The newest breakdown sets the length when none was set (its clips added up)."""
    project.breakdown_seconds = sum(clip.seconds for clip in bd.clips) or None


def as_roles(db: Session, project: Project, bd: Breakdown) -> Breakdown:
    from app.cast_roles import as_roles as roles

    return roles(db, project, bd)


def save_breakdown(db: Session, job: Job) -> None:
    """Store Claude's breakdown (with its problems) as the project's newest breakdown, or on
    the library version it previews (workflow v2)."""
    if draft_id := job.input.get("script_draft_id"):
        from app import script_preview
        from app.models.script_library import ScriptDraft

        draft = db.get(ScriptDraft, draft_id)
        script_preview.save(  # it lands the plan (roles, names it doesn't have)
            db, draft, Breakdown.model_validate(job.output), job.created_by_id,
            job.input.get("script_text"),
        )  # fmt: skip
        return
    project = db.get(Project, job.input["project_id"])
    version = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.project_id == project.id,
            ScriptVersion.version == job.input["script_version"],
        )
    )
    bd, removed = land(db, project, Breakdown.model_validate(job.output))
    record_length(project, bd)
    db.add(
        BreakdownVersion(
            project_id=project.id,
            script_version=version.version,
            source="claude",
            job_id=job.id,
            data=bd.model_dump(),
            problems=problems(db, project, version.text, bd) + removed,
            created_by_id=job.created_by_id,
        )
    )
    from app import clip_prompts
    from app.models.accounts import User

    db.flush()  # stale clip prompts are rewritten, within budget (follow commits first)
    clip_prompts.follow(db, project, db.get(User, job.created_by_id))
