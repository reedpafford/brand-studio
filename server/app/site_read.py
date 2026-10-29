"""Import from website (flows BR2): read a brand's site, show what was found, save only the
ticked. Two jobs: a free `site_fetch` on our own server (app/site_fetch.py: the page's words,
colours and logo address) and, when it found something, the paid `site_read` call that names
the products and picks the brand's colours (about 3 credits; never more than shown). Failed
reads aren't counted, and a read that finds nothing is set to 0: "Nothing was charged".
What was found waits in the read's own output until Save; nothing is written before."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.enhance import escape
from app.models.accounts import User
from app.models.brands import Brand
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem

KIND = "write-claude"
FAILED = "Couldn't read that site. Nothing was charged."
EMPTY = "Nothing useful on that page. Try the home page."
NO_LOGO = "Couldn't get the logo from the site."
SAVED = "This read is already saved."


def stand_in_logo(url: str) -> tuple[bytes, str]:
    """The practice page's logo (stand-ins): a small PNG; an address with "nologo" fails."""
    import io

    from PIL import Image

    from app.site_fetch import Refused

    if "nologo" in url:
        raise Refused(NO_LOGO)
    out = io.BytesIO()
    Image.new("RGB", (64, 64), "#e4572e").save(out, "PNG")
    return out.getvalue(), "image/png"


def fetch_input(brand: Brand, url: str) -> dict:
    return {"step": "site_fetch", "brand_id": brand.id, "url": url}


def save_fetched(db: Session, job: Job) -> None:
    """The page is in: ask for the products and the brand's colours, unless it had nothing."""
    from app.routes.jobs import enqueue

    page = job.output or {}
    if page.get("problem") or not (page.get("text") or page.get("colours")):
        return  # a refused fetch or an empty page: free, and the read says so
    prompt = "\n".join([
        f"<site>{escape(page.get('url', ''))}</site>",
        f"<title>{escape(page.get('title', ''))}</title>",
        f"<description>{escape(page.get('description', ''))}</description>",
        f"<colours>{' '.join(page.get('colours', []))}</colours>",
        f"<page>\n{escape(page.get('text', ''))}\n</page>",
    ])  # fmt: skip
    data = {"step": "site_read", "brand_id": job.input["brand_id"], "fetch_job_id": job.id,
            "system": prompts.system("site_read"), "prompt": prompt}  # fmt: skip
    try:
        read = enqueue(db, db.get(User, job.created_by_id), KIND, data, provider="claude")
    except HTTPException as no:  # over the cap or the credits: the read stops, uncharged
        job.output = {**page, "read_error": no.detail}
        return
    job.output = {**page, "read_job_id": read.id}


def save_read(db: Session, job: Job) -> None:
    """Keep only colours the page named; nothing found is free (it's charged 0)."""
    page = db.get(Job, job.input["fetch_job_id"]).output or {}
    out = job.output or {}
    colours = [c for c in out.get("colours", []) if c in page.get("colours", [])]
    products = [p for p in out.get("products", []) if p.get("name", "").strip()][:12]
    logo = page.get("logo_url", "") if out.get("logo") else ""
    job.output = {**out, "colours": colours, "products": products, "logo_url": logo}
    if not (colours or products or logo):
        job.credits = 0  # nothing to show, so nothing is charged


def state(db: Session, brand: Brand, fetch: Job) -> dict:
    """{status: reading | done | failed | empty | saved, reason, found}."""
    page = fetch.output or {}
    found = {"logo_url": "", "colours": [], "products": []}
    if fetch.status in (JobStatus.queued, JobStatus.running):
        return {"status": "reading", "reason": "", "found": found}
    if fetch.status != JobStatus.succeeded or page.get("problem") or page.get("read_error"):
        reason = page.get("read_error") or FAILED
        return {"status": "failed", "reason": reason, "found": found}
    if not page.get("read_job_id"):
        return {"status": "empty", "reason": EMPTY, "found": found}
    read = db.get(Job, page["read_job_id"])
    if read.status in (JobStatus.queued, JobStatus.running):
        return {"status": "reading", "reason": "", "found": found}
    if read.status != JobStatus.succeeded:
        return {"status": "failed", "reason": FAILED, "found": found}
    out = read.output or {}
    found = {"logo_url": out.get("logo_url", ""), "colours": out.get("colours", []),
             "products": out.get("products", [])}  # fmt: skip
    if not (found["logo_url"] or found["colours"] or found["products"]):
        return {"status": "empty", "reason": EMPTY, "found": found}
    status = "saved" if page.get("saved") else "done"
    return {"status": status, "reason": "", "found": found}


def products(db: Session, brand: Brand) -> dict[str, LibraryItem]:
    """The brand's products by lower-cased name."""
    from app.models.library import item_brands

    rows = db.scalars(select(LibraryItem).join(item_brands).where(
        item_brands.c.brand_id == brand.id, LibraryItem.kind == Kind.prop,
        LibraryItem.archived.is_(False)))  # fmt: skip
    return {key(i.name): i for i in rows}


def key(name: str) -> str:
    return " ".join(name.split()).lower()
