"""Songs, narration and music on a script (Producer, 1 Nov; QA on #1067): an editor's paid
press of them outside any video waits for the owner (Hold requests); its writing runs free
as before and the owner's are never held. All on the free stand-ins."""

from app.models.jobs import Job, JobStatus
from app.models.songs import SongTake
from app.routes.jobs import SCRIPT_MEDIA
from tests.test_music import LYRICS
from tests.test_narration import WORDS
from tests.test_song_takes import _style, _work


def _script(client, kind: str, text: str) -> str:
    brand = client.get("/brands").json()[0]["id"]
    made = client.post("/scripts", json={"brand_id": brand, "title": "S", "kind": kind,
                                         "text": text}).json()  # fmt: skip
    return f"/scripts/{made['id']}/drafts/0"


def _held(db) -> list[Job]:
    db.expire_all()
    return db.query(Job).filter_by(status=JobStatus.needs_owner_approval).all()


def test_an_editors_song_takes_wait_for_the_owner_and_the_owners_never_do(app, db, owner, editor):
    app.state.settings.fake_providers = True
    url = _script(editor, "song", LYRICS)
    _style(editor, url, "pop")
    assert editor.post(f"{url}/songs", json={}).status_code == 201
    (held,) = _held(db)
    assert (held.kind, held.input["held"]) == ("music", SCRIPT_MEDIA)
    assert "Reed" not in editor.get(f"/jobs/{held.id}").json()["held"]
    assert editor.post(f"/jobs/{held.id}/cancel").json()["status"] == "cancelled"  # withdrawn
    mine = _script(owner, "song", LYRICS)
    _style(owner, mine, "pop")
    assert owner.post(f"{mine}/songs", json={}).status_code == 201
    assert not _held(db)  # the owner's run


def test_a_narration_waits_then_its_music_follows_and_a_music_retry_waits_again(
    app, db, owner, editor, monkeypatch
):
    app.state.settings.fake_providers = True
    monkeypatch.setattr("app.narration_music.on", lambda db: True)
    url = _script(editor, "narrated", WORDS)
    assert editor.post(f"{url}/songs", json={}).status_code == 201
    (held,) = _held(db)
    assert (held.kind, held.input["held"]) == ("speech", SCRIPT_MEDIA)
    assert owner.post(f"/jobs/{held.id}/approve").json()["status"] == "queued"
    _work(app, db, ticks=8)
    (take,) = editor.get(f"{url}/songs").json()["takes"]
    assert take["status"] == "ready" and take["music_status"] == "ready"  # never held again
    assert not _held(db)

    bed = db.query(Job).filter(Job.kind == "music_bed").one()
    bed.status = "failed"  # as if the music model failed: the bed alone is pressed again
    db.get(SongTake, take["id"]).music_file_id = None
    db.commit()
    assert editor.post(f"/songs/{take['id']}/music-again").status_code == 200
    (again,) = _held(db)
    assert (again.kind, again.input["held"]) == ("music_bed", SCRIPT_MEDIA)
