"""A language's sample test (flows VS1, Reed 2026-10-29, owner only): "Test Spanish" writes
one short script for a brand in that language (one Claude call), the owner reads it and
approves it, which switches the language on for editors, or rejects it and tests again. The
newest test is on the language's switch (language_switches.sample_job_id, n14). On the test
site the test is a stand-in, unless real ones are switched on (`lane`)."""

import logging
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import languages
from app.credits import estimate, test_budget_fits
from app.enhance import escape
from app.models.accounts import User
from app.models.brands import Brand
from app.models.jobs import Job, JobStatus
from app.models.languages import LanguageSwitch
from app.models.projects import Project
from app.prompts.schemas import ScriptDrafts
from app.providers import REAL_TESTS

log = logging.getLogger(__name__)

STEP, KIND, SECONDS = "language_sample", "write-claude", 15
WAITING = (JobStatus.queued, JobStatus.running, JobStatus.needs_owner_approval)
ENGLISH = "English is always on: it needs no test."
ALREADY = "This language's test is already being written."
NO_SAMPLE = "Test it first: a language is switched on only once its sample is read and approved."
REAL_NOTE = "Test site: this test is written for real."
USED_UP = ("Test site: the budget for real language tests is used up, so this test will be a "
           "stand-in (a placeholder line). Raise the budget to write real ones.")  # fmt: skip


def job_input(db: Session, brand: Brand, language: str) -> dict:
    """The script writer's rules and the brand, asked for one short script in the language."""
    from app.enhance import project_context

    project = Project(workspace_id=brand.workspace_id, brand_id=brand.id, name="Language test",
                      goal=f"A short {brand.name} ad, to test writing in "
                           f"{languages.name(language)}.",
                      planned_seconds=SECONDS, aspect_ratio="9:16", cast_ids=[],
                      product_variants={}, slot_cast={})  # fmt: skip
    system, context = project_context(db, project, STEP)
    prompt = f"{context}\n<language>{escape(languages.name(language))}</language>"
    return {"step": STEP, "language": language, "brand_id": brand.id, "system": system,
            "prompt": prompt}  # fmt: skip


def price(db: Session, ws: int) -> Decimal:
    return estimate(db, ws, KIND, Decimal(1))


def lane(db: Session, settings, credits: Decimal) -> str:
    """Claude's (real on live, a stand-in on the test site), or the test site's real lane
    while real tests are on and this one still fits their budget. The switch alone decides
    here: the key is only the Claude worker's, and the deploy writes the switch only with it."""
    if not (settings.fake_providers and settings.real_language_samples):
        return "claude"
    if not test_budget_fits(db, REAL_TESTS, settings.language_samples_budget_usd, credits):
        log.warning("Real language tests stopped at the test budget: this one is a stand-in.")
        return "claude"
    return REAL_TESTS


def test_site_note(db: Session, settings, ws: int) -> str | None:
    """Said before the press while real tests are on (the test site)."""
    if not (settings.fake_providers and settings.real_language_samples):
        return None
    fits = test_budget_fits(db, REAL_TESTS, settings.language_samples_budget_usd, price(db, ws))
    return REAL_NOTE if fits else USED_UP


def _job(db: Session, row: LanguageSwitch | None) -> Job | None:
    return db.get(Job, row.sample_job_id) if row and row.sample_job_id else None


def state(db: Session, ws: int, language: str) -> tuple[str, str | None, str | None]:
    """(none | making | ready | rejected | failed, the script's words, a plain reason)."""
    row = languages.switch(db, ws, language)
    job = _job(db, row)
    if job is None:
        return "none", None, None
    if job.status in WAITING:
        return "making", None, None
    if job.status != JobStatus.succeeded:
        return "failed", None, "The test didn't finish. Nothing was charged for it."
    text = ScriptDrafts.model_validate(job.output).drafts[0].script
    return ("rejected" if row.rejected else "ready"), text, None


def switch_row(db: Session, ws: int, language: str) -> LanguageSwitch:
    row = languages.switch(db, ws, language)
    if row is None:
        row = LanguageSwitch(workspace_id=ws, language_id=language)
        db.add(row)
    return row


def make(db: Session, owner: User, language: str, brand: Brand, settings) -> None:
    """Test <language>: one short script written in it, for this brand. Again replaces it."""
    from app.routes.jobs import enqueue

    ws = owner.workspace_id
    if languages.check(language) == languages.DEFAULT:
        raise HTTPException(409, ENGLISH)
    if state(db, ws, language)[0] == "making":
        raise HTTPException(409, ALREADY)
    on = lane(db, settings, price(db, ws))
    job = enqueue(db, owner, KIND, job_input(db, brand, language), provider=on)
    row = switch_row(db, ws, language)
    row.sample_job_id, row.rejected = job.id, False
    db.commit()


def reject(db: Session, owner: User, language: str, rejected: bool) -> None:
    """Reject the sample (the language goes or stays off; Test again writes a new one), or
    Undo that (on again if it was on)."""
    if state(db, owner.workspace_id, language)[0] not in ("ready", "rejected"):
        raise HTTPException(409, NO_SAMPLE)
    row = switch_row(db, owner.workspace_id, language)
    if rejected and not row.rejected:
        row.was_on, row.on = languages.is_on(db, owner.workspace_id, language), False
    elif not rejected and row.rejected:
        row.on = row.was_on  # Undo: as it was before the Reject
    row.rejected = rejected
    db.commit()


def ready(db: Session, ws: int, language: str) -> bool:
    """Approved for switching on: a written, unrejected sample."""
    return state(db, ws, language)[0] == "ready"
