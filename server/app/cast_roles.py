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


def picked(project: Project, slot: ScriptCastSlot) -> int | None:
    """The look chosen for a role (locked on the script, or cast at Assets), live or not."""
    return slot.library_item_id or (project.slot_cast or {}).get(str(slot.id))


def pick(db: Session, project: Project, slot: ScriptCastSlot) -> int | None:
    """The role's look, if it can still be used: a deleted (archived) one, or another
    workspace's, counts as no look, so the role is uncast everywhere (Kel's empty chair: the
    girlfriend was deleted from Cast & places while still cast as "Her friend")."""
    from app.models.library import LibraryItem

    item = db.get(LibraryItem, picked(project, slot) or 0)
    live = item is not None and not item.archived and item.workspace_id == project.workspace_id
    return item.id if live else None


def own_look_in(db: Session, project: Project, slot: ScriptCastSlot, look: str) -> int | None:
    """The role's own look already made here in `look` (n12), if it's still there."""
    from app.models.library import LibraryItem

    item = db.get(LibraryItem, ((project.own_looks or {}).get(str(slot.id)) or {}).get(look) or 0)
    return item.id if item is not None and not item.archived else None


def all_slots(db: Session, project: Project) -> list[ScriptCastSlot]:
    """Every role of the library script this video is made from, in order (none for older
    videos)."""
    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if draft is None:
        return []
    query = select(ScriptCastSlot).where(ScriptCastSlot.script_id == draft.script_id)
    return list(db.scalars(query.order_by(ScriptCastSlot.position, ScriptCastSlot.id)))


def video_slots(db: Session, project: Project) -> list[ScriptCastSlot]:
    """The video's roles: the script's, less those merged into another on its Assets."""
    merged = project.slot_merged or {}
    return [s for s in all_slots(db, project) if str(s.id) not in merged]


def ref(db: Session, project: Project, slot: ScriptCastSlot) -> str:
    """How a breakdown names the role: its look (char:N) when it has one, else slot:N."""
    return f"char:{who}" if (who := pick(db, project, slot)) else f"slot:{slot.id}"


def merge_shots(db: Session, project: Project, bd, slot, into) -> list[str]:
    """`slot`'s shots go to `into` in place: who's in them and who speaks. The shot ids."""
    refs = {f"slot:{slot.id}", *([f"char:{slot.library_item_id}"] if slot.library_item_id else [])}
    refs |= {f"char:{c}" for c in [(project.slot_cast or {}).get(str(slot.id))] if c}
    target, moved = ref(db, project, into), []
    for shot in (s for scene in bd.scenes for s in scene.shots):
        spoken = bool(shot.speaker) and same(shot.speaker, slot.role)
        if spoken or refs & set(shot.character_ids):
            shot.character_ids = list(dict.fromkeys(target if r in refs else r
                                                    for r in shot.character_ids))  # fmt: skip
            shot.speaker = into.role if spoken else shot.speaker
            moved.append(shot.id)
    return moved


def same(a: str, b: str) -> bool:
    return (short(a) or a).strip().lower() == (short(b) or b).strip().lower()


ALIASES = {"gf": "girlfriend", "bf": "boyfriend"}  # short forms of one word ("Goth GF")


def labels(label: str, role: str) -> bool:
    """A script's speaker label is this role: the same name, or the label's last word is the
    last word of the role's name or the head noun of its description ("GROOM" is "Nate, the
    teen groom", "EX-BRIDE" is "The bride"). Never a word inside the description: "NATE" is
    not "Kimchi, Nate's rich friend". "GF" is "Girlfriend" (`ALIASES`)."""
    last = [ALIASES.get(w, w) for w in re.findall(r"[a-z]+", label.lower())[-1:]]
    name, _, about = role.partition(",")
    words = [re.findall(r"[a-z']+", part.lower()) for part in (short(name) or name, about)]
    heads = {ALIASES.get(w[-1], w[-1]) for w in words if w and not w[-1].endswith("'s")}
    return same(label, role) or bool(set(last) & heads)


def cast_roles(db: Session, project: Project) -> dict[int, list[ScriptCastSlot]]:
    """character id -> the roles they play (in slot order); empty for older videos."""
    out: dict[int, list[ScriptCastSlot]] = {}
    for slot in video_slots(db, project):
        if who := pick(db, project, slot):
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
    for slot in video_slots(db, project):
        if not pick(db, project, slot):
            out[f"slot:{slot.id}"] = [slot]
    return out


def mismatches(db: Session, project: Project, script: str, bd) -> list[tuple]:
    """Shots whose script lines name a role but show someone else's character in its place:
    (shot, [missing (role, ref)], [wrong (role, ref)]). Only a clear swap counts (a named
    role's look missing *and* another role's look there instead), so someone in a shot
    without lines is never flagged, nor a reaction shot whose action names who it shows
    (QA-Live, video 16: the boss's line over "Lexi takes the hit")."""
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
            seen = f"{shot.action} {shot.reaction or ''}"  # "Lexi takes the hit": her reaction
            insert = not shot.speaker and not any(named(s.role, seen) for v in roles.values()
                                                  for s in v)  # fmt: skip
            if insert:  # a close-up of a thing (the vacuum's canister): nobody to swap
                continue
            if missing and wrong and not any(named(role, seen) for role, _ in wrong):
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


def _recast(db: Session, text: str, swap: dict[str, str]) -> str:
    """The old look's name and description swapped for the new one's (free). The words in
    brackets after the person's name describe the old look ("Kimchi (cap, tee, chain)"), so
    they go: the new look's sheet sets the face and outfit (QA-Live 6, rule 10)."""
    for was, now in swap.items():
        a, b = _look(db, was), _look(db, now)
        slot = db.get(ScriptCastSlot, int(was[5:])) if was.startswith("slot:") else None
        if b is None:
            continue
        if a:  # a look's name, never a role's: a role's name is in the dialogue too
            text = re.sub(rf"(?<!\w){re.escape(a.name)}(?!\w)", b.name, text)
        for notes in (a.notes if a else "", slot.description if slot else ""):
            if notes and b.notes:
                text = text.replace(notes, b.notes)
        for name in {b.name, *([short(slot.role)] if slot else [])} - {""}:
            text = bare(text, name)
    return text


def bare(text: str, name: str) -> str:
    """Without the look words in brackets after a person's name ("Kimchi (cap, tee, chain)"):
    the sheet sets the face and outfit (rule 10). "Mom (sharp):" before a line stays."""
    return re.sub(rf"(?<!\w)({re.escape(name)})\s*\([^)]*\)(?!\s*:)", r"\1", text)


def carry_clips(db: Session, project: Project, old_row, new_row) -> int:
    """Clip prompts follow a recast like frames (free, no model call): a clip whose shots
    only changed who plays a role moves to the new breakdown with its references, the look's
    name and description swapped. Its takes stay (they show the old cast, so it isn't
    approved any more). Others stay behind as stale, for clip_prompts.follow. How many moved."""
    from app.models.clips import ProjectClip
    from app.prompts.schemas import Breakdown

    old, new = Breakdown.model_validate(old_row.data), Breakdown.model_validate(new_row.data)
    swaps, renamed = _swaps(old, new), _renamed(old, new)
    clips = {c.id: c.shot_ids for c in new.clips}
    moved = 0
    for clip in db.scalars(select(ProjectClip).where(ProjectClip.breakdown_id == old_row.id)):
        to = renamed.get(clip.clip_id)  # regrouped (a split): written again
        if to is None or any(swaps.get(s, {}) is None for s in clips[to]):
            continue
        swap = {k: v for s in clips[to] for k, v in (swaps.get(s) or {}).items()}
        clip.breakdown_id, clip.clip_id = new_row.id, to
        moved += 1
        if swap:
            clip.references = [{**r, "id": swap.get(r["id"], r["id"])} for r in clip.references]
            clip.prompt = _recast(db, clip.prompt, swap)
            clip.approved = clip.prompt_ok = False
    return moved


def _renamed(old, new) -> dict[str, str]:
    """Old clip id -> new, for each clip whose shots are the same (a split renumbers the
    clips after it: c2 becomes c3)."""
    now = {tuple(c.shot_ids): c.id for c in new.clips}
    return {c.id: now[k] for c in old.clips if (k := tuple(c.shot_ids)) in now}


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
    clips, renamed = {c.id: c.shot_ids for c in new.clips}, _renamed(old, new)
    of_shot = {s: c.id for c in new.clips for s in c.shot_ids}
    outdated = []
    frames = db.scalars(select(StoryboardFrame).where(StoryboardFrame.breakdown_id == old_row.id))
    for frame in frames:
        if frame.shot_id in shots:  # a shot's frame goes with its shot, to its clip now
            mine, to = [frame.shot_id], of_shot.get(frame.shot_id, frame.clip_id)
        else:  # a clip's: only to the same clip, under its new number
            to = renamed.get(frame.clip_id)
            mine = clips.get(to, [])
        if not mine or any(swaps.get(s, {}) is None for s in mine):
            continue  # its shots changed beyond a recast: write the storyboard again
        swap = {k: v for s in mine for k, v in (swaps.get(s) or {}).items()}
        frame.breakdown_id, frame.clip_id = new_row.id, to
        if not swap:
            continue
        frame.reference_ids = [swap.get(r, r) for r in frame.reference_ids]
        frame.prompt = _recast(db, frame.prompt, swap)
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
    from app.credits import estimate, fits, price
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
    if why := fits(db, project, user, total):
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
    breakdown reads like the script; a role merged on the video's Assets is the role kept.
    Returns the breakdown, fixed in place."""
    every = {str(s.id): s for s in all_slots(db, project)}
    for slot_id, into_id in (project.slot_merged or {}).items():
        if (slot := every.get(slot_id)) and (into := every.get(str(into_id))):
            merge_shots(db, project, bd, slot, into)
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
