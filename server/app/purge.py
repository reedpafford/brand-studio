"""Housekeeping (gaps #18): scripts deleted over 30 days ago go for good, with their imported
reel's files. Archived scripts (they have videos) and anything a video still uses are never
touched. Safe to run again: what's gone is simply not found. No paid calls.

Run by the worker that prepares reels, at start and once a day; or by hand:
`python -m app.purge`."""

import logging
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import script_library as lib
from app.db import utcnow
from app.models.files import StoredFile
from app.models.script_library import Script, ScriptCastSlot, ScriptDraft, ScriptDraftText
from app.models.scripts import Suggestion
from app.storage import Storage

log = logging.getLogger("purge")
PURGE_AFTER = timedelta(days=30)  # the "Removed for good on" date the list shows
REEL_FILES = ("video_file_id", "contact_file_id", "watch_file_id")


def reel_file_ids(script: Script) -> list[int]:
    reel = script.reel or {}
    ids = [reel.get(k) for k in REEL_FILES] + list(reel.get("grid_file_ids") or [])
    return [i for i in ids if i]


def purge_deleted(db: Session, storage: Storage) -> int:
    """Remove every script deleted before the cut-off; returns how many went."""
    due = db.scalars(
        select(Script).where(
            Script.archived,
            Script.deleted_at.is_not(None),
            Script.deleted_at < utcnow() - PURGE_AFTER,
        )
    ).all()
    gone = 0
    for script in due:
        if lib.has_videos(db, script):  # an archived script: its videos keep it
            continue
        drafts = select(ScriptDraft.id).where(ScriptDraft.script_id == script.id)
        db.execute(delete(Suggestion).where(Suggestion.script_draft_id.in_(drafts)))
        db.execute(delete(ScriptDraftText).where(ScriptDraftText.draft_id.in_(drafts)))
        db.execute(delete(ScriptDraft).where(ScriptDraft.script_id == script.id))
        db.execute(delete(ScriptCastSlot).where(ScriptCastSlot.script_id == script.id))
        for file in db.scalars(select(StoredFile).where(StoredFile.id.in_(reel_file_ids(script)))):
            storage.delete(file.key)
            db.delete(file)
        db.delete(script)
        db.commit()  # one script at a time, so a failure halfway never leaves a half-removed one
        gone += 1
    if gone:
        log.info("Removed %d script(s) deleted over %d days ago.", gone, PURGE_AFTER.days)
    return gone


def main() -> None:  # pragma: no cover - wiring only
    from app.db import make_sessionmaker
    from app.settings import get_settings
    from app.storage import LocalStorage

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    with make_sessionmaker(settings.database_url)() as db:
        print(purge_deleted(db, LocalStorage(settings.storage_dir)), "removed")


if __name__ == "__main__":
    main()
