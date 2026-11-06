"""S3-14: an editor asks to change a locked line. The published script's words are set, so the
note is answered at once, free and with no model call, with what can change instead, each
priced as its press charges ("up to"; an editor reads credits, the owner dollars). A press makes
it through Make a take's own price and holds, and the cut is made again once it's in. All on
the stand-ins (no paid call)."""

from fastapi.testclient import TestClient

from app import director, locked_line
from app.models.asks import Ask
from app.models.clips import FinalVideo, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from tests.conftest import PASSWORD
from tests.test_director import _made, _run

ASK = "Can we change “bought the dip” to “bought the top”? It feels a bit harsh."


def _delivered(app, db, owner, editor) -> int:
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    assert editor.get(f"/projects/{pid}/director").json()["status"] == "delivered"
    return pid


def _cut(db, pid: int) -> FinalVideo:
    return db.query(FinalVideo).filter_by(project_id=pid).order_by(FinalVideo.id.desc()).first()


def _card(client, pid: int) -> dict:
    return next(a for a in client.get(f"/projects/{pid}/asks").json() if a["kind"] == "instead")


def test_a_note_to_change_the_scripts_words_is_answered_at_once(app, db, owner, editor):
    pid = _delivered(app, db, owner, editor)
    jobs = db.query(Job).count()
    r = editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    assert r.status_code == 201, r.text
    out = r.json()
    assert db.query(Job).count() == jobs  # nothing asked of a model, nothing charged
    assert out["status"] == "delivered" and out["unread"] == 0  # no Make it again waits for it
    said = [t for t in out["thread"] if t["kind"] in ("message", "ask")][-2:]
    assert said[0]["text"] == ASK and said[0]["answered"]
    assert said[1]["kind"] == "ask" and said[1]["who"] == "Director"
    card = _card(editor, pid)
    assert card["question"] == ("The script’s words are set for this script, so I can’t change "
                                "“bought the dip”. Here’s what I can change instead:")  # fmt: skip
    assert card["state"] == "offered" and card["can"] == ["instead"]
    (softer,) = card["choices"]
    assert (softer["title"], softer["do"], softer["made"]) == ("Say it softer", "softer", "")
    assert softer["why"] == "Nate says it more softly. Redo the voice line and clip 1"
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    from app.clip_takes import take_credits
    from app.credits import price

    up_to = price(take_credits(db, db.get(Project, pid), row))
    assert softer["price"] == {"credits": up_to, "usd": None}  # an editor: credits only
    assert _card(owner, pid)["choices"][0]["price"]["usd"] > 0  # the owner: dollars
    assert director.asks.waiting(db, db.get(Project, pid)) == []  # never a question that waits
    needs = owner.get("/needs-you").json()
    assert needs["total"] == 0 and needs["questions"] == []  # nor in Needs you


def test_saying_it_softer_makes_a_new_take_at_its_price_then_the_cut_again(app, db, owner, editor):
    pid = _delivered(app, db, owner, editor)
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    card = _card(editor, pid)
    cut = _cut(db, pid)
    was = (cut.id, list(cut.take_ids))
    pressed = editor.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
    assert pressed.status_code == 200, pressed.text
    choice = pressed.json()["choices"][0]
    assert choice["made"] == "making" and pressed.json()["can"] == []
    job = db.query(Job).filter(Job.kind == "video").order_by(Job.id.desc()).first()
    assert job.input[locked_line.FOR] == card["id"]
    assert job.credits <= choice["price"]["credits"]  # never past the "up to" it showed
    assert locked_line.SOFTER_NOTE in str(job.input)  # how it's said; the words stay
    again = editor.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
    assert again.status_code == 409  # one at a time
    _run(app, db, ticks=10, start=False)
    db.expire_all()
    assert _card(editor, pid)["choices"][0]["made"] == "done"
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    cut = _cut(db, pid)
    assert row.picked_take_id in cut.take_ids and (cut.id, cut.take_ids) != was  # cut again
    assert editor.get(f"/projects/{pid}/director").json()["status"] == "delivered"  # no new run


def test_an_editor_past_the_budget_is_held_for_the_owner(app, db, owner, editor, monkeypatch):
    from decimal import Decimal

    pid = _delivered(app, db, owner, editor)
    monkeypatch.setattr(Project, "budget_credits", property(lambda p: Decimal(1)))  # past it
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    card = _card(editor, pid)
    pressed = editor.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
    assert pressed.status_code == 200, pressed.text
    assert pressed.json()["choices"][0]["made"] == "held"
    held = db.query(Job).filter(Job.kind == "video").order_by(Job.id.desc()).first()
    assert held.status == JobStatus.needs_owner_approval  # S3-06/07: the owner's OK first
    budget = [a for a in owner.get(f"/projects/{pid}/asks").json() if a["kind"] == "budget"]
    assert budget and budget[-1]["state"] == "open"


def test_who_may_press_and_when_nothing_is_offered(app, db, owner, editor):
    pid = _delivered(app, db, owner, editor)
    url = f"/projects/{pid}/director/messages"
    editor.post(url, json={"text": "Make clip 1 slower."})  # not the script's words
    assert editor.get(f"/projects/{pid}/director").json()["unread"] == 1
    db.expire_all()
    db.get(Project, pid).director_chat = []
    db.commit()
    editor.post(url, json={"text": "Can we change “something nobody says”?"})  # not in it
    assert not db.query(Ask).filter_by(project_id=pid, kind="instead").count()
    db.get(Project, pid).director_chat = []
    db.commit()
    editor.post(url, json={"text": ASK})
    card = _card(editor, pid)
    token = owner.post("/team/invites", json={"email": "bo@example.com"}).json()["token"]
    with TestClient(app) as other:  # another editor may read it but not press it
        other.post("/auth/accept-invite", json={"token": token, "name": "Bo", "password": PASSWORD})
        assert _card(other, pid)["can"] == []
        bad = other.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
        assert bad.status_code == 403
    no = editor.post(f"/asks/{card['id']}/answer", json={"how": "choice", "choice": "A"})
    assert no.status_code == 422
    assert owner.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "Z"}
                      ).status_code == 422  # fmt: skip


def test_while_a_run_goes_on_the_director_reads_the_note(app, db, owner, editor):
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    assert not db.query(Ask).filter_by(project_id=pid, kind="instead").count()


def test_nothing_is_offered_where_the_clip_doesnt_carry_the_voice(app, db, owner, editor,
                                                                   monkeypatch):  # fmt: skip
    from app import director_song

    pid = _delivered(app, db, owner, editor)
    monkeypatch.setattr(director_song, "kind", lambda db, project: "narrated")
    out = editor.post(f"/projects/{pid}/director/messages", json={"text": ASK}).json()
    assert out["unread"] == 1  # it waits for the director, as any note does
    assert not db.query(Ask).filter_by(project_id=pid, kind="instead").count()
