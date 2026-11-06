"""The combined "Approve cast & places" checkpoint (Reed, 4 Nov, on S-gaps-07). Every
character and place a video's shots show, and a presenter's host, is approved together, once,
by the person making the video (its maker or the owner). It's a creative approval, never a
spending OK. Each item's approval is kept as the exact pictures and words its stills and takes
are made with (`sig`). An item that changes later (a new sheet, another look in the role, its
outfit or words, the video's style) needs the OK again. Only the stills and takes that show
it wait; everything else carries on. Library sheets keep their own approval (rule 8); this
sits on top of it. Every video waits for it the same way; only a one-clip freestyle, which has
no video and shows no character or place, has nothing to approve."""

import hashlib
import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.accounts import User
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame

KINDS = ("char:", "slot:", "place:")  # what the checkpoint covers: people and places
STEPS = ("frame", "clip_take", "host_still", "host_piece")  # the jobs that wait for it
WAIT = "{} {} for the cast and places OK. Approve them in Cast to go on."
SEEN_AGAIN = "{} changed since you opened Cast. Look at it again, then approve."
NOT_READY = "{} first, then approve the cast and places."
NOTHING = "There's nothing new to approve: the cast and places are approved."
PAUSED = "Not made: the cast or places changed since. Approve them in Cast, then make it again."


class Waiting(HTTPException):
    """A still or take refused because something it shows waits for the OK: the director
    skips it and does the rest (unrelated work carries on)."""


def not_yet(no: HTTPException) -> str:
    """A remake the director's watch wanted, held for the cast and places OK, as it says it."""
    return f"Not remade yet: {no.detail.split(' Approve')[0]} Approve them in Cast, then remake it."


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def parts(db: Session, project: Project, known: dict, ref: str) -> dict[str, str]:
    """An item as its stills and takes are made with, in three parts the card can name when
    one changes: its pictures (`look`), its line for the prompt (`words`: name, roles,
    outfit), and a character's voice. How a presenter appears isn't part of the character."""
    found = known.get(ref) or ("", [])
    item = _item(db, project, ref)
    voice = [item.voice_id, item.voice_stock_key, item.voice_file_id] if item else []

    def h(value) -> str:
        return hashlib.sha256(json.dumps(value).encode()).hexdigest()[:12]

    return {"look": h(list(found[-1])), "words": h(found[0]), "voice": h(voice)}


def sig(db: Session, project: Project, known: dict, ref: str) -> str:
    """The whole of `parts`, in one: what the person approved."""
    made = json.dumps(parts(db, project, known, ref), sort_keys=True)
    return hashlib.sha256(made.encode()).hexdigest()[:16]


def voice_of(db: Session, item: LibraryItem | None) -> dict | None:
    """A character's voice as the card shows it: {name, sample_url} (an API path, as #1314's:
    the web adds /api); None when it has none."""
    from app import voices
    from app.models.voices import Voice

    if item is None or item.kind != Kind.character:
        return None
    if voice := db.get(Voice, item.voice_id or 0):
        named = voices.sample_name(voice)
        url = (f"/voices/samples/{named}.mp3" if named else
               f"/files/{voice.sample_file_id}" if voice.sample_file_id else None)  # fmt: skip
        return {"name": voice.name, "sample_url": url}
    if key := item.voice_stock_key:
        try:
            name = voices.stock(key)["name"]
        except HTTPException:
            name = key
        named = voices.sample_name(None, key)
        return {"name": name, "sample_url": f"/voices/samples/{named}.mp3" if named else None}
    if item.voice_file_id:
        return {"name": "Its voice sample", "sample_url": f"/files/{item.voice_file_id}"}
    return None


def approved(project: Project) -> dict[str, str]:
    return {ref: v["sig"] for ref, v in ((project.cast_ok or {}).get("items") or {}).items()}


def shown(db: Session, project: Project, data: dict) -> dict[str, set[str]]:
    """Each shot's characters and place: who it shows as the look gate reads it (a role that
    may be another counts as them), and where it is."""
    from app.breakdown import would_show

    shots = [s for sc in data.get("scenes", []) for s in sc.get("shots", [])]
    if not shots:  # no plan yet: nothing to show
        return {}
    people = would_show(db, project, data)  # one list a shot, in order (then unroled speakers)
    return {s["id"]: {r for r in [*ids, s.get("place_id")] if r and r.startswith(KINDS)}
            for s, ids in zip(shots, people, strict=False)}  # fmt: skip


def refs(db: Session, project: Project, data: dict, shot_ids=None, also=(), known=None) -> list:
    """The characters and places in these shots (all when None), each once, and those a still
    or take attaches beyond them (`also`: its references that are part of the video)."""
    found = shown(db, project, data)
    mine = [rs for s, rs in found.items() if shot_ids is None or s in shot_ids]
    extra = [r for r in also if r.startswith(KINDS) and r in (known or {})]
    return list(dict.fromkeys([*(r for rs in mine for r in sorted(rs)), *extra]))


def _attached(db: Session, project: Project, bd) -> dict[str, set[str]]:
    """Each clip's characters and places its stills and prompt attach, on the newest shots."""
    out: dict[str, set[str]] = {}
    if bd is None:
        return out
    frames = select(StoryboardFrame).where(StoryboardFrame.breakdown_id == bd.id)
    for frame in db.scalars(frames):
        out.setdefault(frame.clip_id, set()).update(frame.reference_ids or [])
    for clip in db.scalars(select(ProjectClip).where(ProjectClip.breakdown_id == bd.id)):
        out.setdefault(clip.clip_id, set()).update(r["id"] for r in clip.references or [])
    return {c: {r for r in rs if r.startswith(KINDS)} for c, rs in out.items()}


def _host(db: Session, project: Project) -> list[str]:
    from app import host

    who = host.host_look(db, project) if host.on(db, project) else None
    return [f"char:{who.id}"] if who else []


def held(db: Session, project: Project, wanted: list[str], known: dict) -> list[str]:
    """Those of `wanted` that wait for the OK: never approved, or changed since."""
    ok = approved(project)
    return [r for r in wanted if ok.get(r) != sig(db, project, known, r)]


def require(db: Session, project: Project, wanted: list[str], known: dict) -> None:
    """Refuse a still or take (409) while an item it shows waits for the OK, naming them."""
    from app.advice import names

    if waiting := held(db, project, wanted, known):
        called = names(known)
        who = list(dict.fromkeys(called.get(r, "a character") for r in waiting))
        raise Waiting(409, WAIT.format(_and(who), "waits" if len(who) == 1 else "wait"))


def stamp(db: Session, project: Project, wanted: list[str], known: dict) -> dict[str, str]:
    """Kept in a still's or take's `made_with`: each item as it was made with."""
    return {r: sig(db, project, known, r) for r in wanted}


def job_paused(db: Session, job: Job) -> bool:
    """A queued still or take (one held for the owner, say) whose cast or places changed or
    were approved again since it was asked for: it must not run on an old look."""
    made = (job.input.get("made_with") or {}).get("cast")
    if job.input.get("step") not in STEPS or not made:
        return False
    project = db.get(Project, job.project_id, populate_existing=True)  # as approved now
    if project is None:
        return False
    from app.storyboard import assets

    known, ok = assets(db, project), approved(project)
    return any(ok.get(r) != s or sig(db, project, known, r) != s for r, s in made.items())


# --- The Cast view's set ------------------------------------------------------------------------


def _item(db: Session, project: Project, ref: str) -> LibraryItem | None:
    from app import cast_roles
    from app.models.script_library import ScriptCastSlot

    kind, _, n = ref.partition(":")
    if kind == "slot":
        slot = db.get(ScriptCastSlot, int(n))
        n = cast_roles.pick(db, project, slot) if slot else None
    item = db.get(LibraryItem, int(n or 0))
    return item if item is not None and not item.archived else None


def source(db: Session, project: Project, item: LibraryItem | None) -> str | None:
    """Where an item came from, as its card says: the brand's library, an upload, made for
    this video (a library character drawn in this video's style too), or made for its
    script."""
    from app.sheets import look_copy

    if item is None:
        return None
    if item.owner_project_id:
        return "uploaded" if item.source_photo_file_id else "video"
    if item.owner_script_id:
        return "script"
    return "video" if look_copy(db, project, item) else "library"


def _readiness(db: Session, project: Project, item: LibraryItem | None, files) -> str:
    """drawing or waiting_for_owner while its sheet (or its check) is being made, needs_look
    when it has no picture yet, else ready."""
    from app.routes.library import _waiting_sheets
    from app.sheets import look_copy

    jobs = _waiting_sheets(look_copy(db, project, item) or item) if item else []
    if any(j.status == JobStatus.needs_owner_approval for j in jobs):
        return "waiting_for_owner"
    if jobs:
        return "drawing"
    return "ready" if files else "needs_look"


WHY = {"needs_look": "{} needs a look", "drawing": "{} is still being drawn",
       "waiting_for_owner": "{}'s look waits for the owner's OK"}  # fmt: skip


def current(db: Session, project: Project) -> list[dict]:
    """Every character and place the newest shots show (and a presenter's host), each with
    where it came from, its picture, whether it's ready and whether it's approved as it is."""
    from app.advice import names
    from app.clip_prompts import newest
    from app.storyboard import assets

    bd = newest(db, project)
    data = bd.data if bd else {}
    known, ok = assets(db, project), approved(project)
    called, by_shot = names(known), shown(db, project, data)
    clips = {s: c["id"] for c in data.get("clips", []) for s in c["shot_ids"]}
    joined = _attached(db, project, bd)
    every = [r for rs in by_shot.values() for r in sorted(rs)]
    every += [r for rs in joined.values() for r in sorted(rs) if r in known]
    out = []
    for ref in dict.fromkeys([*every, *_host(db, project)]):
        item, files = _item(db, project, ref), (known.get(ref) or ("", []))[-1]
        now, bits = sig(db, project, known, ref), parts(db, project, known, ref)
        was = ((project.cast_ok or {}).get("items") or {}).get(ref) or {}
        word = "place" if ref.startswith("place:") else "character"
        out.append({
            "ref": ref, "kind": word,
            "name": called.get(ref) or (item.name if item else f"A {word}"),
            "library_item_id": item.id if item else None,
            "version": item.version if item else None,
            "source": source(db, project, item),
            "preview_file_id": files[0] if files else None,
            "readiness": _readiness(db, project, item, files),
            "approval": "approved" if ok.get(ref) == now else ("changed" if ref in ok else "new"),
            "sig": now,
            # what changed since the OK: "look", "words" (name, role, outfit), "voice"
            "changes": [k for k, v in bits.items() if ok.get(ref) not in (None, now)
                        and (was.get("parts") or {}).get(k) != v],
            "voice": voice_of(db, item),
            "was_voice": was.get("voice") if ok.get(ref) not in (None, now)
            and (was.get("parts") or {}).get("voice") != bits["voice"] else None,
            **history(db, project, item),
            "clip_ids": sorted({*(clips[s] for s, rs in by_shot.items()
                                  if ref in rs and s in clips),
                                *(c for c, rs in joined.items() if ref in rs)}, key=_clip_order),
        })  # fmt: skip
    return out


def _made(db: Session, project: Project) -> tuple[list, list]:
    """The newest shots' drawn stills, and each clip with its picked take."""
    from app.clip_prompts import newest

    bd = newest(db, project)
    frames = db.scalars(select(StoryboardFrame).where(
        StoryboardFrame.project_id == project.id, StoryboardFrame.file_id.is_not(None),
        StoryboardFrame.breakdown_id == (bd.id if bd else 0))).all()  # fmt: skip
    rows = db.scalars(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                                ProjectClip.picked_take_id.is_not(None))
                      .order_by(ProjectClip.id)).all()  # fmt: skip
    return list(frames), [(r, db.get(ClipTake, r.picked_take_id)) for r in rows]


def _old(made: dict | None, now: dict[str, str]) -> bool:
    """Made with an earlier version of an item, and not kept as it is since."""
    made = made or {}
    kept = (made.get("kept") or {}).get("cast") or {}
    return any(now.get(r) != kept.get(r, s) for r, s in (made.get("cast") or {}).items())


def _update(db: Session, project: Project, items: list[dict]) -> dict:
    """The stills and takes already made with an earlier version of an item (`made_with`'s
    cast): kept as they are, never made again by themselves; what remaking them costs, up
    to (rule 36), so the person sees the price first; and those the person said to keep."""
    from app.clip_takes import take_credits
    from app.credits import price
    from app.storyboard import image_model, still_credits

    now = {i["ref"]: i["sig"] for i in items}
    frames, clips = _made(db, project)
    stills = [f.shot_id for f in frames if _old(f.made_with, now)]
    takes = [r for r, take in clips if take is not None and _old(take.made_with, now)]
    remakes = sum((take_credits(db, project, r) for r in takes), Decimal(0))
    total = still_credits(db, project.workspace_id, image_model(project)) * len(stills) + remakes
    marks = [("still", f.shot_id, f.made_with) for f in frames]
    marks += [("clip", r.clip_id, take.made_with) for r, take in clips if take is not None]
    kept = []
    for kind, ref, made in marks:
        mark = (made or {}).get("kept")
        if mark and not _old(made, now):
            by = db.get(User, mark.get("by") or 0)
            kept.append({"kind": kind, "id": ref, "by": by.name if by else "", "at": mark["at"]})
    return {"stills": stills, "clips": [r.clip_id for r in takes],
            "credits": price(total) if total else 0,
            "clips_credits": price(remakes) if remakes else 0, "kept_items": kept}  # fmt: skip


def keep(db: Session, user: User, project: Project, stills: list[str] | None,
         clips: list[str] | None) -> None:  # fmt: skip
    """Keep them: stills and takes made with an earlier look stay as they are and stop
    counting as needing an update (who and when are kept). Neither given: every one listed;
    one given: only those (the other kind is left as it is)."""
    if stills is not None or clips is not None:
        stills, clips = stills or [], clips or []
    now = {i["ref"]: i["sig"] for i in current(db, project)}
    frames, rows = _made(db, project)

    def kept(made: dict) -> dict:
        cast = {r: now.get(r) for r in made.get("cast") or {}}  # as they are now: one gone too
        return {**made, "kept": {"by": user.id, "at": utcnow().isoformat(), "cast": cast}}

    for frame in frames:
        if _old(frame.made_with, now) and (stills is None or frame.shot_id in stills):
            frame.made_with = kept(frame.made_with)
    for row, take in rows:
        if take and _old(take.made_with, now) and (clips is None or row.clip_id in clips):
            take.made_with = kept(take.made_with)
    db.commit()


def _who(db: Session, job: Job) -> str:
    from app.routes.jobs import BY_DIRECTOR

    if job.input.get(BY_DIRECTOR) or job.input.get("fit_redo"):
        return "director"  # its own move, or its look check's one redo
    user = db.get(User, job.created_by_id or 0)
    return user.name if user else ""


def history(db: Session, project: Project, item: LibraryItem | None) -> dict:
    """A look made for this video: who made it and when ("director" or the person; for an
    upload, who gave the photo), and its last revision: when, by whom, why (the change
    asked for) and the picture before it."""
    from app.models.files import StoredFile

    out = dict.fromkeys(("made_by", "made_at", "revised_by", "revised_at", "revised_why",
                         "was_preview_file_id"))  # fmt: skip
    if item is None or item.owner_project_id != project.id:
        return out
    jobs = [j for j in db.scalars(select(Job).where(
        Job.project_id == project.id, Job.status == JobStatus.succeeded,
        Job.input["library_item_id"].as_integer() == item.id).order_by(Job.id))
        if j.input.get("step") == "sheet" and (j.output or {}).get("file_ids")]  # fmt: skip
    photo = db.get(StoredFile, item.source_photo_file_id or 0)
    if jobs:
        out.update(made_by=_who(db, jobs[0]), made_at=jobs[0].created_at.isoformat())
    elif photo is not None:
        by = db.get(User, photo.uploaded_by_id or 0)
        out.update(made_by=by.name if by else "", made_at=photo.created_at.isoformat())
    was = db.get(LibraryItem, item.copied_from_id or 0)  # this look replaced that one here
    if was is not None and len(jobs) < 2:
        out.update(revised_by=out["made_by"], revised_at=out["made_at"] or
                   item.created_at.isoformat(), revised_why="New photo" if photo else "",
                   was_preview_file_id=was.sheet_file_id)  # fmt: skip
    if len(jobs) > 1:
        last = jobs[-1]
        out.update(revised_by=_who(db, last), revised_at=last.created_at.isoformat(),
                   revised_why=last.input.get("change") or "",
                   was_preview_file_id=jobs[-2].output["file_ids"][0])  # fmt: skip
    return out


def previews(db: Session, user: User, project: Project) -> dict:
    """What the looks made for this video have cost so far (their sheets, checks and redos),
    against its budget: credits for everyone, dollars for the owner only (rule 4)."""
    from app.credits import COUNTED, USD_PER_CREDIT

    own = set(db.scalars(select(LibraryItem.id).where(LibraryItem.owner_project_id == project.id)))
    jobs = db.scalars(select(Job).where(Job.project_id == project.id, Job.status.in_(COUNTED)))
    used = sum((j.credits for j in jobs if j.input.get("library_item_id") in own), Decimal(0))
    budget = Decimal(project.budget_credits)

    def usd(credits: Decimal, up) -> float | None:
        return float(up(credits * USD_PER_CREDIT * 100) / 100) if user.is_owner else None

    import math

    return {"credits": float(round(used, 3)), "usd": usd(used, math.ceil),
            "budget_credits": float(budget), "budget_usd": usd(budget, round)}  # fmt: skip


def state(db: Session, project: Project, user: User | None = None) -> dict:
    """The Cast view's checkpoint: none (nothing shown needs a look), not_ready (something
    has no look yet or is still being drawn), ready (all drawn; something new or changed
    waits for the OK) or approved; who approved it and when; what waits for it; and what was
    made with an earlier version."""
    items = current(db, project)
    waiting = [i for i in items if i["approval"] != "approved"]
    unready = [i for i in items if i["readiness"] != "ready"]
    said = "none" if not items else (
        "approved" if not waiting else "not_ready" if unready else "ready")  # fmt: skip
    rec = project.cast_ok or {}
    by = db.get(User, rec.get("by") or 0)
    return {
        "state": said,
        "approved_by": by.name if by else None,
        "approved_at": rec.get("at"),
        "asked": said in ("ready", "not_ready") and _asked(rec, items),
        "items": items,
        "waiting": [i["name"] for i in waiting] if said != "none" else [],
        "not_ready": [{"ref": i["ref"], "name": i["name"],
                       "why": WHY[i["readiness"]].format(i["name"])} for i in unready],
        "paused_clips": sorted({c for i in waiting for c in i["clip_ids"]}, key=_clip_order)
        if said not in ("none", "approved") else [],
        "update": _update(db, project, items),
        "previews": previews(db, user, project) if user else None,
    }  # fmt: skip


def _asked(rec: dict, items: list[dict]) -> bool:
    """The director asked for the OK on this very set: a revision since means asking again."""
    asked = (rec.get("asked") or {}).get("sigs")
    return asked == {i["ref"]: i["sig"] for i in items}


def _clip_order(clip_id: str) -> tuple:
    digits = clip_id.lstrip("c")
    return (0, int(digits)) if digits.isdigit() else (1, clip_id)


def approve(db: Session, user: User, project: Project, seen: dict[str, str]) -> None:
    """Approve cast & places: the whole set as the person saw it (`seen`: each item's sig).
    Refused while anything has no look or is still being drawn, when something changed since
    they looked, or when there's nothing new. Unchanged items stay approved as they were."""
    from app import director
    from app.credits import lock

    lock(db, Project, project.id)
    db.refresh(project)
    items = current(db, project)
    if all(i["approval"] == "approved" for i in items):
        raise HTTPException(409, NOTHING)
    if unready := [i for i in items if i["readiness"] != "ready"]:
        why = _and([WHY[i["readiness"]].format(i["name"]) for i in unready])
        raise HTTPException(409, NOT_READY.format(why[:1].upper() + why[1:]))
    if moved := [i["name"] for i in items if seen.get(i["ref"]) != i["sig"]]:
        raise HTTPException(409, SEEN_AGAIN.format(_and(list(dict.fromkeys(moved)))))
    kept = (project.cast_ok or {}).get("items") or {}
    known = assets_of(db, project)
    now = {i["ref"]: {"sig": i["sig"], "item": i["library_item_id"], "version": i["version"],
                      "file": i["preview_file_id"],
                      "parts": parts(db, project, known, i["ref"]),
                      "voice": i["voice"]} for i in items}  # fmt: skip
    project.cast_ok = {"items": {**kept, **now}, "by": user.id, "at": utcnow().isoformat()}
    db.commit()
    director.wake(db, project)  # a run waiting on this point goes on


def require_voice(db: Session, project: Project, voice: str | None = None) -> None:
    """A narration read in the host's voice (`voice`, as the narration takes it): refused (409)
    while that voice changed since the cast and places OK, until it's approved again. Another
    voice, or one never approved, isn't held: the cast is set out after the narration."""
    from app import host
    from app.advice import names

    who = host.host_look(db, project) if host.on(db, project) else None
    own = (f"voice:{who.voice_id}" if who.voice_id else who.voice_stock_key) if who else None
    if voice is not None and voice != own:
        return
    was = ((project.cast_ok or {}).get("items") or {}).get(f"char:{who.id}") if who else None
    if not was or not was.get("parts"):
        return
    known = assets_of(db, project)
    if was["parts"].get("voice") != parts(db, project, known, f"char:{who.id}")["voice"]:
        name = names(known).get(f"char:{who.id}") or who.name
        raise Waiting(409, WAIT.format(f"{name}'s new voice", "waits"))


def assets_of(db: Session, project: Project) -> dict:
    from app.storyboard import assets

    return assets(db, project)


def pending(db: Session, project: Project) -> bool:
    """Something the video shows waits for the OK (the director waits on this point)."""
    return any(i["approval"] != "approved" for i in current(db, project))


def ask(db: Session, project: Project, run_id: str | None) -> str:
    """The director's `ask_cast_ok`: the card asking the person to look at the whole set and
    approve it, once every item is drawn. In plain words for its log."""
    said = state(db, project)
    if said["state"] in ("none", "approved"):
        return "Refused: the cast and places are approved already."
    if said["state"] == "not_ready":
        return f"Refused: {_and([n['why'] for n in said['not_ready']])} first."
    if said["asked"]:
        return "Refused: the cast and places OK is already asked for."
    sigs = {i["ref"]: i["sig"] for i in said["items"]}
    asked = {"at": utcnow().isoformat(), "run": run_id, "sigs": sigs}
    project.cast_ok = {**(project.cast_ok or {}), "asked": asked}
    db.commit()
    return f"Asked for the cast and places OK: {_and(said['waiting'])}."
