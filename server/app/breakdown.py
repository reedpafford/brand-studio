"""Breakdown: Claude turns the working script into scenes, shots and clips. The answer is
checked (`check.breakdown`) and saved with its problems so the editor sees what to fix."""

import re
from decimal import Decimal
from inspect import signature

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from app import guides, looks, narration, prompts, song_breakdown
from app.catalogue import CatalogueModel, catalogue
from app.enhance import escape, escape_block, project_context, project_screens, screen_name
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.jobs import Job
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.scripts import ScriptVersion
from app.models.songs import SongTake
from app.prompts import check
from app.prompts.schemas import Breakdown, SongBreakdown

# A song's sung shots need lip-sync (Seedance 2.5), whatever the style. Every other kind follows
# its style (dialogue, narrated; a Movie style on Omni comes later).
LIP_SYNC_KINDS = ("song",)


def video_model(project: Project | None = None, look: str | None = None,
                kind: str | None = None) -> CatalogueModel:  # fmt: skip
    """The video model for a video, the one answer for its takes, quotes and "up to" prices:
    its own pick (VS1) always wins; else the catalogue default (Seedance 2.5) for a song
    (lip-sync); else its look's `video_model:` (Reed, 3 Nov: Seedance 2.5 for Pixar and House,
    Seedance 2.0 for the other animated styles; 6 Nov: Omni 1.2 for UGC, "Omni is more for the
    realistic stuff"). With no video yet (a script's preview, a sample), pass its `look` and
    script `kind`."""
    models = catalogue()
    if project is not None and project.video_model in models:
        return models[project.video_model]
    default = next(m for m in models.values() if m.kind == "video" and m.default)
    if kind is None and project is not None and (db := object_session(project)) is not None:
        from app.narration import video_kind

        kind = video_kind(db, project)
    if kind in LIP_SYNC_KINDS:
        return default
    broll = looks.drawn(project) if project is not None and project.broll_look else None  # n31
    look = broll or look or (project.look if project is not None else None) or "house"
    named = next((s["video_model"] for s in guides.styles() if s["id"] == look), "")
    return models.get(named, default)


def video_model_block(m: CatalogueModel) -> str:
    return (
        f"<video_model>{m.name}: {m.duration.min}–{m.duration.max} s per clip, up to "
        f"{m.max_reference_images} reference images (prefer "
        f"{m.recommended_reference_images or m.max_reference_images} or fewer), "
        f"{m.max_reference_audios} audios</video_model>"
    )


PAUSE = 0.2  # after a sentence, when the guides give no pause (a house reply: 0.05–0.2 s)


def timing(db: Session, project: Project) -> dict:
    """How long a line takes in this video (critique 276): the style's fastest words a second
    and its pause after a sentence (its guide's, else its format's; else 4.8 and PAUSE), and
    the length to land near: the brief's planned length (a library script's target too), else
    the newest length a note of this run asks for ("about 30 s"; never "at 12 s" or "cut 5 s")."""
    from app.director import run_notes
    from app.narration import video_script
    from app.script_library import WORDS_PER_SECOND, format_id

    script = video_script(db, project)
    look, fmt = project.look or "house", format_id(script) if script else "dialogue"
    try:
        fast = (guides.pace(look, fmt) or (0, WORDS_PER_SECOND))[1]
        pause = guides.pause(look, fmt) or PAUSE
    except ValueError:  # a style or format since taken out of the guides
        fast, pause = WORDS_PER_SECOND, PAUSE
    asked = [n for _, text in run_notes(db, project) if (n := check.asked_length(text))]
    return {"fast": fast, "pause": pause, "target": project.planned_seconds or next(
        reversed(asked), None)}  # fmt: skip


def timing_block(t: dict) -> str:
    """<timing> for the breakdown: the pace a line's shot is sized at, and the length."""
    pace = (f"Speaking pace in this style: up to {t['fast']:g} words a second, with about "
            f"{t['pause']:g} s after each sentence. A shot with a line holds at least its words "
            f"÷ {t['fast']:g}, plus {t['pause']:g} s for each sentence in it.")  # fmt: skip
    if target := t.get("target"):
        pace += (f"\nLength: about {target} s asked for, so the clips add up to "
                 f"{round(target * 0.9)}–{round(target * 1.1)} s.")  # fmt: skip
    return f"<timing>\n{pace}\n</timing>"


def _places(db: Session, project: Project) -> str:
    from app.video_variations import own_ids

    own = own_ids(db, project)  # a variation's are its source's
    items = db.scalars(
        select(LibraryItem).where(
            LibraryItem.workspace_id == project.workspace_id,
            LibraryItem.kind == Kind.place,
            LibraryItem.archived.is_(False),
        )
    )
    lines = [  # the brand's places, and those made for this video only (rule 12)
        f"place:{p.id} | {p.name} | {p.notes}"
        for p in items
        if p.owner_project_id in own or any(b.id == project.brand_id for b in p.brands)
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


TIMED_STEP = {"narration": "narrated"}  # a take's kind -> its breakdown step's prefix


def job_input(db: Session, project: Project, version: ScriptVersion) -> dict:
    """The breakdown call; a song video's is timed to its song (song_breakdown), a narrated
    one's to its narration's sentences (narrated_breakdown: every shot B-roll)."""
    take = song_breakdown.take_for(db, project)
    step = "breakdown" if not take else f"{TIMED_STEP.get(take.kind, 'song')}_breakdown"
    system, context = project_context(db, project, step)
    if project.script_draft_id:  # from the library: its unlocked slots, cast at Assets
        from app import script_preview
        from app.models.script_library import ScriptDraft

        draft = db.get(ScriptDraft, project.script_draft_id)
        context = script_preview.with_slots(db, draft.script_id, context, project)
    parts = [context, f"<places>\n{escape(_places(db, project))}\n</places>"]
    from app import plans

    planned = plans.block(db, project, version)  # P2: the shots follow the approved plan
    if planned:
        parts.append(planned[0])
    viewer = project.created_by_id
    if block := payoffs_block(recent_payoffs(db, project.brand_id, project.id, viewer=viewer)):
        parts.append(block)
    parts.append(video_model_block(video_model(project)))
    timed = None if take else timing(db, project)  # a song or narration is timed to its audio
    if timed:
        parts.append(timing_block(timed))
    if project.reference_breakdown:
        ref = prompts.reference_block(project.reference_breakdown, project.reference_replace)
        parts.append(escape_block(ref))
    parts.append(f"<script>\n{escape(prompts.number_lines(version.text))}\n</script>")
    from app.director import treatment_block

    if told := treatment_block(db, project):  # the story it serves (the director's treatment)
        parts.append(told.rstrip())
    if take:
        parts.append(escape_block(prompts.song_block(take.timing or {})))
    return {
        "step": step,
        **({"song_take_id": take.id} if take else {}),
        **(
            {
                "plan_version": planned[1],
                "plan": {k: plans.current(db, project)[k] for k in ("structure", "cast", "scenes")},
            }
            if planned
            else {}
        ),
        **({"timing": timed} if timed else {}),
        "project_id": project.id,
        "script_version": version.version,
        "system": system,
        "prompt": "\n".join(parts),
        "max_tokens": 32000,
    }


def problems(
    db: Session,
    project: Project,
    script: str,
    bd: Breakdown,
    song: dict | None = None,
    written: bool = False,
) -> list[str]:
    """The plan's problems. A song video's are checked with its song part (`song`, else the
    newest row's) against its take; `written`: the AI wrote it (its Sung advice speaks)."""
    shown = project_screens(db, project)
    screens = {f"screen:{s.id}": s.default_for for s in shown}
    m = video_model(project)
    brand = db.get(Brand, project.brand_id)
    params = signature(check.breakdown).parameters
    extra = {}
    if "brand" in params:
        extra["brand"] = brand.name
    if "kinds" in params:  # a moment takes any screen of the same kind (home)
        extra["kinds"] = check.kinds_of(shown)
    if "recent" in params:  # montage variety: the brand's other videos' payoffs
        recent = recent_payoffs(db, project.brand_id, project.id, viewer=project.created_by_id)
        extra["recent"] = [a for _, actions in recent for a in actions]
    if song is None:  # an edit: the song part it will be saved with (song_breakdown._carry)
        order = [s.id for scene in bd.scenes for s in scene.shots]
        song = song_breakdown.carried(db, project.id, order)
    take = db.get(SongTake, song["take_id"]) if song else None
    if take:
        timed, timing = song_breakdown.joined(bd, song), take.timing or {}
        hold = narration.FINAL_HOLD if take.kind == narration.KIND else 0.0  # its last shot's
        found = check.song_breakdown(script, timed, timing, screens, m.duration.min,
                                     m.duration.max, written=written, hold=hold,
                                     **extra)  # fmt: skip
    else:
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
    """The ending's shot that names the brand shows its real screen, on the phone the hero holds
    up (rule 18; Reed, 2026-10-27; the Director, #556): with no screen, it gets the brand's
    balance screen (else its home screen) and the hero, the person in the most shots. Free,
    in code; said as advice. Doing it again changes nothing."""
    from app.advice import names
    from app.enhance import screen_name
    from app.storyboard import assets

    brand = db.get(Brand, project.brand_id)
    shots = [s for scene in bd.scenes for s in scene.shots]
    if check.cta_screen(shots, brand.name) == []:
        return bd, []
    shot = [s for s in shots if s.line and check.says_brand(s.line, brand.name)][-1]
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


PERSON = "person:"  # a shot's "person:Grant": someone on screen the cast doesn't have yet
NO_ROLE = "Advice: {} is on screen with no role."  # an extra: the director's state says so


def extras(problems: list[str] | None) -> list[str]:
    """Who the shots show with no role (NO_ROLE notes), by name."""
    head, tail = NO_ROLE.split("{}")
    return [p.removeprefix(head).removesuffix(tail) for p in problems or [] if p.endswith(tail)]


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
    from app.cast_roles import picked, short, video_slots
    from app.storyboard import assets

    bd = as_roles(db, project, bd)
    known = {**assets(db, project), **dict.fromkeys(also)}
    slots = video_slots(db, project)
    looks = {f"char:{picked(project, s)}": s for s in slots if picked(project, s)}
    notes = []
    for shot in (s for scene in bd.scenes for s in scene.shots):
        for ref in [r for r in shot.character_ids if r not in known]:
            if ref.startswith(PERSON):  # someone who never speaks (226's Grant): their role
                name = ref.removeprefix(PERSON).strip()
                slot = _person(db, project, slots, name)
                if slot is None:  # an extra ("Crowd", "Woman"): the director decides, unpaid
                    shot.character_ids = [r for r in shot.character_ids if r != ref]
                    notes.append(NO_ROLE.format(name or "Someone"))
                    continue
            else:
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
    bd, bags = product_shots(db, project, bd)  # a shot that shows the product attaches it
    return bd, notes + removed + shown + bags


def products_of(db: Session, project: Project) -> list[dict]:
    """The brand's product screens for check.product_shown: this video's chosen variants
    first, then the others (a shot may name another flavour)."""
    from app.enhance import screen_name, screens_of

    chosen = {s.id for s in project_screens(db, project)}
    every = [s for s in screens_of(db, db.get(Brand, project.brand_id)) if "product" in s.tags]
    every.sort(key=lambda s: (s.id not in chosen, s.id))
    return [{"id": f"screen:{s.id}", "name": screen_name(s), "product": s.product,
             "variant": s.variant} for s in every]  # fmt: skip


def product_shots(db: Session, project: Project, bd: Breakdown) -> tuple[Breakdown, list[str]]:
    """Any shot whose action shows the brand's product lists the real product screen, so the
    still and the clip attach the real picture (Reed's #32 c9: an invented "Iron Paws" bag on
    a shelf). Free, in code; said as advice. Doing it again changes nothing."""
    products = products_of(db, project)
    brand = db.get(Brand, project.brand_id)
    ids = {p["id"]: p["name"] for p in products}
    shots = {s.id: s for scene in bd.scenes for s in scene.shots}
    clip_of = {sid: c for c in bd.clips for sid in c.shot_ids}

    def shown(clip) -> set[str]:  # a clip keeps to 3 screens (check.breakdown blocks a 4th)
        return {x for sid in (clip.shot_ids if clip else []) for x in shots[sid].screen_ids}

    notes = []
    for shot in shots.values():
        if any(s in ids for s in shot.screen_ids):
            continue
        found = check.product_shown(f"{shot.action} {shot.camera}", brand.name, products)
        if found and len(shown(clip_of.get(shot.id)) | {found}) <= 3:
            shot.screen_ids = [*shot.screen_ids, found]
            notes.append(f"Advice: Shot {shot.id} now shows the real {ids[found]}.")
    return bd, notes


OFF_SCREEN = re.compile(r"\((?:V\.?\s?O|O\.?\s?[SC])\b", re.I)  # "NATE (V.O.):", "(O.S.)"


KEPT_KEYS = ("plan_version",)  # a plan's own keys that a new version saved from it keeps


def carried_keys(row: BreakdownVersion | None) -> dict:
    """What a new version saved from `row` keeps of it besides its shots and clips: the plan
    version it was made from (plans.older: "Made for an older plan"). Its song part is carried
    on insert (song_breakdown._carry)."""
    data = row.data if row is not None else {}
    return {k: data[k] for k in KEPT_KEYS if k in data}


def carry_kept(kept: list[str], problems: list[str]) -> list[str]:
    """What the editor kept anyway still kept on a new version saved for them (a look made at
    Assets, a recast): the same line, or a cast line on a shot whose cast line was kept,
    whatever look names it now (QA-Live, video 16: Assets sent the editor back to Breakdown)."""
    from app.advice import CAST

    shot = re.compile(r"shot ([\w.]+):")
    cast = {m[1] for p in kept or [] if p.startswith(CAST) and (m := shot.search(p))}
    return [p for p in problems if p in (kept or [])
            or (p.startswith(CAST) and (m := shot.search(p)) and m[1] in cast)]  # fmt: skip


POSSESSIVE = re.compile(r"[\w-]+['’]s\b")  # "Granny's pats": hers, not her


def shows(role: str, shot, roles: list[str], off: bool = False, here: bool = True,
          listed: bool | None = None) -> bool:  # fmt: skip
    """This role is in the shot: it speaks there on screen (`off`: the script's label says
    V.O. or O.S.; not in a reaction shot of someone else among `roles`), or, in a shot with no
    cast list (`listed`, its own by default: an older plan), the action names it; named only
    as an owner ("Nate's ring") unless the plan shows the role only at other places (`here`
    false: video 276's "an echo of Granny's pats" in the truck lot, Granny only ever in the
    barn). A shot's cast list is who it shows (Reed, 9 Nov: trust the plan): nobody joins it
    from its words (video 315: Danny, only talked about in Marcus's car, was put in three
    shots, drawn and attached)."""
    from app.cast_roles import labels, named

    seen = f"{shot.action} {shot.reaction or ''}"
    reacting = [r for r in roles if r != role and named(r, seen)]
    speaks = bool(shot.speaker) and labels(shot.speaker, role) and not off
    speaks = speaks and not (reacting and not named(role, seen))  # a reaction shot
    if bool(shot.character_ids) if listed is None else listed:
        return speaks
    action = shot.action if here else POSSESSIVE.sub("", shot.action)
    return speaks or named(role, action)


def show_roles(db: Session, project: Project, bd: Breakdown, text: str) -> dict[str, list[str]]:
    """Each of the video's roles is in the shots that show them (Reed, 2026-10-27, "Marriage
    Rejection": the groom was never in his own shots, so no sheet was attached and the video
    model invented him): the shots they speak in on screen (the script's label has no V.O. or
    O.S.), and, in a shot the plan gave no cast list, the shots whose action names them
    (`shows`). In place; {shot id: names added}. Free."""
    from app.cast_roles import ref, short, video_slots

    slots = [s for s in video_slots(db, project) if short(s.role)]
    lines, added = text.splitlines(), {}
    shots = [s for scene in bd.scenes for s in scene.shots]
    for shot in shots:
        said = [check.SPEAKER.match(lines[n - 1]) for n in shot.script_lines
                if 0 < n <= len(lines)]  # fmt: skip
        off = any(m and OFF_SCREEN.search(m[0]) for m in said)
        roles, listed = [s.role for s in slots], bool(shot.character_ids)
        for slot in slots:
            who = ref(db, project, slot)
            if {who, f"slot:{slot.id}"} & set(shot.character_ids):
                continue
            seen = {s.place_id for s in shots if {who, f"slot:{slot.id}"} & set(s.character_ids)}
            if shows(slot.role, shot, roles, off, not seen or shot.place_id in seen, listed):
                shot.character_ids = [*shot.character_ids, who]
                added.setdefault(shot.id, []).append(short(slot.role))
    _hero_in_montage(db, project, bd, added)
    return added


def _hero_in_montage(db: Session, project: Project, bd: Breakdown, added: dict) -> None:
    """The main character is in every montage shot (`check.montage`, rule
    17; QA-Live 6: frame c3 had no hero, so none was drawn). In place."""
    from app.storyboard import _name, _same, assets, hero

    known = assets(db, project)
    if not (lead := hero(db, project, bd, known)):
        return
    shots = [s for scene in bd.scenes for s in scene.shots]
    for shot in (shots[k] for k in check.montage(shots)):
        if not any(_same(known, lead, c) for c in shot.character_ids):
            shot.character_ids = [*shot.character_ids, lead]
            added.setdefault(shot.id, []).append(_name(known, lead))


class _Changes(Exception):
    """complete_cast's first, unlocked look found something to change."""


def complete_cast(db: Session, project: Project) -> list[str]:
    """Every speaker in the video's script is a role, and every role is in its shots
    (`show_roles`), so Assets makes and asks for their looks and frames and clips get their
    sheets; a role that is a locked or cast one by another name is merged into it on this video
    (with Undo). A screen shot that gains a person has "Use the real image" turned off (it was
    only offered as a shot with nobody in it). Free and idempotent: when Assets, Storyboard or
    Clips opens. One plain line per change. It looks first without the video's lock, in a
    savepoint it takes back (video 245: every Cast, Clips and Storyboard read waited on the
    lock while a turn held it, 16 s and more); only a change is made under the lock, looked at
    again there."""
    try:
        with db.begin_nested():
            if not _complete_cast(db, project, locked=False):
                return []  # the usual read: nothing to change, no lock taken
            raise _Changes  # its writes are taken back with the savepoint
    except _Changes:
        pass
    return _complete_cast(db, project, locked=True)


def _complete_cast(db: Session, project: Project, locked: bool) -> list[str]:
    from app import merge_roles
    from app.cast_roles import merge_shots, short
    from app.credits import lock
    from app.models.clips import ProjectClip
    from app.models.script_library import CastMerge, Script, ScriptDraft
    from app.routes.scripts import latest

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    script = db.get(Script, draft.script_id) if draft else None
    if script is None:
        return []
    if locked:  # one at a time per video (QA-2: Assets' parallel requests each merged Girl
        lock(db, Project, project.id)  # again); the next one sees what this one did
        db.flush()  # then everything is read again as committed: what the unlocked look
        db.expire_all()  # loaded may be older than a write since (QA on #1427: a song part)
    db.refresh(project)
    out, kept = [], set()
    records = select(CastMerge).where(CastMerge.project_id == project.id).order_by(CastMerge.id)
    for record in db.scalars(records):  # duplicates from before the lock: one note, one Undo
        if (pair := tuple(record.data.get("auto") or ())) and pair in kept:
            db.delete(record)
            out.append(f"{project.name}: removed a repeated merge note")
        kept.add(pair)
    row = db.scalar(
        select(BreakdownVersion)
        .where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc())
        .limit(1)
    )
    out += [f"{script.title}: added {name} to the cast" for name in add_speakers(db, script)]
    words = latest(db, project)
    if row is None or words is None:
        return out
    bd = Breakdown.model_validate(row.data)
    merged = []  # a role that is a locked or cast one by another name, when that's certain
    for slot, into, _ in [p for p in merge_roles.video_pairs(db, project, bd) if p[2]]:
        old = {"slot_merged": project.slot_merged or {}, "slot_cast": project.slot_cast or {},
               "cast_ids": project.cast_ids or [], "breakdown": bd.model_dump(), "made": row.id,
               "auto": [slot.id, into.id]}  # fmt: skip
        old["moved"] = merge_shots(db, project, bd, slot, into)  # for Undo, whatever comes next
        db.add(CastMerge(workspace_id=project.workspace_id, script_id=script.id,
                         project_id=project.id, data=old))  # fmt: skip
        project.slot_merged = {**(project.slot_merged or {}), str(slot.id): into.id}
        merged.append(f"Advice: {short(slot.role) or slot.role} is {short(into.role) or into.role}"
                      ", one role in this video.")  # fmt: skip
    named = _named_extras(db, project, bd)  # before show_roles puts them in their shots
    out += [f"{script.title}: added {name} to the cast" for name in named]
    if not (added := show_roles(db, project, bd, words.text)) and not merged:
        return out
    counts: dict[str, int] = {}
    for name in (n for names in added.values() for n in names):
        counts[name] = counts.get(name, 0) + 1
    notes = merged + [f"Advice: {name} now appears in {'1 shot' if n == 1 else f'{n} shots'}."
                      for name, n in counts.items()]  # fmt: skip
    # its song part (each shot's time on the narration, and its talker shots) and plan version
    # stay: video 240 lost them here, so its talker shots went to Omni as B-roll and its clips
    # weren't cut to the narration (17 clips, 68 s for 24 s)
    row.data = {**row.data, **bd.model_dump()}
    row.problems = problems(db, project, words.text, bd, row.data.get("song")) + notes
    off = 0
    for clip in db.scalars(select(ProjectClip).where(ProjectClip.breakdown_id == row.id)):
        if gone := [k for k, on in (clip.real_images or {}).items()
                    if on and k.split("@", 1)[0] in added]:  # fmt: skip
            clip.real_images = {k: v for k, v in clip.real_images.items() if k not in gone}
            off += len(gone)
    out.append(f"{project.name}: " + " ".join(n.removeprefix("Advice: ") for n in notes))
    if off:
        shots = "1 shot" if off == 1 else f"{off} shots"
        out.append(f"{project.name}: turned off Use the real image on {shots} with a person")
    return out


def would_show(db: Session, project: Project, data: dict, shot_ids=None) -> list[list[str]]:
    """Who each shot (all, or `shot_ids`) shows once every role is in its shots, for the
    look gate before anything is written or drawn (QA-2 on #614: right after produce, before
    Assets was opened), plus a speaker with no role yet as `unroled:<name>`; a role that is or
    may be another (`video_pairs`) counts as them. Read only: it runs on a copy."""
    from app import merge_roles, script_cast_read
    from app.cast_roles import labels, merge_shots, video_slots
    from app.models.script_library import Script, ScriptDraft
    from app.routes.scripts import latest

    bd, words = Breakdown.model_validate(data), latest(db, project)
    if words is not None:
        show_roles(db, project, bd, words.text)
    for slot, into, _ in merge_roles.video_pairs(db, project, bd):
        merge_shots(db, project, bd, slot, into)  # never blocks on one that may be another
    shots = [s for scene in bd.scenes for s in scene.shots if shot_ids is None or s.id in shot_ids]
    out = [s.character_ids for s in shots]
    if draft := db.get(ScriptDraft, project.script_draft_id or 0):
        roles = [s.role for s in video_slots(db, project)]
        said = script_cast_read._speakers(db, db.get(Script, draft.script_id))
        out.append([f"unroled:{n}" for n in said if not any(labels(n, r) for r in roles)
                    and any(s.speaker and labels(s.speaker, n) for s in shots)])  # fmt: skip
    return out


def add_speakers(db: Session, script) -> list[str]:
    """The script's speakers the cast read missed (or that it never had: a script from
    before the cast read), added to its cast as roles. Their names. Safe to run twice at
    once (QA-2: Assets' parallel requests both added "Girl"): the second adds none."""
    from sqlalchemy.exc import IntegrityError

    from app import script_cast_read

    try:
        with db.begin_nested():
            slots = script_cast_read._slots(db, script)
            new = script_cast_read.speaker_slots(db, script, slots)
            for position, slot in enumerate(new, len(slots) + 1):
                slot.position = position
            db.flush()
    except IntegrityError:  # another request added them first
        return []
    return [s.role for s in new]


def _role(db: Session, project: Project, slots: list, speaker: str | None):
    """The script's role for a shot's speaker (`cast_roles.labels`), made with the script's
    other missed speakers when it has none yet; None without a speaker or a library script."""
    from app.cast_roles import labels, video_slots
    from app.models.script_library import Script, ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if not speaker or draft is None:
        return None
    if not any(labels(speaker, s.role) for s in slots) and add_speakers(
        db, db.get(Script, draft.script_id)
    ):
        slots[:] = video_slots(db, project)
    return next((s for s in slots if labels(speaker, s.role)), None)


def _person(db: Session, project: Project, slots: list, name: str):
    """The role of someone the breakdown shows who never speaks ("person:Grant", 226: Grant
    was never a role, so his shots borrowed another's look and no sheet was drawn): the role
    of that very name, else one added as the cast read adds one, only for a proper name the
    script writes capitalised mid-sentence or as a speaker's label (QA on #1405: "A crowd
    cheers", "a woman walks past" are extras, never paid roles; nor is "Woman" ever "Mara, a
    young woman"); or, with no label to go by (a song, a narration), someone the brief, a
    note or the treatment describes as a being (`_a_being`: video 294's Maya). None
    otherwise."""
    from app.cast_roles import all_slots, same
    from app.models.script_library import ScriptDraft

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if found := next((s for s in slots if name and same(name, s.role)), None):
        return found
    every = all_slots(db, project)
    roles = [s.role for s in every]
    if not (draft and name) or any(same(name, r) for r in roles) or not (
            _proper(name, draft.text) or _a_being(db, project, name, roles)):  # fmt: skip
        return None
    slots.append(slot := _add_role(db, project, draft, name))
    return slot


def _proper(name: str, text: str) -> bool:
    """A person's own name in the script: capitalised after a lowercase word ("hands Grant
    the ring"), a speaker's label ("GRANT:"), or someone a line speaks to ("MARCUS: Danny,
    you were right.")."""
    if not name[:1].isupper():
        return False
    word = re.escape(name.strip())
    mid = re.search(rf"\b[a-z][\w']*[,;]? +{word}\b", text)
    told = re.search(rf"^\s*[A-Z][A-Z .'-]*(?:\([^)]*\))?:\s*{word},", text, re.M)
    return bool(mid or told or re.search(rf"^\s*{word.upper()}\s*(?:\([^)]*\))?:", text, re.M))


CALENDAR = re.compile(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|"
                      r"February|March|April|May|June|July|August|September|October|November|"
                      r"December|Thanksgiving|Christmas|Easter|Halloween|Hanukkah|Diwali|Eid|"
                      r"Ramadan|Valentine)$")  # fmt: skip


def _a_being(db: Session, project: Project, name: str, others: list[str]) -> bool:
    """The brief, a note or the treatment says what they look like ("Bruno (a young
    pitbull…)", "his owner Maya, 30s"), in words about them alone (none of `others`)."""
    from app.routes.project_assets import LOOKS, _bracketed, _described, _story

    told = [project.goal or "", *(m.get("text") or "" for m in project.director_chat or []),
            *_story(db, project)]  # fmt: skip
    return bool(LOOKS.search(_bracketed(name, told)) or _described(name, others, told))


def _named_extras(db: Session, project: Project, bd: Breakdown) -> list[str]:
    """In a plan with no cast list on its shots (an older one), a person the script names who
    the shots' actions show in two or more clips is a role, so they get a look and the cast
    and places OK covers them (video 281: Danny, Marcus's brother-in-law, in four B-roll
    clips, was no role and drifted from clip to clip). A shot with a cast list is shown as
    listed, its words never add anyone (video 315: Danny, only talked about by Marcus, was
    made a role and drawn); someone it lists is a role as it lands (`land`). Named
    in one clip only, they're a one-off: drawn as part of the scene, never a paid look. Only
    someone the script treats as a person (a speaker's label, or someone a line speaks to:
    "MARCUS: Danny, you were right."), or, in a song or a narrated video where nobody has a
    label, someone the brief, a note or the treatment describes as a being ("Bruno (a young
    pitbull…)", "his owner Maya, 30s") whom the shots show as one ("Bruno gnaws", "Maya's
    hand": video 294's dog and his owner; never "Robinhood flashes" or "Tesla gleams": QA on
    #1473); never the brand, its
    products, screens or places
    (QA on #1466: "Iron Paws", "Robinhood", "Resilia"), a word before another capitalised one,
    a day or a holiday, or someone already in the cast. The names added."""
    from app.cast_roles import all_slots, same
    from app.models.library import Kind, LibraryItem
    from app.models.script_library import ScriptDraft
    from app.storyboard import cast_looks

    draft = db.get(ScriptDraft, project.script_draft_id) if project.script_draft_id else None
    if draft is None:
        return []
    clip_of = {s: c.id for c in bd.clips for s in c.shot_ids}
    unlisted = [s for scene in bd.scenes for s in scene.shots if not s.character_ids]
    seen: dict[str, set[str]] = {}
    for shot in unlisted:
        mid = r"(?<=[a-z,] )([A-Z][a-z]{2,})\b(?!\s+[A-Z])"  # mid-sentence, or at its start
        first = r"(?:^|(?<=[.!?] ))([A-Z][a-z]{2,})(?='s\b| [a-z]+s\b)"  # as "Maya's hand"
        for found in re.finditer(f"{mid}|{first}", shot.action):
            seen.setdefault(found[1] or found[2], set()).add(clip_of.get(shot.id, shot.id))
    items = db.scalars(select(LibraryItem.name).where(  # its places and products
        LibraryItem.workspace_id == project.workspace_id,
        LibraryItem.kind.in_([Kind.place, Kind.prop])))  # fmt: skip
    screens = [screen_name(x) for x in project_screens(db, project)]
    things = " ".join([db.get(Brand, project.brand_id).name, *items, *screens]).lower()
    known = [s.role for s in all_slots(db, project)] + [i.name for i in cast_looks(db, project)]
    actions = " ".join(s.action for s in unlisted)
    out = []
    for name, clips in seen.items():
        if (len(clips) < 2 or CALENDAR.match(name) or any(same(name, k) for k in known)
                or re.search(rf"\b{name.lower()}\b", things)):  # fmt: skip
            continue
        word = re.escape(name)
        being = re.search(rf"\b{word}(?:'s\b| [a-z]+s\b)", actions)  # "Maya's", "Bruno gnaws"
        others = [n for n in seen if n != name] + known
        if _addressed(name, draft.text) or (being and _a_being(db, project, name, others)):
            _add_role(db, project, draft, name)
            out.append(name)
    return out


def _add_role(db: Session, project: Project, draft, name: str):
    """A role added to the video's script, as the cast read adds one."""
    from app.cast_roles import all_slots
    from app.models.script_library import ScriptCastSlot

    slot = ScriptCastSlot(script_id=draft.script_id, role=name, kind="Helper",
                          appears_in=[draft.slot],
                          position=len(all_slots(db, project)) + 1)  # fmt: skip
    db.add(slot)
    db.flush()
    return slot


def _addressed(name: str, text: str) -> bool:
    """The script treats them as a person: a speaker's label ("DANNY:") or someone a line
    speaks to ("MARCUS: Danny, you were right.")."""
    word = re.escape(name)
    label = re.search(rf"^\s*{word.upper()}\s*(?:\([^)]*\))?:", text, re.M)
    return bool(label or re.search(rf"^\s*[A-Z][A-Z .'-]*(?:\([^)]*\))?:\s*{word},", text, re.M))


def unknown_names(db: Session, project: Project, bd: Breakdown, known=None) -> dict[str, str]:
    """What people call each name a shot has that the video doesn't ({ref: "Nate"}), so Edit
    shot can say "Remove Nate from this shot" (spec one-click-fixes.md §2). Free."""
    from app.storyboard import assets

    known = assets(db, project) if known is None else known
    refs = [r for scene in bd.scenes for shot in scene.shots
            for r in [*shot.character_ids, shot.place_id, *shot.screen_ids]]  # fmt: skip
    return {r: _called(db, r, project.workspace_id) for r in dict.fromkeys(refs)
            if r and r not in known}  # fmt: skip


def follow_model(db: Session, project: Project) -> None:
    """A video-model switch checks the newest breakdown's clip lengths again for the new
    model (QA #1013: a 25 s clip is fine on a 30 s model, not on a 15 s one)."""
    row = db.scalar(
        select(BreakdownVersion).where(BreakdownVersion.project_id == project.id)
        .order_by(BreakdownVersion.id.desc()).limit(1)
    )  # fmt: skip
    if row is None:
        return
    m = video_model(project)
    length = re.compile(r"(?i)^clip c\d+: \d+ s is outside \d+–\d+ s$")
    row.problems = [p for p in row.problems or [] if not length.match(p)] + check.clip_lengths(
        Breakdown.model_validate(row.data), m.duration.min, m.duration.max
    )


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
            job.input.get("script_text"), job.input.get("plan_version"),
        )  # fmt: skip
        return
    project = db.get(Project, job.input["project_id"])
    version = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.project_id == project.id,
            ScriptVersion.version == job.input["script_version"],
        )
    )
    if job.input.get("song_take_id"):  # the plan, and its song part beside it
        plan, song = song_breakdown.split(
            SongBreakdown.model_validate(job.output),
            job.input["song_take_id"],
            broll=job.input.get("step") == "narrated_breakdown",
            shortest=song_breakdown.least(db, project.id),
            longest=song_breakdown.most(db, project.id),
        )
    else:
        plan, song = Breakdown.model_validate(job.output), None
    bd, removed = land(db, project, plan)
    record_length(project, bd)
    db.add(
        BreakdownVersion(
            project_id=project.id,
            script_version=version.version,
            source="claude",
            job_id=job.id,
            data={
                **bd.model_dump(),
                **({"song": song} if song else {}),
                **({"plan_version": v} if (v := job.input.get("plan_version")) else {}),
            },
            problems=problems(db, project, version.text, bd, song, written=True)
            + removed
            + (job.output or {}).get("plan_advice", []),  # P2: what still doesn't follow the plan
            created_by_id=job.created_by_id,
        )
    )
    from app import clip_prompts, video_settings
    from app.models.accounts import User

    db.flush()  # stale clip prompts are rewritten, within budget (follow commits first)
    video_settings.follow_lip_sync(db, project, could=True)  # no lip-sync: Sung to B-roll (VS1)
    clip_prompts.follow(db, project, db.get(User, job.created_by_id))


def make_price(db: Session, project: Project) -> Decimal:
    """What Make the shots charges: the writing call and, once the video has clip prompts,
    their rewrite, which follows by itself (clip_prompts.follow, within the budget). Approve
    the plan makes the shots too, so it shows the same."""
    from app import clip_prompts
    from app.credits import estimate
    from app.models.clips import ProjectClip

    call = estimate(db, project.workspace_id, "write-claude", Decimal(1))
    have = list(db.scalars(select(ProjectClip.clip_id).where(ProjectClip.project_id == project.id)))
    return call + (clip_prompts.rewrite_price(db, project, have) if have else Decimal(0))
