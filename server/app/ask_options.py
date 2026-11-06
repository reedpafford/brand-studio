"""The options on an ask card (app/asks.py): the brand's saved items first, each with how many
of its videos use it, and Generate options (paid, "up to" first; what it makes stays with this
video and is never the brand's, rule 12)."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.accounts import User
from app.models.asks import Ask
from app.models.brands import Brand, BrandScreen
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project

GENERATES = {"cast": "nano-banana-2.1", "place": "nano-banana-2.1", "presenter": "nano-banana-pro"}
OPTIONS = 3  # Generate options makes 3 a round
ASK = "ask_id"  # in an option's job's input: its card
WORDS = {"cast": "character", "presenter": "character", "place": "place"}
NO_GENERATE = {
    "product": "A product shot has to be the real product: upload it or pick a saved one.",
    "brand_item": "This has to be the brand's real screen: upload it or pick a saved one.",
}

# --- The brand's saved options ----------------------------------------------------------------


def saved(db: Session, project: Project, kind: str) -> list[dict]:
    """The brand's own items that can answer this kind, each {id, name, note, file_id,
    used_in, sample_file_id}: characters, places, products, screens or voices."""
    brand = db.get(Brand, project.brand_id)
    if kind in WORDS:
        return _items(db, brand, Kind(WORDS[kind]), "")
    if kind == "product":
        shots = [s for s in _screens(db, brand) if s["product"]]
        return _items(db, brand, Kind.prop, "product") + shots
    if kind == "brand_item":
        return _screens(db, brand)
    if kind == "voice":
        return _voices(db, brand)
    return []


def _items(db: Session, brand: Brand, kind: Kind, note: str) -> list[dict]:
    rows = db.scalars(select(LibraryItem).where(
        LibraryItem.brands.any(Brand.id == brand.id), LibraryItem.kind == kind,
        LibraryItem.archived.is_(False), LibraryItem.owner_project_id.is_(None),
        LibraryItem.owner_script_id.is_(None)).order_by(LibraryItem.id)).all()  # fmt: skip
    used = _used(db, brand)
    out = [{"id": f"item:{i.id}", "name": i.name, "note": note,
            "file_id": i.sheet_file_id or i.source_photo_file_id or next(iter(i.image_file_ids
                                                                            or []), None),
            "used_in": used.get(i.id, 0), "sample_file_id": None}
           for i in rows]  # fmt: skip
    return sorted(out, key=lambda o: -o["used_in"])


def _used(db: Session, brand: Brand) -> dict[int, int]:
    """How many of the brand's videos each saved item is in."""
    count: dict[int, int] = {}
    rows = db.execute(select(Project.cast_ids, Project.slot_cast).where(
        Project.brand_id == brand.id, Project.archived_at.is_(None)))  # fmt: skip
    for cast, slots in rows:
        for item in {*(cast or []), *((slots or {}).values())}:
            count[item] = count.get(item, 0) + 1
    return count


def _screens(db: Session, brand: Brand) -> list[dict]:
    rows = db.scalars(select(BrandScreen).where(BrandScreen.brand_id == brand.id,
                                                BrandScreen.deleted_at.is_(None))
                      .order_by(BrandScreen.id)).all()  # fmt: skip
    return [{"id": f"screen:{s.id}", "name": s.variant or s.name, "file_id": s.file_id,
             "note": "still" if s.product else f"{brand.name} screen", "used_in": 0,
             "sample_file_id": None, "product": s.product}
            for s in rows]  # fmt: skip


def _voices(db: Session, brand: Brand) -> list[dict]:
    """The voices this brand may use (#1314's rows: its own saved and cloned voices, the
    styles' voices, then the app's voices), each with its free sample and how many of the
    brand's narrations used it, most used first. Refs as `projects.voice` takes them:
    "voice:<id>" or "stock:<key>"."""
    from app import narration, voices
    from app.models.songs import SongTake
    from app.routes.voices import _url

    takes = db.execute(select(SongTake.voice, SongTake.project_id)
                       .join(Project, Project.id == SongTake.project_id)
                       .where(Project.brand_id == brand.id, SongTake.kind == narration.KIND,
                              SongTake.deleted_at.is_(None))).all()  # fmt: skip
    videos: dict[str, set] = {}
    for said, pid in takes:
        videos.setdefault(said, set()).add(pid)
    rows = voices.rows(db, brand.workspace_id, brand.id)
    out = [{"id": f"voice:{v.id}", "name": v.name, "file_id": None,
            "note": (f"Described: \u201c{v.description}\u201d" if v.kind == "described"
                     else v.description),
            "used_in": len(videos.get(f"voice:{v.id}", ())), "sample_file_id": v.sample_file_id,
            "sample_url": _url(voices.sample_name(v))}
           for v in rows  # what narration reads: a ready clone, or one described in words
           if voices.state(db, v)[0] in ("ready", "may_expire")]  # fmt: skip
    for key in voices.stock_keys():
        given = voices.stock(key)
        out.append({"id": f"stock:{key}", "name": given["name"], "note": given["description"],
                    "file_id": None, "used_in": len(videos.get(key, ())), "sample_file_id": None,
                    "sample_url": _url(voices.sample_name(None, key))})  # fmt: skip
    return sorted(out, key=lambda o: -o["used_in"])


# --- Generate options (paid; made for this video only) ----------------------------------------


def generate(db: Session, user: User, ask: Ask, like: int | None = None, change: str = "") -> None:
    """Three options for this video only, at the price on the button: from the question, more
    like one option (`like`), or with a change. A failed round charges nothing; an editor's
    press past the budget waits for the owner on the card itself."""
    from app.asks import NOT_NEEDED, OPEN, state
    from app.routes.jobs import HELD, enqueue

    if ask.kind not in GENERATES:
        raise HTTPException(409, NO_GENERATE.get(ask.kind, "This question can't make options."))
    if ask.state not in OPEN:
        raise HTTPException(409, NOT_NEEDED if ask.state == "not_needed" else "It's answered.")
    if state(db, ask) in ("generating", "held"):
        raise HTTPException(409, "Options are being made.")
    project = db.get(Project, ask.project_id)
    refs = []
    if like is not None:
        made = options(db, ask)
        if not 0 <= like < len(made) or not made[like]["file_id"]:
            raise HTTPException(422, "Pick one of the options that's made.")
        refs = [made[like]["file_id"]]
    data = _option_input(project, ask, change, refs)
    one = generate_price(db, ask)
    first = enqueue(db, user, "image", data, project=project, provider="replicate",
                    hold=one / OPTIONS * (OPTIONS - 1))  # fmt: skip
    wait = first.input.get(HELD, "")
    jobs = [first.id] + [enqueue(db, user, "image", data, project=project, provider="replicate",
                                 prepaid=not wait, wait=wait).id
                         for _ in range(OPTIONS - 1)]  # fmt: skip
    ask = db.get(Ask, ask.id)
    ask.rounds = [*ask.rounds, {"jobs": jobs, "like": like, "change": change.strip()[:500]}]
    ask.state = "open"
    db.commit()


def _option_input(project: Project, ask: Ask, change: str, refs: list[int]) -> dict:
    from app import prompts
    from app.catalogue import get_model
    from app.images import image_job_input

    kind = "place" if ask.kind == "place" else "character"
    words = " ".join(x for x in (ask.describe or ask.subject or ask.question, change.strip()) if x)
    prompt = prompts.sheet_prompt(kind, words, from_photo=bool(refs), style_id=project.look)
    aspect = "16:9" if kind == "place" else "9:16"
    job = image_job_input(get_model(GENERATES[ask.kind]), prompt, aspect, objects=refs)
    return {**job, "step": "ask_option", ASK: ask.id}


def generate_price(db: Session, ask: Ask) -> Decimal:
    """A round's price "up to" (rule 36): its options at the model's price."""
    from app.credits import estimate

    if ask.kind not in GENERATES:
        return Decimal(0)
    project = db.get(Project, ask.project_id)
    one = estimate(db, project.workspace_id, "image", Decimal(1),
                   _option_input(project, ask, "", []))  # fmt: skip
    return one * OPTIONS


def options(db: Session, ask: Ask) -> list[dict]:
    """The newest round's options, each {index, state, file_id, job_id}."""
    if not ask.rounds:
        return []
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_(ask.rounds[-1]["jobs"])))}
    out = []
    for n, job_id in enumerate(ask.rounds[-1]["jobs"]):
        job = jobs.get(job_id)
        files = (job.output or {}).get("file_ids") or [] if job else []
        out.append({"index": n, "job_id": job_id, "state": str(job.status) if job else "failed",
                    "file_id": files[0] if job and job.status == JobStatus.succeeded and files
                    else None})  # fmt: skip
    return out


def stop_options(db: Session, ask: Ask, drop: bool = False) -> None:
    """The newest round's options not made yet are stopped: nothing is charged for them.
    `drop` (Cancel): a round that made nothing goes, and the card is open again."""
    from app.routes.jobs import stop_jobs

    if not ask.rounds:
        return
    stop_jobs(db, Job.id.in_(ask.rounds[-1]["jobs"]))
    db.flush()
    if drop and not any(o["file_id"] for o in options(db, ask)):
        ask.rounds = ask.rounds[:-1]


def spent(db: Session, ask: Ask) -> Decimal:
    """What its options cost so far: every round, failed and stopped ones at nothing."""

    ids = [j for r in ask.rounds for j in r["jobs"]]
    if not ids:
        return Decimal(0)
    return Decimal(db.scalar(select(func.coalesce(func.sum(Job.credits), 0)).where(
        Job.id.in_(ids), Job.status == JobStatus.succeeded)) or 0)  # fmt: skip
