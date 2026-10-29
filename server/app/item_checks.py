"""The advisory check on a still or a take (flows.md 1b, P4): after each one finishes, one
cheap look compares it with the cast's character sheets and, on a ★ shot, the product's
image. It gives Advice only: it never blocks, never changes an approval and never redoes
anything. On the test site it runs on the free stand-in until the Producer approves a real
test (BS_ITEM_CHECKS_PAID)."""

import logging
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.credits import estimate, fits
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.checks import ItemCheck
from app.models.jobs import Job
from app.models.projects import Project
from app.prompts import check
from app.prompts.schemas import ItemCheck as Answer
from app.settings import get_settings

log = logging.getLogger(__name__)
KIND = "check-claude"


class FindingOut(BaseModel):
    index: int  # what Looks fine sends back
    kind: str  # face, outfit or product
    text: str  # the card's line: "Mia's face may differ from her sheet"
    note: str  # the ready "Change this…" note


class CheckOut(BaseModel):
    id: int
    status: str  # checking, ok, advice, failed or skipped
    findings: list[FindingOut]  # the ones not dismissed (Looks fine)


def on() -> bool:
    """Checks run on the free stand-in, or for real only once the Producer turns them on."""
    settings = get_settings()
    return settings.fake_providers or settings.item_checks_paid


def price(db: Session, project: Project) -> Decimal:
    return estimate(db, project.workspace_id, KIND, Decimal(1), {})


def scope() -> str:
    return get_settings().item_check_scope


def _shots(db: Session, breakdown_id: int) -> dict[str, dict]:
    data = db.get(BreakdownVersion, breakdown_id).data
    return {s["id"]: s for sc in data.get("scenes", []) for s in sc.get("shots", [])}


def _products(db: Session, project: Project) -> set[str]:
    """The brand's products as picture ids: product screens (the bag) and props."""
    from app.enhance import project_screens

    return {f"screen:{s.id}" for s in project_screens(db, project) if s.product
            or "product" in (s.tags or [])}  # fmt: skip


def key(db: Session, project: Project, shots: list[dict], refs: list[str]) -> bool:
    """A ★-product or speaking item: the ones checked by default (key_takes)."""
    products = _products(db, project)
    shown = {x for s in shots for x in s.get("screen_ids", [])} | set(refs)
    return (
        any(s.get("line") for s in shots)
        or bool(shown & products)
        or any(r.startswith("prop:") for r in refs)
    )


def _one_take(db: Session, project: Project, breakdown_id: int, shot_ids: list[str]) -> Decimal:
    """A check never takes the room for one more take of its clip (Flow-QA, Producer): it's
    skipped when, after it, the video couldn't pay for one."""
    from app.clip_takes import take_credits
    from app.models.clips import ProjectClip

    data = db.get(BreakdownVersion, breakdown_id).data
    clip_id = next((c["id"] for c in data.get("clips", []) if set(shot_ids) & set(c["shot_ids"])),
                   None)  # fmt: skip
    row = db.scalar(select(ProjectClip).where(ProjectClip.project_id == project.id,
                                              ProjectClip.clip_id == clip_id))  # fmt: skip
    return take_credits(db, project, row) if row else Decimal(0)


def per_video(db: Session, project: Project) -> Decimal:
    """About what the checks cost on this video, at the scope in force: one take a clip (and
    one still a clip with `everything`), from its newest breakdown."""
    row = db.scalar(select(BreakdownVersion).where(BreakdownVersion.project_id == project.id)
                    .order_by(BreakdownVersion.id.desc()).limit(1))  # fmt: skip
    if row is None or not on():
        return Decimal(0)
    shots = _shots(db, row.id)
    clips = [[shots[i] for i in c["shot_ids"] if i in shots] for c in row.data.get("clips", [])]
    if scope() == "key_takes":
        count = sum(key(db, project, c, []) for c in clips)
    else:
        count = len(clips) * (2 if scope() == "everything" else 1)
    return price(db, project) * count


def queue(db: Session, job: Job, target: str, target_id: int, file_id: int, refs: list[str],
          breakdown_id: int, shot_ids: list[str]) -> ItemCheck | None:  # fmt: skip
    """After a still or take is saved (in the worker): its check, unless checks are off, it
    has nobody to compare, or it would go over the video's budget ("skipped", never held)."""
    from app.storyboard import assets

    project = db.get(Project, job.project_id) if job.project_id else None
    if not project or not on() or (target == "frame" and scope() != "everything"):
        return None
    shots = [s for i, s in _shots(db, breakdown_id).items() if i in shot_ids]
    if scope() == "key_takes" and not key(db, project, shots, refs):
        return None
    known = assets(db, project)
    sheets = [r for r in dict.fromkeys(refs) if r.startswith(("char:", "slot:"))
              and known.get(r, ("", []))[1]]  # fmt: skip
    products = _products(db, project)
    product = next((r for r in refs if (r.startswith("prop:") or r in products)
                    and known.get(r, ("", []))[1]), None)  # fmt: skip
    if not sheets and not product:
        return None
    frames = 3 if scope() == "everything" else 1  # a take as one frame keeps it to cents
    row = ItemCheck(project_id=project.id, target=target, target_id=target_id, status="checking")
    db.add(row)
    user = db.get(User, job.created_by_id)
    credits = price(db, project)
    if not user or fits(db, project, user, credits + _one_take(db, project, breakdown_id,
                                                                 shot_ids)):  # fmt: skip
        row.status = "skipped"  # "Not checked: the video is at its budget."
        db.flush()
        return row
    images = [known[r][1][0] for r in sheets]
    pair = None
    if product:
        images.append(known[product][1][0])
        pair = (f"product:{product.split(':')[1]}", known[product][0])
    text = prompts.item_check_input(" ".join(s["action"] for s in shots),
                                    [(r, known[r][0]) for r in sheets], pair,
                                    frames=frames if target == "take" else 1)  # fmt: skip
    data = {"step": "item_check", "item_check_id": None, "project_id": project.id,
            "system": [prompts.system("item_check")], "prompt": text, "effort": "low",
            "max_tokens": 2000, "fit_images_to": 1024,
            "ref_ids": sheets + ([pair[0]] if pair else []),
            "files": {"reference_images": [file_id] * (target == "frame") + images}}  # fmt: skip
    if target == "take":
        data["take_frames"] = {"file_id": file_id, "count": frames}  # the worker reads them
    db.flush()
    data["item_check_id"] = row.id
    check_job = Job(workspace_id=project.workspace_id, created_by_id=user.id, kind=KIND,
                    provider="claude", input=data, project_id=project.id,
                    brand_id=project.brand_id, credits=credits, status="queued",
                    approved_by_id=job.approved_by_id)  # fmt: skip
    db.add(check_job)
    db.flush()
    row.job_id = check_job.id
    return row


def queue_safely(db: Session, *args) -> None:
    """A check never stops a still or a take from being saved."""
    try:
        with db.begin_nested():
            queue(db, *args)
    except Exception:
        log.exception("couldn't queue the check for %s %s", args[1], args[2])


def save(db: Session, job: Job) -> None:
    """The check's answer: only findings about a reference it was given."""
    row = db.get(ItemCheck, job.input.get("item_check_id") or 0)
    if not row:
        return
    answer = check.item_check(Answer.model_validate(job.output), job.input.get("ref_ids", []))
    row.findings = [{"kind": f.kind, "role": f.who, "text": f.says, "change_note": f.note}
                    for f in answer.findings]  # fmt: skip
    row.status = "done"


def failed(db: Session, job: Job) -> None:
    """ "Couldn't check this one." Nothing is charged (a failed job isn't counted)."""
    row = db.get(ItemCheck, job.input.get("item_check_id") or 0)
    if row:
        row.status = "failed"


def latest(db: Session, target: str, target_ids: list[int]) -> dict[int, ItemCheck]:
    rows = db.scalars(select(ItemCheck).where(ItemCheck.target == target,
                                              ItemCheck.target_id.in_(target_ids))
                      .order_by(ItemCheck.id))  # fmt: skip
    return {r.target_id: r for r in rows}  # the newest wins


def shown(db: Session, row: ItemCheck | None) -> CheckOut | None:
    if row is None:
        return None
    if row.status == "checking" and row.job_id:  # its job ended without an answer
        job = db.get(Job, row.job_id)
        if job and job.status in ("failed", "cancelled"):
            row.status = "failed"
    gone = {d["index"] for d in row.dismissed or []}
    findings = [FindingOut(index=i, kind=f["kind"], text=f["text"], note=f["change_note"])
                for i, f in enumerate(row.findings or []) if i not in gone]  # fmt: skip
    status = {"checking": "checking", "failed": "failed", "skipped": "skipped"}.get(
        row.status, "advice" if findings else "ok"
    )
    return CheckOut(id=row.id, status=status, findings=findings)


def with_advice(db: Session, target: str, ids: list[int]) -> int:
    """How many of these items' newest checks still have Advice ("2 approved with Advice")."""
    rows = latest(db, target, ids).values()
    return sum(1 for r in rows if (out := shown(db, r)) and out.findings)
