"""What was really spent, and where (Reed, 9 Nov: "track API usage per brand (from all api
providers), and spend per video/project"). Owner only: these are dollars. One reading of the
job records for every figure: each Usage row as its provider reported it (else at list
price, marked), and a job sent to a paid provider with no Usage row (a dropped connection) at
its own list price."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.catalogue import get_model
from app.credits import FREE_LANES, never_billed
from app.models.credits import USD_PER_CREDIT
from app.models.jobs import Job, JobStatus, Usage
from app.providers import STAND_IN

PROVIDERS = {"replicate": "Replicate", "claude": "Claude", "heygen": "HeyGen", "suno": "Suno (KIE)"}
# Voices billed through Replicate, named apart as Reed counts them
MAKERS = {"minimax": "MiniMax", "elevenlabs": "ElevenLabs"}
KINDS = [  # (job kind starts with, what it made), in the order Usage lists them
    ("image", "Stills"),
    ("video", "Takes"),
    ("watch", "Checks and watches"),
    ("speech", "Voice"),
    ("voice", "Voice"),
    ("narration", "Voice"),
    ("music", "Song and music"),
    ("song", "Song and music"),
    ("sound", "Sound effects"),
]
THINKING = "Claude's thinking"  # planning, writing, directing
CHECKS = "Checks and watches"  # Claude's looks at stills, takes and the cut; Gemini's watches
KIND_ORDER = [THINKING, *dict.fromkeys(name for _, name in KINDS), "Other"]


def provider_name(provider: str, model: str | None) -> str:
    """'Replicate', 'Claude', 'MiniMax', …; a test site's real lane counts as its provider."""
    base = provider.removesuffix("-samples")
    found = get_model(model or "")
    maker = found.provider_model.split("/")[0] if found else ""
    if base == "replicate" and maker in MAKERS:
        return MAKERS[maker]
    return PROVIDERS.get(base, "Other")


def kind_name(provider: str, kind: str) -> str:
    if kind == "check-claude":  # take_watch, still_review, watch_cut, item_checks
        return CHECKS
    if provider.startswith("claude") or kind.endswith("-claude"):
        return THINKING
    return next((name for start, name in KINDS if kind.startswith(start)), "Other")


@dataclass
class Charge:
    project_id: int | None
    brand_id: int | None
    by: int | None  # who asked for it
    at: datetime  # the job's own time
    provider: str
    kind: str
    usd: Decimal
    listed: bool  # at list price: the provider gave no figure


def _charge(j, usd: Decimal, listed: bool) -> Charge:
    return Charge(j.project_id, j.brand_id, j.created_by_id, j.created_at,
                  provider_name(j.provider, j.model),
                  kind_name(j.provider, j.kind), Decimal(usd), listed)  # fmt: skip


def charges(db: Session, *where, usage_at=(), job_at=()) -> tuple[list[Charge], bool]:
    """Every charge of the jobs `where` picks, and whether one still running hasn't reported
    yet. `usage_at` picks Usage rows by their own time, `job_at` the jobs with none by theirs.
    Only columns are read, never a job's input (a turn's holds its whole prompt: video 240)."""
    model = Job.input["model"].as_string().label("model")
    cols = (Job.project_id, Job.brand_id, Job.created_by_id, Job.created_at, Job.provider,
            Job.kind, model)  # fmt: skip
    rows = select(*cols, Usage.cost_usd, Usage.estimated).join(Usage, Usage.job_id == Job.id)
    out = [_charge(j, j.cost_usd, j.estimated) for j in db.execute(rows.where(*where, *usage_at))]
    sent = and_(Job.provider_ref.is_not(None), Job.provider_ref.not_like(f"{STAND_IN}%"),
                Job.provider.not_in(FREE_LANES))  # fmt: skip
    none = (~select(Usage.id).where(Usage.job_id == Job.id).exists(),
            or_(Job.status == JobStatus.running, sent))  # fmt: skip
    pending = False
    for j in db.execute(select(*cols, Job.status, Job.error_detail, Job.credits)
                        .where(*where, *job_at, *none)):  # fmt: skip
        if j.status == JobStatus.running:
            pending = True
        elif not never_billed(j):
            out.append(_charge(j, j.credits * USD_PER_CREDIT, True))
    return out, pending


@dataclass
class Split:
    """One figure split by provider and by kind."""

    usd: Decimal
    listed: Decimal  # of it, at list price
    providers: dict[str, list[Decimal]]  # name: [usd, at list price]
    kinds: dict[str, list[Decimal]]


def split(found: list[Charge]) -> Split:
    out = Split(Decimal(0), Decimal(0), {}, {})
    for c in found:
        out.usd += c.usd
        out.listed += c.usd if c.listed else 0
        for part in (out.providers.setdefault(c.provider, [Decimal(0)] * 2),
                     out.kinds.setdefault(c.kind, [Decimal(0)] * 2)):  # fmt: skip
            part[0] += c.usd
            part[1] += c.usd if c.listed else 0
    return out
