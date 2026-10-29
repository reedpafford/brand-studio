"""Storyboard: Claude writes one image prompt per clip (or per shot) of the newest breakdown
and picks its reference pictures. Frames are saved with their problems; the editor can edit
them before any still is rendered."""

import json
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.advice import names, plain
from app.cast_roles import bare, cast_roles, pick, plays, short, video_slots
from app.cast_roles import ref as role_ref
from app.catalogue import CatalogueModel, catalogue
from app.enhance import escape, logo_only, project_context, project_screens, screen_name
from app.images import image_job_input, image_model_block
from app.models.brands import Brand
from app.models.breakdowns import BreakdownVersion
from app.models.files import StoredFile
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.prompts import check
from app.prompts.schemas import Breakdown, Frame, StoryboardFrames
from app.sheets import require_cast_sheets, require_looks, require_sheet, usable_files

PREFIX = {Kind.character: "char", Kind.place: "place", Kind.prop: "prop"}


def image_model() -> CatalogueModel:
    return next(m for m in catalogue().values() if m.kind == "image" and m.default)


def cast_looks(db: Session, project: Project) -> list[LibraryItem]:
    """The video's cast looks a breakdown may name (char:N): in its cast, in its workspace and
    not deleted. The breakdown's prompt and its check both use this, so the AI is never told
    about someone the check then calls "not part of this video" (Kel's empty chair)."""
    ids = set(project.cast_ids or [])
    items = db.scalars(
        select(LibraryItem).where(
            LibraryItem.id.in_(ids),
            LibraryItem.workspace_id == project.workspace_id,
            LibraryItem.kind == Kind.character,
            LibraryItem.archived.is_(False),
        )
    )
    return sorted(items, key=lambda i: project.cast_ids.index(i.id))


SHEET_SETS = (  # no role text or notes beside a sheet: "the golden dog" drew a Frenchie golden
    "looks exactly as their sheet; never describe their face, breed, coat, skin, hair or colouring"
)


def assets(db: Session, project: Project) -> dict[str, tuple[str, list[int]]]:
    """Every picture a frame may use: asset id -> (its line for the prompt, its file ids).
    The cast (each look with the roles it plays), the script's cast slots (a filled slot:N is
    the same line as the look that plays it, so one person never shows under two names or
    outfits; an empty one has no picture until Assets casts it), the
    brand's places and props, and the brand's screens."""
    out: dict[str, tuple[str, list[int]]] = {}
    roles = cast_roles(db, project)
    items = db.scalars(
        select(LibraryItem).where(
            LibraryItem.workspace_id == project.workspace_id,
            LibraryItem.archived.is_(False),
            LibraryItem.kind != Kind.character,
        )
    )
    for item in [*cast_looks(db, project), *items]:
        if item.kind != Kind.character and not any(b.id == project.brand_id for b in item.brands):
            continue
        key = f"{PREFIX[item.kind]}:{item.id}"
        parts = (key, item.kind, item.name, plays(roles.get(item.id, [])), item.notes)
        if item.kind == Kind.character and usable_files(item):  # rule 10: the sheet wins
            them = "; ".join(f"plays {short(s.role)}" for s in roles.get(item.id, []))
            parts = (key, item.kind, item.name, them, SHEET_SETS)
        out[key] = (" | ".join(x for x in parts if x), usable_files(item))
    for slot in video_slots(db, project):  # a role a breakdown may name before it's cast
        item_id = pick(db, project, slot)  # a deleted look: the role has none yet
        # A locked role uses the sheet it was locked with, even if its look has a newer sheet
        # waiting for approval (Reed's live test: "Mogging BF" read as not approved).
        locked = (
            [slot.sheet_file_id]
            if item_id and slot.library_item_id and slot.sheet_file_id
            else None
        )
        if f"char:{item_id}" in out:  # the look's own line: its notes win (Reed: used as is)
            line, files = out[f"char:{item_id}"]
            out[f"char:{item_id}"] = out[f"slot:{slot.id}"] = (line, locked or files)
            continue
        item = db.get(LibraryItem, item_id) if item_id else None
        look = "" if item else " (no look yet)"
        line = f"slot:{slot.id} | character | {slot.role} | {slot.description}{look}"
        out[f"slot:{slot.id}"] = (line, locked or (usable_files(item) if item else []))
    brand = db.get(Brand, project.brand_id)
    for s in project_screens(db, project):
        product = "product" in s.tags  # e.g. the Iron Paws bag: shown as a product, no face
        kind, what = ("product", "product") if product else ("screen", "app screen")
        name, tags = screen_name(s), ", ".join(s.tags)
        if logo_only(s, brand):  # rule 14: the logo is attached, the trading screen invented
            out[f"screen:{s.id}"] = (f"screen:{s.id} | logo | {brand.name} logo | for the {name} "
                                     f"screen ({tags}): invent it, this logo sharp in its top "
                                     "corner", [brand.logo_file_id])  # fmt: skip
            continue
        line = f"screen:{s.id} | {kind} | {name} | {brand.name} {what}, {tags}"
        out[f"screen:{s.id}"] = (line, [s.file_id])
    return out


def job_input(db: Session, project: Project, bd: BreakdownVersion, per_shot: bool) -> dict:
    system, _ = project_context(db, project, "storyboard")
    lines = "\n".join(dict.fromkeys(line for line, _ in assets(db, project).values()))
    parts = [
        image_model_block(image_model(), project.aspect_ratio),
        f"<assets>\n{escape(lines)}\n</assets>",
        f"<breakdown>\n{escape(json.dumps(bd.data, ensure_ascii=False))}\n</breakdown>",
    ]
    if per_shot:
        parts.append("<per_shot>true</per_shot>")
    return {
        "step": "storyboard",
        "project_id": project.id,
        "breakdown_id": bd.id,
        "system": system,
        "prompt": "\n".join(parts),
        "max_tokens": 32000,
    }


CHAR = ("char:", "slot:")  # a person's sheet: sent first, as the image model keeps likeness


def _shot(bd: Breakdown, shot_id: str):
    return next((s for scene in bd.scenes for s in scene.shots if s.id == shot_id), None)


def _name(known: dict, ref: str) -> str:
    """A character's name as people read it ("Mia"; a role "Nate, the son" is "Nate")."""
    parts = known[ref][0].split(" | ") if ref in known else []
    return parts[2].split(",")[0].strip() if len(parts) > 2 else "A character"


def hero(db: Session, project: Project, bd: Breakdown, known: dict) -> str | None:
    """The main character, as the breakdown names them (Reed, 2026-10-27: their sheet always
    goes first): of the script's Main roles in a shot, the one in the most shots (the first on
    a tie); with none, whoever is in the most shots. None when no one is, or on a tie."""
    shots = [s for scene in bd.scenes for s in scene.shots]

    def count(r: str) -> int:
        return sum(any(_same(known, r, c) for c in s.character_ids) for s in shots)

    mains = [role_ref(db, project, s) for s in video_slots(db, project) if s.kind == "Main"]
    if mains := [r for r in mains if count(r)]:
        return max(mains, key=count)
    everyone: list[str] = []  # one id per person (a role and its look are one)
    for c in (c for s in shots for c in s.character_ids):
        everyone += [] if any(_same(known, c, e) for e in everyone) else [c]
    counts = sorted(((count(c), c) for c in everyone), key=lambda x: -x[0])
    if not counts or (len(counts) > 1 and counts[0][0] == counts[1][0]):
        return None
    return counts[0][1]


def nearest_first(shot, known: dict, lead: str | None = None) -> list[str]:
    """The shot's cast, nearest the camera first, the main character (`lead`) always first.
    A breakdown has no depth, so: whoever speaks, then the order the action and reaction name
    them, then the shot's own order."""
    text = f"{shot.action} {shot.reaction or ''}".lower()
    speaker = (shot.speaker or "").lower()

    def key(item):
        i, ref = item
        name = _name(known, ref).lower() if ref in known else ""
        at = text.find(name) if name else -1
        first = 0 if lead and _same(known, ref, lead) else 1
        return (first, 0 if name and name in speaker else 1, at if at >= 0 else len(text) + 1, i)

    return [ref for _, ref in sorted(enumerate(shot.character_ids), key=key)]


def is_logo(known: dict, ref: str) -> bool:
    return known.get(ref, ("",))[0].split(" | ")[1:2] == ["logo"]


def one_logo(known: dict, ref: str) -> str:
    """Every logo-only screen is the one logo picture, so it stands as the first of them."""
    return next((k for k in known if is_logo(known, k) and _same(known, k, ref)), ref)


OLD_SCREEN = re.compile(r"logo, colou?rs and layout exact(ly)?")


def logo_words(prompt: str, tag: str, said: str, who: str) -> str:
    """A saved prompt's old words for a logo-only screen (`tag` matches its "[Image4]" or
    "image 4") say the logo, `said`, instead (rule 14). Free; again changes nothing."""

    seen: list[str] = []

    def fix(m: re.Match) -> str:
        if not re.search(tag, m[0]):
            return m[0]
        if lead := re.match(rf"(\s*(?:References: )?)(?:{tag} is the |Show the )", m[0]):
            seen.append(said)  # up and down both attached: the logo is said once
            return lead[1] + said if len(seen) == 1 else lead[1].strip(" ")
        return OLD_SCREEN.sub(
            f"{who}, the word {_word(who)} in lowercase, sharp and legible in the top corner, the "
            "rest of the screen invented",
            m[0],
        )

    return re.sub(r"[^.\n]*\.", fix, prompt)


def _word(who: str) -> str:
    """The brand's name, the word its logo must read ("fomo logo" -> "fomo"): QA-Live, video
    #17, a logo alone came out "JOMO" or as the icon with no word."""
    return who.removesuffix(" logo")


def logo_still(n: int, who: str) -> str:  # Nano Banana wants the exact words in quotes
    return (f'Image {n} is the {who}, the word "{_word(who)}" in lowercase: sharp and legible in '
            "the top corner of the phone's trading screen, invented with the chart this beat "
            "needs.")  # fmt: skip


def logo_clip(n: int, who: str) -> str:  # no quote marks: Seedance reads them as speech
    return f"[Image{n}] is the {who}: the word {_word(who)} in lowercase."


OLDER = "Advice: Drawn from an older look of "


def older_looks(db: Session, known: dict, frame: StoryboardFrame) -> list[str]:
    """Who or what in a frame's still was drawn from an earlier sheet than its approved one
    now (QA-Live, video #17: 5 stills kept Goth GF 2's old look; N6: a place's too): the
    still's job sent other pictures. None when its job isn't known (a still picked back, or
    from before)."""
    jobs = db.scalars(select(Job).where(Job.project_id == frame.project_id, Job.kind == "image",
                                        Job.status == JobStatus.succeeded))  # fmt: skip
    drew = [j for j in jobs if j.input.get("frame_id") == frame.id
            and ((j.output or {}).get("file_ids") or [None])[0] == frame.file_id]  # fmt: skip
    if not frame.file_id or not drew:
        return []
    sent = set(drew[-1].input.get("files", {}).get("image_input", []))
    return drawn_from_older(known, frame.reference_ids, sent)


SHEETS = (*CHAR, "place:", "prop:")  # Cast & places pictures a sheet change can make old


def drawn_from_older(known: dict, refs: list[str], sent: set[int]) -> list[str]:
    """Who or what among `refs` has an approved picture now that wasn't among the files a
    still or take was made from (N6: a Cast & places sheet changed since)."""
    sheets = {r: known.get(r, ("", []))[-1][:1] for r in refs if r.startswith(SHEETS)}
    return [_name(known, r) for r, f in sheets.items() if f and f[0] not in sent]


def newer_sheets(db: Session, known: dict, refs: list[str], job_id: int | None) -> list[str]:
    """The people among `refs` whose approved sheet was made after the call that wrote the
    prompt: its look words may be the old look's (QA-Live, video #17)."""
    job = db.get(Job, job_id) if job_id else None
    files = {r: known.get(r, ("", []))[-1][:1] for r in refs if r.startswith(CHAR)}
    made = {r: db.get(StoredFile, f[0]) for r, f in files.items() if f}  # None: purged
    return [r for r, s in made.items() if job and s and s.created_at > job.created_at]


def say_logo(known: dict, prompt: str, ids: list[str], clip: bool = False) -> str:
    """Old words for each logo-only screen among `ids` (a clip's images, or a frame's) say the
    logo: run by the free repair and before every paid still or take, so no logo goes out
    labelled as a chart (QA on #654)."""
    for n, r in enumerate(ids, 1):
        if is_logo(known, r):
            who = _name(known, r)
            tag, said = (rf"\[Image{n}\]", logo_clip(n, who)) if clip else (
                rf"(?i:\bimage {n}\b)", logo_still(n, who))  # fmt: skip
            prompt = logo_words(prompt, tag, said, who)
    return prompt


def _same(known: dict, a: str, b: str) -> bool:
    """The same person: one id, or a cast role and the look that plays it (one sheet)."""
    if a == b:
        return True
    sheet_a, sheet_b = known.get(a, ("", []))[1][:1], known.get(b, ("", []))[1][:1]
    return bool(sheet_a) and sheet_a == sheet_b


IMAGES = re.compile(r"(?i)\b(images?\s+)(\d+(?:\s*(?:,|and|&)\s*\d+)*)")


def _renumber(
    prompt: str, moved: dict[int, int], names: dict[int, str], pattern: re.Pattern = IMAGES
) -> str:
    """'image N' (or a clip's '[ImageN]', `pattern`) follows its picture to its new place;
    a dropped one becomes the name."""

    def one(n: str) -> str:
        k = int(n)
        return str(moved[k]) if k in moved else n

    def fix(m: re.Match) -> str:
        nums = [int(n) for n in re.findall(r"\d+", m[2])]
        if len(nums) == 1 and nums[0] in names:
            return names[nums[0]]
        tail = m[0][m.end(2) - m.start() :]
        return m[1] + re.sub(r"\d+", lambda d: one(d[0]), m[2]) + tail

    return pattern.sub(fix, prompt)


def is_product(known: dict, ref: str) -> bool:
    return " | product | " in known.get(ref, ("", []))[0]


def shown_product(
    db: Session, project: Project, text: str, known: dict, have, screens: set[str]
) -> str | None:
    """The real product a shot's words show ("an Iron Paws bag on a shelf", Reed's #32 c9: it
    was drawn invented), as if the breakdown listed it: the video's flavour, or the one
    named; only one of the video's own pictures, none when a product is attached, and never
    a clip's fourth screen (`screens`: its clip's; "keep the 3" blocks)."""
    from app.breakdown import products_of

    products = products_of(db, project)
    if any(is_product(known, r) or r in {p["id"] for p in products} for r in have):
        return None
    if len(screens) >= 3:
        return None
    found = check.product_shown(text, db.get(Brand, project.brand_id).name, products)
    return found if found in known else None


def weakest(refs: list[str], known: dict) -> list[str]:
    """Room for the real product when the pictures are full: the last place or prop goes."""
    drop = next((r for r in reversed(refs) if r.split(":")[0] in ("place", "prop")), None)
    return [r for r in refs if r != drop]


def with_cast(
    db: Session,
    project: Project,
    frame: Frame,
    bd: Breakdown,
    known=None,
    trim: bool = True,
    note: str = "",
) -> Frame:
    """Every character in the frame's shot gets their approved sheet, whatever the storyboard
    picked (Reed's live test: a frame without Mia's sheet couldn't be made). People come first,
    nearest the camera first, within the image model's limits; then the place, props and
    screens in their order. The prompt's "image N" follow their pictures. Free; doing it
    again changes nothing. With trim off (an editor's edit, or a saved frame) nothing already
    picked is dropped: missing sheets are only added while there's room."""
    known = known if known is not None else assets(db, project)
    shot = _shot(bd, frame.shot_id)
    if shot is None:
        return frame
    m = image_model()
    refs = list(dict.fromkeys(one_logo(known, r) for r in frame.reference_ids))
    people = [r for r in refs if r.startswith(CHAR)]
    objects = [r for r in refs if not r.startswith(CHAR)]
    cast = nearest_first(shot, known, hero(db, project, bd, known))
    missing = [
        c for c in cast if known.get(c, ("", []))[1] and not any(_same(known, c, r) for r in people)
    ]

    def rank(r: str) -> int:
        return next((i for i, c in enumerate(cast) if _same(known, r, c)), len(cast))

    room = len(people) + len(missing)
    if m.max_character_images:
        room = min(room, m.max_character_images)
    if m.max_reference_images:
        room = min(room, max(m.max_reference_images - len(objects), 0))
    if trim:  # stable: people not in the shot stay last
        people = sorted(people + missing, key=rank)[:room]
    else:  # an edit keeps everyone; the main character still moves first
        missing = missing[: max(room - len(people), 0)]
        picked, people = people, sorted(people + missing, key=rank)
    new = people + objects
    # The shot's screens too, after everything else, while there's room (the Director, #556),
    # and the real product its words show (a Change it note's too), making room if it must.
    words = f"{shot.action} {shot.camera} {frame.prompt} {note}"
    clip = next((c for c in bd.clips if frame.shot_id in c.shot_ids), None)
    shown = {x for sc in bd.scenes for s in sc.shots if clip and s.id in clip.shot_ids
             for x in s.screen_ids}  # fmt: skip
    product = shown_product(db, project, words, known, [*shot.screen_ids, *new], shown)
    if product and m.max_reference_images and len(new) >= m.max_reference_images:
        new = weakest(new, known)
    wanted = [*([product] if product else []), *shot.screen_ids]  # the product first
    screens = [s for s in dict.fromkeys(one_logo(known, s) for s in wanted)
               if s in known and s not in new]  # fmt: skip
    if m.max_reference_images:
        screens = screens[: max(m.max_reference_images - len(new), 0)]
    if not (trim or missing or screens or people != picked):
        return frame  # an edit with nothing to add or move stays as the editor saved it
    new += screens
    if new == frame.reference_ids:
        return frame
    was = [one_logo(known, r) for r in frame.reference_ids]
    moved = {i + 1: new.index(r) + 1 for i, r in enumerate(was) if r in new}
    dropped = {i + 1: _name(known, r) for i, r in enumerate(was) if r not in new}
    prompt = _renumber(frame.prompt, moved, dropped)
    for r in new:
        if r in screens and is_logo(known, r):
            prompt += " " + logo_still(new.index(r) + 1, _name(known, r))
        elif r in screens and is_product(known, r):
            prompt += f" Show the real {_name(known, r)} from image {new.index(r) + 1} as it is."
        elif r in screens:
            prompt += f" Show the {_name(known, r)} screen from image {new.index(r) + 1} as it is."
        elif r not in was:
            prompt += (
                f" Keep {_name(known, r)} from image {new.index(r) + 1} exactly as on their sheet."
            )
    return Frame(clip_id=frame.clip_id, shot_id=frame.shot_id, prompt=prompt, reference_ids=new)


def frame_problems(db: Session, project: Project, frame: Frame, breakdown_id: int) -> list[str]:
    """With the frame's breakdown, a character in the shot without an approved look is
    flagged too, by name, a role not cast yet included (Reed, 2026-10-27: nothing is drawn
    without a sheet for everyone in it); the problem links to Assets."""
    m = image_model()
    known = assets(db, project)
    bd = Breakdown.model_validate(db.get(BreakdownVersion, breakdown_id).data)
    found = check.storyboard(
        StoryboardFrames(frames=[frame]), m.max_reference_images, m.max_character_images, bd
    )  # its people are checked below, by name, with roles not cast yet left out
    problems = [p for p in found if not p.endswith("in the shot without a sheet")]
    problems += [
        f"{frame.clip_id}: unknown reference {r}" for r in frame.reference_ids if r not in known
    ]
    shot = _shot(bd, frame.shot_id)
    people = [r for r in frame.reference_ids if r.startswith(CHAR)]
    if shot and (not m.max_character_images or len(people) < m.max_character_images):
        for c in shot.character_ids:
            if not any(_same(known, c, r) for r in people):
                problems.append(
                    f"{_name(known, c)} has no approved look yet. Approve one in Assets."
                )
    return plain(problems, names(known))


TOO_MANY = "more references than"


LEFT_OUT = "Advice: Left out "


def left_out(names: list[str], limit: int) -> list[str]:
    """Advice naming the pictures a trim to the model's limit left out (QA on #527)."""
    if not names:
        return []
    return [f"{LEFT_OUT}{', '.join(dict.fromkeys(names))}: the model takes {limit} "
            "pictures, nearest the camera first."]  # fmt: skip


def _cap(frame: Frame, known: dict) -> Frame:
    """Over the image model's limit even with the nearest people only: the last pictures
    (props, then screens) go, and the prompt names them instead."""
    limit = image_model().max_reference_images
    if not limit or len(frame.reference_ids) <= limit:
        return frame
    new = frame.reference_ids[:limit]
    dropped = {i + 1: _name(known, r) for i, r in enumerate(frame.reference_ids) if r not in new}
    prompt = _renumber(frame.prompt, {}, dropped)
    return frame.model_copy(update={"prompt": prompt, "reference_ids": new})


def repair(db: Session, project: Project) -> int:
    """Give every frame of the video the sheets of the characters in its shot (`with_cast`),
    and check it again. Free and idempotent: run when the storyboard is opened. Returns how
    many frames changed."""
    known, changed = assets(db, project), 0
    breakdowns: dict[int, Breakdown] = {}
    rows = db.scalars(select(StoryboardFrame).where(StoryboardFrame.project_id == project.id))
    for row in rows:
        if row.breakdown_id not in breakdowns:
            data = db.get(BreakdownVersion, row.breakdown_id).data
            breakdowns[row.breakdown_id] = Breakdown.model_validate(data)
        was = Frame(clip_id=row.clip_id, shot_id=row.shot_id, prompt=row.prompt,
                    reference_ids=row.reference_ids)  # fmt: skip
        now = with_cast(db, project, was, breakdowns[row.breakdown_id], known, trim=False)
        now = now.model_copy(update={"prompt": say_logo(known, now.prompt, now.reference_ids)})
        for r in newer_sheets(db, known, now.reference_ids, row.job_id):  # the sheet sets it
            now = now.model_copy(update={"prompt": bare(now.prompt, _name(known, r))})
        problems = frame_problems(db, project, now, row.breakdown_id) + [
            p for p in row.problems or [] if p.startswith(LEFT_OUT) or p == REFUSED
        ]  # what an earlier trim left out, or a refusal, stays said
        if any(p.lower().startswith(TOO_MANY) for p in problems):  # never a dead end
            now = _cap(with_cast(db, project, was, breakdowns[row.breakdown_id], known), known)
            problems = frame_problems(db, project, now, row.breakdown_id) + left_out(
                [_name(known, r) for r in was.reference_ids if r not in now.reference_ids],
                image_model().max_reference_images,
            )
        if older := older_looks(db, known, row):  # flagged once: an approval after it stays
            problems.append(f"{OLDER}{', '.join(older)}. Redraw it to show the new look.")
            if not any(p.startswith(OLDER) for p in row.problems or []):
                row.still_stale, row.approved = True, False  # "Out of date", one-click redraw
        if now == was and problems == (row.problems or []):
            continue
        row.prompt, row.reference_ids, row.problems = now.prompt, now.reference_ids, problems
        changed += 1
    return changed


GENTLE = {  # what Nano Banana refuses (check.FLAGGED), said so it draws (Reed, #520)
    "leggings": "workout pants", "thigh": "leg",
    "thighs": "legs", "cleavage": "neckline", "pus": "redness", "discharge": "irritation",
    "wound": "scrape", "wounds": "scrapes",
}  # fmt: skip
STEMS = {"ooz": "glistening", "blood": "red", "vomit": "feeling sick"}


def soften(prompt: str) -> str:
    """The prompt with only the words the image model refuses said gently; free, no model
    call. The same prompt when there's nothing to soften."""

    def gentle(m: re.Match) -> str:
        word = m[0].lower()
        out = GENTLE.get(word) or next(v for k, v in STEMS.items() if word.startswith(k))
        return out[:1].upper() + out[1:] if m[0][:1].isupper() else out

    return check.FLAGGED.sub(gentle, prompt)


def softened(prompt: str) -> dict | None:
    """The change note for a frame softened by itself: shown with its Before and After."""
    after = soften(prompt)
    if after == prompt:
        return None
    return {"note": "Softened so it can be drawn.", "status": "done", "before": prompt,
            "after": after, "unchanged": False, "softened": True}  # fmt: skip


REFUSED = ("Advice: the image model refused to draw this still, so nothing was charged. "
           "It may refuse a word here: soften it, or change the prompt.")  # fmt: skip


def still_refused(db: Session, job: Job) -> None:
    """The image model refusing a still ("sensitive", E005) says so plainly on its frame,
    with Soften it (Reed, 2026-10-28). Failed stills aren't counted (credits.COUNTED)."""
    if not re.search(r"sensitive|E005|ContentModeration|flagged for", job.error_detail or "", re.I):
        return
    job.error = REFUSED.removeprefix("Advice: ").capitalize()
    frame = db.get(StoryboardFrame, job.input.get("frame_id") or 0)
    if frame and REFUSED not in (frame.problems or []):
        frame.problems = [*(frame.problems or []), REFUSED]


def save_frames(db: Session, job: Job) -> None:
    """Replace the project's frames with Claude's new ones (a new storyboard was asked for), or
    the one frame Redo this frame wrote again."""
    if job.input.get("redo_frame_id"):
        from app import redo_frame

        return redo_frame.save(db, job)
    project = db.get(Project, job.input["project_id"])
    result = StoryboardFrames.model_validate(job.output)
    db.execute(delete(StoryboardFrame).where(StoryboardFrame.project_id == project.id))
    bd = Breakdown.model_validate(db.get(BreakdownVersion, job.input["breakdown_id"]).data)
    known = assets(db, project)
    for f in (with_cast(db, project, f, bd, known) for f in result.frames):
        note = softened(f.prompt)  # a word the image model refuses never blocks
        f = f.model_copy(update={"prompt": note["after"]}) if note else f
        db.add(
            StoryboardFrame(
                project_id=project.id,
                breakdown_id=job.input["breakdown_id"],
                job_id=job.id,
                clip_id=f.clip_id,
                shot_id=f.shot_id,
                prompt=f.prompt,
                reference_ids=f.reference_ids,
                problems=frame_problems(db, project, f, job.input["breakdown_id"]),
                change=note,
            )
        )


def still_price(db: Session, project: Project) -> int:
    """What one still costs (Make still, Redo, Save and redraw), rounded up: the image model's
    price, the same for every frame of the video."""
    from app.credits import estimate, price

    job = image_job_input(image_model(), "", project.aspect_ratio)
    return price(estimate(db, project.workspace_id, "image", Decimal(1), job))


def render_input(db: Session, project: Project, frame: StoryboardFrame, note: str = "") -> dict:
    """The Nano Banana job for one frame's still: the project's aspect ratio (always sent),
    character sheets first, then the place, props and screens, in the frame's order."""
    from app.breakdown import would_show

    known = assets(db, project)
    breakdown = db.get(BreakdownVersion, frame.breakdown_id)
    require_cast_sheets(db, breakdown.data, [frame.shot_id], known)
    require_looks(would_show(db, project, breakdown.data, [frame.shot_id]), known)
    characters, objects = [], []
    for ref in frame.reference_ids:
        if ref not in known:
            raise HTTPException(
                409, "A picture on this frame is no longer part of this video. Edit the frame."
            )
        files = known[ref][1][:1]  # the approved sheet (characters, places) or main picture
        if not files and ref.startswith(("char:", "place:")):
            require_sheet(db.get(LibraryItem, int(ref.split(":")[1])))
        (characters if ref.startswith(CHAR) else objects).extend(files)
    prompt = say_logo(known, frame.prompt, frame.reference_ids)  # never a logo called a chart
    prompt = f"{prompt}\nChange from the last still: {note}" if note else prompt
    job = image_job_input(
        image_model(), prompt, project.aspect_ratio, characters=characters, objects=objects
    )
    return {**job, "step": "frame", "project_id": project.id, "frame_id": frame.id}


def save_still(db: Session, job: Job) -> None:
    """Attach the rendered still to its frame (if the frame still exists)."""
    frame = db.get(StoryboardFrame, job.input["frame_id"])
    file_ids = (job.output or {}).get("file_ids") or []
    if frame and file_ids:
        if frame.file_id and frame.file_id != file_ids[0]:  # the old still stays, to pick back
            frame.earlier = [
                *(frame.earlier or []),
                {"file_id": frame.file_id, "prompt": job.input.get("was_prompt", frame.prompt)},
            ]
        frame.file_id, frame.approved, frame.still_stale = file_ids[0], False, False
        if job.id and (frame.change or {}).get("made_job_id") == job.id:  # Redo: now it's done
            frame.change = {**frame.change, "status": "done"}
