"""Housekeeping (gaps #18): scripts deleted over 30 days ago go for good with their reel files;
newer deletes and archived scripts (they have videos) stay."""

from datetime import timedelta

from app.db import utcnow
from app.models.files import StoredFile
from app.models.script_library import Script, ScriptDraft
from app.purge import purge_deleted
from tests.conftest import upload
from tests.test_breakdown import BREAKDOWN
from tests.test_script_library import SCRIPT, _make
from tests.test_script_produce import _published


def _deleted(client, db, days_ago: int, script_id: int | None = None) -> int:
    script_id = script_id or _make(client, text=SCRIPT)["id"]
    assert client.delete(f"/scripts/{script_id}").status_code == 204
    db.get(Script, script_id).deleted_at = utcnow() - timedelta(days=days_ago)
    db.commit()
    return script_id


def test_only_scripts_deleted_over_30_days_ago_go_with_their_reel_files(app, owner, editor, db):
    old = _deleted(owner, db, 31)
    files = [upload(owner, "reel.mp4"), upload(owner, "grid.jpg")]
    db.get(Script, old).reel = {"video_file_id": files[0], "grid_file_ids": [files[1]]}
    db.commit()
    keys = [db.get(StoredFile, f).key for f in files]
    recent = _deleted(owner, db, 29)
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    editor.post(f"{base}/drafts/0/produce")  # a video: deleting it archives it
    archived = _deleted(owner, db, 90, int(base.rsplit("/", 1)[1]))

    assert purge_deleted(db, app.state.storage) == 1
    db.expire_all()
    assert db.get(Script, old) is None and not db.query(ScriptDraft).filter_by(script_id=old).all()
    assert [db.get(StoredFile, f) for f in files] == [None, None]
    assert not any(app.state.storage.exists(k) for k in keys)  # off the disk too
    assert db.get(Script, recent) and db.get(Script, archived)  # kept
    assert owner.post(f"/scripts/{recent}/restore").status_code == 200  # still restorable
    assert purge_deleted(db, app.state.storage) == 0  # safe to run again
