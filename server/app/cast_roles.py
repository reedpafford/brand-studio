"""Who plays whom in a video made from a library script: each character's cast slots (roles),
locked ones and those cast at the Assets step. Every model call that sees the cast is told,
so a shot never gets the wrong person (Reed, "Turned down in Paris": the rich older man
showed up in Nate's proposal). A deterministic check and fix use the same map."""

import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.projects import Project
from app.models.script_library import ScriptCastSlot, ScriptDraft


def cast_roles(db: Session, project: Project) -> dict[int, list[ScriptCastSlot]]:
    """character id -> the roles they play (in slot order); empty for older videos."""
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if draft is None:
        return {}
    slots = db.scalars(
        select(ScriptCastSlot)
        .where(ScriptCastSlot.script_id == draft.script_id)
        .order_by(ScriptCastSlot.position, ScriptCastSlot.id)
    )
    picked = project.slot_cast or {}
    out: dict[int, list[ScriptCastSlot]] = {}
    for slot in slots:
        if who := slot.library_item_id or picked.get(str(slot.id)):
            out.setdefault(who, []).append(slot)
    return out


def plays(slots: list[ScriptCastSlot]) -> str:
    """'plays Nate, the groom' for a cast line ('' with no role). Only the role's name: the
    look is used as is, so its own notes say how they look, never the role's description."""
    return "; ".join(f"plays {s.role}" for s in slots)


def short(role: str) -> str:
    """A role's name as a script labels it: "Nate, the teen groom" -> "Nate", "The bride" ->
    "bride"."""
    name = re.split(r"[,(]", role, maxsplit=1)[0].strip()
    return re.sub(r"^(the|a|an)\s+", "", name, flags=re.I)


def named(role: str, text: str) -> bool:
    """The role is named in these words ("Nate", "the rich older man"), ignoring case, a
    leading "the" and any description after a comma."""
    return any(
        w and re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text, re.I)
        for w in {short(role), re.sub(r"^(the|a|an)\s+", "", role.strip(), flags=re.I)}
    )


LABEL = re.compile(r"^\s*([A-Z][A-Z .'-]*?)(?: \([^)]*\))?:")  # "NATE:" or "NATE (V.O.):"


def on_screen(lines: list[str]) -> str:
    """What says who is in a shot: its speakers' labels and its action lines. A name said
    inside someone's dialogue ("where's the bride?") doesn't put them in the shot."""
    out = []
    for line in lines:
        label = LABEL.match(line)
        out.append(label.group(1) if label else line)
    return "\n".join(out)


def role_refs(db: Session, project: Project) -> dict[str, list[ScriptCastSlot]]:
    """As a breakdown names them: "char:N" -> the roles that look plays, and "slot:N" -> its
    role, for a role nobody plays yet."""
    out = {f"char:{c}": slots for c, slots in cast_roles(db, project).items()}
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if draft is not None:
        picked = project.slot_cast or {}
        for slot in db.scalars(
            select(ScriptCastSlot).where(ScriptCastSlot.script_id == draft.script_id)
        ):
            if not (slot.library_item_id or picked.get(str(slot.id))):
                out[f"slot:{slot.id}"] = [slot]
    return out


def mismatches(db: Session, project: Project, script: str, bd) -> list[tuple]:
    """Shots whose script lines name a role but show someone else's character in its place:
    (shot, [missing (role, ref)], [wrong (role, ref)]). Only a clear swap counts (a named
    role's look missing *and* another role's look there instead), so someone in a shot
    without lines is never flagged."""
    roles = role_refs(db, project)
    if not roles:
        return []
    lines = script.splitlines()
    found = []
    for scene in bd.scenes:
        for shot in scene.shots:
            said = [lines[n - 1] for n in shot.script_lines if 0 < n <= len(lines)]
            text = "\n".join([on_screen(said), shot.speaker or ""])
            here = list(dict.fromkeys(shot.character_ids))
            wanted = {r: s for r, slots in roles.items() for s in slots if named(s.role, text)}
            missing = [(s.role, r) for r, s in wanted.items() if r not in here]
            wrong = [(roles[r][0].role, r) for r in here if r in roles and r not in wanted]
            if missing and wrong:
                found.append((shot, missing, wrong))
    return found


def fix(db: Session, project: Project, script: str, bd):
    """The breakdown with each swapped shot's wrong characters replaced by the roles its
    script lines name (no model call). None if every shot is right."""
    found = mismatches(db, project, script, bd)
    if not found:
        return None
    fixed = bd.model_copy(deep=True)
    shots = {s.id: s for scene in fixed.scenes for s in scene.shots}
    for shot, missing, wrong in found:
        gone = {r for _, r in wrong}
        kept = [r for r in shots[shot.id].character_ids if r not in gone]
        shots[shot.id].character_ids = kept + [r for _, r in missing]
    return fixed


def changed_shots(old, new) -> list[dict]:
    """Each shot whose cast differs between two breakdowns: {shot_id, before, after}, so a
    screen can show what a fix changed and Undo can put it back."""
    before = {s.id: s.character_ids for scene in old.scenes for s in scene.shots}
    return [
        {"shot_id": s.id, "before": before[s.id], "after": s.character_ids}
        for scene in new.scenes
        for s in scene.shots
        if s.id in before and before[s.id] != s.character_ids
    ]


def _swaps(old, new) -> dict[str, dict[str, str] | None]:
    """Per shot: who replaced whom ({"char:9": "char:12"}), {} if its cast didn't change, or
    None when it isn't a one-for-one swap (then its frames need writing again)."""
    out = {}
    for change in changed_shots(old, new):
        gone = [r for r in change["before"] if r not in change["after"]]
        came = [r for r in change["after"] if r not in change["before"]]
        out[change["shot_id"]] = (
            dict(zip(gone, came, strict=True)) if len(gone) == len(came) else None
        )
    return out


def _look(db: Session, ref: str):
    from app.models.library import LibraryItem

    return (
        db.get(LibraryItem, int(ref[5:])) if ref.startswith("char:") and ref[5:].isdigit() else None
    )


def carry_frames(db: Session, project: Project, old_row, new_row, same_look=False) -> list:
    """Frames of the replaced breakdown move to the new one when only who plays a role
    changed: their references, the look's name and its description are swapped in the
    prompt (free, no model call). A still that shows the old cast is marked out of date and
    returned, for redrawing (not when it's the same picture under a new name, as a look saved
    to Cast & places is). Frames whose shots changed otherwise stay behind (stale)."""
    from app.models.storyboards import StoryboardFrame
    from app.prompts.schemas import Breakdown

    old, new = Breakdown.model_validate(old_row.data), Breakdown.model_validate(new_row.data)
    swaps = _swaps(old, new)
    shots = {s.id for scene in new.scenes for s in scene.shots}
    clips = {c.id: c.shot_ids for c in new.clips}
    outdated = []
    frames = db.scalars(select(StoryboardFrame).where(StoryboardFrame.breakdown_id == old_row.id))
    for frame in frames:
        mine = [frame.shot_id] if frame.shot_id in shots else clips.get(frame.clip_id, [])
        if not mine or any(swaps.get(s, {}) is None for s in mine):
            continue  # its shots changed beyond a recast: write the storyboard again
        swap = {k: v for s in mine for k, v in (swaps.get(s) or {}).items()}
        frame.breakdown_id = new_row.id
        if not swap:
            continue
        frame.reference_ids = [swap.get(r, r) for r in frame.reference_ids]
        for was, now in swap.items():
            a, b = _look(db, was), _look(db, now)
            if a and b:
                frame.prompt = re.sub(rf"(?<!\w){re.escape(a.name)}(?!\w)", b.name, frame.prompt)
                if a.notes and b.notes:
                    frame.prompt = frame.prompt.replace(a.notes, b.notes)
        if same_look:
            continue
        frame.approved = False
        if frame.file_id:
            frame.still_stale = True
            outdated.append(frame)
    return outdated


def redraw(db: Session, project: Project, user, frames: list) -> dict | None:
    """Redraw stills that show the old cast, as normal paid stills, but only if all of them
    fit: a library version's budget, or the editor's week on their own script. Otherwise
    none are drawn (they stay out of date) and the reason is kept for the screen."""
    from fastapi import HTTPException

    from app import storyboard
    from app.credits import credits_left, credits_used, estimate, own_script, price
    from app.routes.jobs import enqueue

    if not frames:
        return None
    try:
        inputs = [storyboard.render_input(db, project, f) for f in frames]
    except HTTPException as e:  # e.g. the new look's sheet isn't approved yet
        result = {"redraw_refused": {"count": len(frames), "credits": 0, "reason": e.detail}}
        project.cast_redraw = result
        db.commit()
        return result
    total = sum(
        (estimate(db, project.workspace_id, "image", Decimal(1), i) for i in inputs), Decimal(0)
    )
    n = len(frames)
    stills = "1 still shows" if n == 1 else f"{n} stills show"
    if own_script(db, project, user):
        left = credits_left(db, user)
        fits = left is None or total <= left
        why = "would go over this week's free credits. It resets on Monday."
    else:
        fits = credits_used(db, project) + total <= project.budget_credits
        why = "would go over this video's budget."
    if not fits:
        shown = price(total)  # as the button shows it
        said = "1 credit" if shown == 1 else f"{shown} credits"
        reason = (
            f"Frames rewritten for the new cast. {stills} the old cast: "
            f"redrawing {'it' if n == 1 else 'them'} ({said}) {why}"
        )
        result = {"redraw_refused": {"count": n, "credits": float(total), "reason": reason}}
        project.cast_redraw = result
        db.commit()
        return result
    done = 0
    for frame, data in zip(frames, inputs, strict=True):
        try:  # checked above; a refusal here (e.g. the per-video cap) never breaks the cast
            enqueue(db, user, "image", data, project=project, provider="replicate")
        except HTTPException as e:
            left = n - done
            result = {
                "redraw_refused": {"count": left, "credits": float(total), "reason": e.detail}
            }
            if done:
                result["redrawn_for_cast"] = {"count": done, "credits": float(total)}
            project.cast_redraw = result
            db.commit()
            return result
        frame.redrawn, frame.approved = True, False
        done += 1
    result = {"redrawn_for_cast": {"count": n, "credits": float(total)}}
    project.cast_redraw = result
    db.commit()
    return result


def as_roles(db: Session, project: Project, bd):
    """A shot's speaker is the role ("Omar"), never the look that plays it ("Carl"), so the
    breakdown reads like the script. Returns the breakdown, fixed in place."""
    looks = {}
    for char_id, slots in cast_roles(db, project).items():
        from app.models.library import LibraryItem

        item = db.get(LibraryItem, char_id)
        if item and len(slots) == 1 and item.name.strip().lower() != slots[0].role.strip().lower():
            looks[item.name.strip().lower()] = slots[0].role
    for scene in bd.scenes:
        for shot in scene.shots:
            if shot.speaker and (role := looks.get(shot.speaker.strip().lower())):
                shot.speaker = role
    return bd
