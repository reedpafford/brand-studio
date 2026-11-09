"""The director's make_looks for someone it names (video 294: four tries for Maya, three for
Bruno, drew nothing, as neither was a role the shots showed, and each said it was "making the
missing looks"). Who they are is read first, so one person is never two roles (rule 9): a role
by that name or one it contains ("Maya Chen" is Maya), or, said as a description ("the woman",
"Bruno's owner"), the one role their shots already show. Only someone new is made a role, there
and then, in the shots that show them, and drawn from the director's words with the plan's.
When the words point at a moment already made ("the woman who opens the bag at 10.3 s in clip
4"), that frame is their picture, as an upload is (free; only the sheet is paid). A try that
draws nobody says why in one line. Per person: the second asks the owner who plays them (a
cast card), and the run waits for that answer; one more try after it, never a loop."""

import copy
import re
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import asks, cast_roles
from app.models.accounts import User
from app.models.asks import Ask
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.files import StoredFile
from app.models.projects import Project

AT = re.compile(r"\bat (\d+(?:\.\d+)?) ?s(?:ec(?:onds?)?)?\b", re.I)  # "at 10.3 s"
CLIP = re.compile(r"\bclip (\d+)\b", re.I)
DESCRIBED = re.compile(r"(?i)^(the|a|an|his|her|their|our|my)\b|'s\b")  # not a person's own name
TRIES, CARDS = "look_tries", "look_cards"  # in a run, per person: tries that drew nobody; card
WAITING = "Waiting on the owner's answer to who plays "  # the run sleeps until it's answered


def prepare(db: Session, user: User, project: Project, look: dict, storage) -> str:
    """The person `look` names, ready for make_missing: their role (made only for someone new)
    in the shots that show them (`shot_ids`, else those whose words name them), with the frame
    its words point at as their picture when they have no look yet. "" when they can be drawn,
    else why, in one line the director can act on."""
    from app.breakdown import complete_cast
    from app.routes.project_assets import _cast, _missing, _undrawn, own_look, role_words

    name, shots = look["name"].strip(), list(look.get("shot_ids") or [])
    if gone := [s for s in shots if s not in _plan(db, project)]:
        return f"there's no shot {gone[0]} in this video's plan; give `shot_ids` from the plan."
    slot, why = _who(db, project, name, shots)
    if why:
        return why
    if slot is None and _asset(db, project, name):
        return ""  # a place, product or cast character: make_missing draws it as it is
    slot = slot or asks._new_role(db, project, name, bool(shots))
    if slot is None:
        return (f"{name} is named in neither the script nor the plan's shots; give "
                "`shot_ids`, the plan's shots that show them.")  # fmt: skip
    if shots:
        _in_shots(db, project, slot, shots)
    complete_cast(db, project)  # also in the shots whose words name them
    if all(s.id != slot.id for s in _missing(db, project)):
        return _why_not(db, project, slot, name)
    said = (look.get("description") or "").strip()
    if not _undrawn(db, project, slot) and (photo := frame(db, storage, project, said)):
        words = role_words(db, project, slot).rstrip(". ")
        item = own_look(db, project, slot, ". ".join(filter(None, [words, said])), photo)
        _cast(db, user, project, slot, item)  # make_missing draws its sheet, as an upload's
    return ""


def _plan(db: Session, project: Project) -> dict[str, dict]:
    from app.routes.project_assets import _newest

    bd = _newest(db, project)
    return {s["id"]: s for sc in (bd.data["scenes"] if bd else []) for s in sc["shots"]}


def _who(db: Session, project: Project, name: str, shots: list[str]) -> tuple:
    """(the role `name` means, or None for someone new; why it can't tell, or ""): that role
    by name; one whose name it contains ("Maya Chen"), never as an owner ("Bruno's owner" is
    not Bruno); said as a description, the one role its shots already show (`shot_ids`, else
    those whose words name it). Several there: it can't tell which, and says who they are."""
    roles = cast_roles.video_slots(db, project)
    if slot := asks._slot(db, project, name):
        return slot, ""
    owned = [r for r in roles if _says(r, name, owner=True)]
    if found := [r for r in roles if _says(r, name) and r not in owned]:
        return found[0], ""
    if not DESCRIBED.search(name):  # a person's own name: someone new
        return None, ""
    plan = _plan(db, project)
    at = shots or [i for i, s in plan.items() if cast_roles.named(name, s.get("action") or "")]
    seen = {c for i in at for c in plan[i]["character_ids"]}
    there = [r for r in roles if r not in owned
             and {f"slot:{r.id}", cast_roles.ref(db, project, r)} & seen]  # fmt: skip
    if len(there) == 1:
        return there[0], ""
    if not there:
        return None, ""
    them = " and ".join(cast_roles.short(r.role) or r.role for r in there)
    return None, (f"shot {', '.join(at)} already shows {them}: make_looks one of them by "
                  "name, or give `shot_ids` that show none of them for someone new.")  # fmt: skip


def _says(slot, name: str, owner: bool = False) -> bool:
    """`name` says this role's name as a word ("Maya Chen"); `owner`: as an owner ("Bruno's")."""
    short = cast_roles.short(slot.role)
    end = "'s" if owner else r"(?!\w)"
    return bool(short) and bool(re.search(rf"(?<!\w){re.escape(short)}{end}", name, re.I))


def _asset(db: Session, project: Project, name: str) -> bool:
    """`name` is one of the video's places, products, screens or cast looks, never a role."""
    from app.advice import names
    from app.storyboard import assets

    return any(cast_roles.same(called, name) for ref, called in names(assets(db, project)).items()
               if not ref.startswith("slot:"))  # fmt: skip


def _in_shots(db: Session, project: Project, slot, shots: list[str]) -> None:
    """The director's `shot_ids` show this role: in place, as complete_cast puts roles in."""
    from app.routes.project_assets import _newest

    bd, who = _newest(db, project), cast_roles.ref(db, project, slot)
    data = copy.deepcopy(bd.data)
    for shot in (s for sc in data["scenes"] for s in sc["shots"] if s["id"] in shots):
        shot["character_ids"] = list(dict.fromkeys([*shot["character_ids"], who]))
    bd.data = data
    db.flush()


def _why_not(db: Session, project: Project, slot, name: str) -> str:
    """Why a named role isn't one make_missing draws."""
    role = cast_roles.short(slot.role) or slot.role
    who = name if cast_roles.same(name, role) else f"{name} is {role}, who"
    if cast_roles.pick(db, project, slot) is not None:
        return f"{who} has a look in this video already (it's used); change_look {role} to redraw."
    refs = {cast_roles.ref(db, project, slot), f"slot:{slot.id}"}
    if not any(refs & set(s["character_ids"]) for s in _plan(db, project).values()):
        return f"{role} is in none of the plan's shots; give `shot_ids`, the shots that show them."
    return (f"{role}'s look is the person's call (they said Not now, or {role} may be another "
            "role); `ask` who plays them.")  # fmt: skip


def frame(db: Session, storage, project: Project, words: str) -> int | None:
    """The frame already made that `words` point at, stored as a picture: the newest cut's at
    that time ("at 10.3 s in clip 4", where clip 4 sits in the cut), else the named clip's
    picked take's at its own time ("at 1.2 s in clip 5"). None when they point at none."""
    from app import deep_watch, reel
    from app.delivery import _spans
    from app.host import _store

    if storage is None or not (at := AT.search(words)):
        return None
    t, n = float(at[1]), CLIP.search(words)
    cut = db.scalar(select(FinalVideo).where(FinalVideo.project_id == project.id)
                    .order_by(FinalVideo.id.desc()).limit(1))  # fmt: skip
    source = cut.file_id if cut else None
    if n:
        part = next((s for s in _spans(db, cut) if s["row"].clip_id == f"c{n[1]}"), None)
        if not (part and part["start"] <= t < part["start"] + part["seconds"]):
            row = db.scalar(select(ProjectClip).where(
                ProjectClip.project_id == project.id, ProjectClip.clip_id == f"c{n[1]}",
                ProjectClip.picked_take_id.is_not(None)).order_by(ProjectClip.id.desc())
                .limit(1))  # fmt: skip
            take = db.get(ClipTake, row.picked_take_id) if row else None
            source = take.file_id if take else None
    if source is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "in.mp4", Path(tmp) / "frame.png"
        src.write_bytes(storage.get(db.get(StoredFile, source).key))
        if not reel._grab(src, t, out, deep_watch.probe(src)["width"]):  # None past its end
            return None
        png = out.read_bytes()
    return _store(db, storage, project, png, f"frame at {t:g} s.png", "image/png").id


def _person(db: Session, project: Project, look: dict) -> tuple[str, str]:
    """(who a make_looks is for, however it words them: their role, else its shots, else the
    name; what the owner's card calls them)."""
    name, shots = (look.get("name") or "").strip(), sorted(look.get("shot_ids") or [])
    slot, _ = _who(db, project, name, shots)
    if slot is not None:
        return f"slot:{slot.id}", cast_roles.short(slot.role) or slot.role
    return (f"shots:{','.join(shots)}" if shots else f"name:{name.lower()}"), name


def failed(db: Session, project: Project, run: dict | None, look: dict, why: str) -> str:
    """A make_looks that drew nobody: why, in one line. The second for the same person in a run
    asks the owner who plays them (a cast card: their saved ones, Upload, Reply or Generate
    options); `held` then keeps the run from trying them again until it's answered."""
    said = f"Refused: {why}"
    if run is None:
        return said
    key, called = _person(db, project, look)
    run[TRIES] = {**run.get(TRIES, {}), key: run.get(TRIES, {}).get(key, 0) + 1}
    if run[TRIES][key] != 2:
        return said
    question = f"Who plays {called}? Pick or upload a picture of them."
    move = {"kind": "cast", "subject": called, "question": question, "why": why}
    asked = asks.asked(db, project, run.get("id"), move)
    card = db.scalar(select(Ask.id).where(Ask.project_id == project.id, Ask.kind == "cast",
                                          Ask.subject == called)
                     .order_by(Ask.id.desc()))  # fmt: skip
    run[CARDS] = {**run.get(CARDS, {}), key: card}
    return f"{said} {asked}"


def held(db: Session, project: Project, run: dict | None, decision: dict) -> str:
    """A make_looks for someone it tried twice for, whatever its words: "" for the one try
    after the owner answered, else what the run does instead. `WAITING…` while the card is
    open (the run sleeps until it's answered); else why it stops."""
    key, called = _person(db, project, decision.get("look") or {})
    tries = (run or {}).get(TRIES, {}).get(key, 0)
    if tries < 2:
        return ""
    card = (run.get(CARDS) or {}).get(key) or 0  # as it is now: answered by another request
    state = db.scalar(select(Ask.state).where(Ask.id == card))
    if state in asks.OPEN:
        return f"{WAITING}{called}."
    if state == "answered" and tries == 2:
        return ""
    return f"{called}'s look was tried {tries} times and the owner was asked; nothing more to try."


def again(db: Session, project: Project, run: dict | None, decision: dict, refused: str) -> str:
    """The same make_looks right after it drew nobody, which would stop the run: its retry,
    so the owner's card instead; "" past that (the run stops as before)."""
    look = decision.get("look") or {}
    if not (look.get("name") or "").strip() or run is None:
        return ""
    if run.get(TRIES, {}).get(_person(db, project, look)[0], 0) != 1:
        return ""
    return failed(db, project, run, look, refused.split(" Then: ")[-1])
