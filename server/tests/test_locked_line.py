"""S3-14: an editor asks to change a locked line. The published script's words are set, so the
note is answered at once, free and with no model call, with what can change instead, each
priced as its press charges ("up to"; an editor reads credits, the owner dollars). A press makes
it through Make a take's own price and holds, and the cut is made again once it's in. All on
the stand-ins (no paid call)."""

import pytest
from fastapi.testclient import TestClient

from app import director, locked_line
from app.models.asks import Ask
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.providers import get_providers
from app.providers.local import LocalProvider
from app.worker import run_once
from tests.conftest import PASSWORD
from tests.test_director import _made, _run

ASK = "Can we change “bought the dip” to “bought the top”? It feels a bit harsh."


@pytest.fixture(autouse=True)
def checks_on(monkeypatch):
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins


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


def _press(editor, db, pid: int) -> dict:
    card = _card(editor, pid)
    pressed = editor.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
    assert pressed.status_code == 200, pressed.text
    return pressed.json()


def test_saying_it_softer_makes_a_take_and_once_its_watch_is_clean_the_cut_again(
    app, db, owner, editor
):
    pid = _delivered(app, db, owner, editor)
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    card = _card(editor, pid)
    cut = _cut(db, pid)
    was = (cut.id, list(cut.take_ids))
    pressed = _press(editor, db, pid)
    choice = pressed["choices"][0]
    assert choice["made"] == "making" and pressed["can"] == []
    job = db.query(Job).filter(Job.kind == "video").order_by(Job.id.desc()).first()
    assert job.input[locked_line.FOR] == [card["id"], "A"]
    assert job.credits <= choice["price"]["credits"]  # never past the "up to" it showed
    assert locked_line.SOFTER_NOTE in str(job.input)  # how it's said; the words stay
    again = editor.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
    assert again.status_code == 409  # one at a time
    providers = get_providers(app.state.settings, app.state.storage)
    seen = []
    for _ in range(12):
        run_once(db, providers, app.state.storage)
        db.expire_all()
        seen.append(_card(editor, pid)["choices"][0]["made"])
    assert seen.index("watching") < seen.index("done")  # its watch first (rule 35)
    done = _card(editor, pid)["choices"][0]
    assert done["said"] == "Made and watched. Making Cut 2 with it."  # after its Cut 1
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    cut = _cut(db, pid)
    assert row.picked_take_id in cut.take_ids and (cut.id, cut.take_ids) != was  # cut again
    assert db.get(ClipTake, row.picked_take_id).watch["action"] == "keep"
    assert editor.get(f"/projects/{pid}/director").json()["status"] == "delivered"  # no new run


def test_a_take_its_watch_doesnt_pass_leaves_the_cut_and_says_why(app, db, owner, editor,
                                                                   monkeypatch):  # fmt: skip
    from app import take_watch

    real = take_watch.save

    def flagged(db_, job):
        real(db_, job)
        take = db_.get(ClipTake, job.input["take_id"])
        take.watch = {**take.watch, "action": "flagged",
                      "did": "Flagged for you: the fix would change what's said"}  # fmt: skip

    pid = _delivered(app, db, owner, editor)
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    was = _cut(db, pid).id
    monkeypatch.setattr(take_watch, "save", flagged)
    _press(editor, db, pid)
    _run(app, db, ticks=12, start=False)
    db.expire_all()
    c = _card(editor, pid)["choices"][0]
    assert c["made"] == "kept" and _cut(db, pid).id == was  # the cut stays as it was
    assert c["said"] == ("Made. Flagged for you: the fix would change what's said. The cut stays "
                         "as it was; look at clip 1 in Clips, then make the cut.")  # fmt: skip


def test_a_cut_that_cant_be_made_again_says_why(app, db, owner, editor, monkeypatch):
    from fastapi import HTTPException

    from app.routes import cut

    pid = _delivered(app, db, owner, editor)
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})

    def refused(**_):
        raise HTTPException(409, "The music file stops at 0:41.")

    monkeypatch.setattr(cut, "make", refused)
    _press(editor, db, pid)
    _run(app, db, ticks=12, start=False)
    db.expire_all()
    c = _card(editor, pid)["choices"][0]
    assert c["made"] == "kept"
    assert c["said"] == ("Made and watched, but the cut wasn’t made again: The music file stops "
                         "at 0:41. Make the cut from the Cut tab once that’s done.")  # fmt: skip


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
    db.expire_all()
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


NOT_ASKS = [  # notes that quote the words but don't ask to change them (QA on e17e902f)
    "When he says “bought the dip”, cut to the close-up",
    "Use a wider shot when he says “bought the dip”",
    "Drop the music under “bought the dip”",
    "Instead of the close-up on “bought the dip”, show the chart",
    "Can you say “bought the dip” louder?",
    "Swap the B-roll on “bought the dip” for the trading screen",
    "Remove the stray sound after “bought the dip”",
    "Make “bought the dip” land harder and hold on the face after “the”",
    "Change “bough” to “branch”",  # not the script's words as a whole word
    "Change “bought the dip” to a close-up",  # pictures: no quoted replacement (QA on 9a5862df)
    "Swap “bought the dip” for a reaction shot",
    "Switch “bought the dip” to slow motion",
    "Replace “bought the dip” with B-roll of the chart",
    "Change “bought the dip” to the wide shot please",
    "Can we change the line “bought the dip” to a cutaway?",
]
ASKS = [
    "Can we change “bought the dip” to “bought the top”?",
    "Swap the words “bought the dip” for “bought more”, please",
    "Reword “bought the dip”",
    "Say “bought the top” instead of “bought the dip”",
    "Could it be 'bought the top' instead of 'bought the dip'?",
]


def test_only_a_note_that_asks_to_replace_the_words_is_answered():
    from tests.test_script_library import SCRIPT

    for text in NOT_ASKS:
        assert locked_line.asked(text, SCRIPT) is None, text
    for text in ASKS:
        assert locked_line.asked(text, SCRIPT) == ("bought the dip", True), text
    for more in (
        "Change “bought the dip” to “bought the top”, and make the end brighter.",
        "Change “bought the dip” to “bought more”. Also the logo at the end is blurry",
        "Change “bought the dip” to “bought more” and the ending feels slow",
    ):
        assert locked_line.asked(more, SCRIPT) == ("bought the dip", False), more
    assert locked_line.asked(
        "Change “bought the dip” to “bought more”. It sounds too harsh.", SCRIPT
    ) == ("bought the dip", True)  # a bare verdict on those words
    for other in (
        "It's too dark at the end.",
        "It is too loud overall.",  # QA on 234cde64
        "This is too slow in the middle.",
        "That's fine but the ending drags.",
        "Because the music is too loud.",
        "It might work better with a close-up.",
    ):
        said = f"Change “bought the dip” to “bought more”. {other}"
        assert locked_line.asked(said, SCRIPT) == ("bought the dip", False), other


def test_a_note_that_asks_more_keeps_the_rest_for_the_director(app, db, owner, editor):
    pid = _delivered(app, db, owner, editor)
    text = "Change “bought the dip” to “bought the top”, and make the end brighter."
    out = editor.post(f"/projects/{pid}/director/messages", json={"text": text}).json()
    assert _card(editor, pid)["choices"]  # what can change instead of the words, at once
    assert out["unread"] == 1  # the rest waits for the next Make it, as any note does
    note = next(t for t in out["thread"] if t["kind"] == "message" and t["text"] == text)
    assert note["answered"] is False


def test_false_positives_drop_nothing(app, db, owner, editor):
    pid = _delivered(app, db, owner, editor)
    for text in NOT_ASKS[:3]:
        db.expire_all()
        db.get(Project, pid).director_chat = []
        db.commit()
        out = editor.post(f"/projects/{pid}/director/messages", json={"text": text}).json()
        assert out["unread"] == 1, text
    assert not db.query(Ask).filter_by(project_id=pid, kind="instead").count()


def test_only_where_the_words_are_set_and_only_while_it_can_be_made(app, db, owner, editor):
    pid = _delivered(app, db, owner, editor)
    project = db.get(Project, pid)
    draft, project.script_draft_id = project.script_draft_id, None  # not a published script's
    db.commit()
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    assert not db.query(Ask).filter_by(project_id=pid, kind="instead").count()
    db.expire_all()
    project = db.get(Project, pid)
    project.script_draft_id, project.director_chat = draft, []
    db.commit()
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    card = _card(editor, pid)
    assert editor.post(f"/projects/{pid}/director").status_code == 201  # a run starts
    going = _card(editor, pid)
    assert going["can"] == [] and going["choices"][0]["cannot"] == locked_line.RUNNING
    no = editor.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
    assert (no.status_code, no.json()["detail"]) == (409, locked_line.RUNNING)
    editor.post(f"/projects/{pid}/director/stop")
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    row.clip_id = "c9"  # its clip isn't in the video any more
    db.commit()
    gone = _card(editor, pid)["choices"][0]
    assert gone["cannot"] == "Clip 1 isn't in this video any more." and gone["price"] is None
    no = editor.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
    assert (no.status_code, no.json()["detail"]) == (409, "Clip 1 isn't in this video any more.")


def _landed(app, db, editor, pid: int, ticks=12) -> dict:
    providers = get_providers(app.state.settings, app.state.storage)
    for _ in range(ticks):
        run_once(db, providers, app.state.storage)
        db.expire_all()
    return _card(editor, pid)["choices"][0]


def test_a_take_nobody_watched_offers_use_it_and_make_the_cut(app, db, owner, editor,
                                                               monkeypatch):  # fmt: skip
    """Rule 22: the take's watch was skipped (at the budget): one free press on the card uses
    it (the person's OK, rule 21) and makes the cut."""
    from app import take_watch

    pid = _delivered(app, db, owner, editor)
    monkeypatch.setattr(take_watch, "on", lambda: False)  # as when it's skipped
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    was = _cut(db, pid).id
    _press(editor, db, pid)
    c = _landed(app, db, editor, pid)
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    n = db.get(ClipTake, row.picked_take_id).number
    assert c["made"] == "kept" and _cut(db, pid).id == was
    assert c["then"] == f"Use take {n} and make the cut"
    card = _card(editor, pid)
    assert card["can"] == ["instead"]
    used = editor.post(f"/asks/{card['id']}/answer",
                       json={"how": "instead", "choice": "A", "option": "use"})  # fmt: skip
    assert used.status_code == 200, used.text
    done = used.json()["choices"][0]
    number = _cut(db, pid).number + 1
    assert done["made"] == "done" and done["said"] == (
        f"Take {n} is used. Making Cut {number} with it.")  # fmt: skip
    run_once(db, {"local": LocalProvider(app.state.storage)}, app.state.storage, only={"local"})
    db.expire_all()
    assert _cut(db, pid).id != was and _cut(db, pid).number == number and done["then"] == ""


def test_a_remake_that_wasnt_made_never_leaves_the_card_waiting(app, db, owner, editor,
                                                                 monkeypatch):  # fmt: skip
    """Its watch found a fault and asked for a remake that never came (it failed, or the owner
    declined it): the card says so, points to Clips (no press on a faulty take) and stops
    waiting."""
    from app import take_watch

    real = take_watch.save

    def remade(db_, job):
        real(db_, job)
        take = db_.get(ClipTake, job.input["take_id"])
        take.watch = {**take.watch, "action": "redo", "did": "Remade it."}

    pid = _delivered(app, db, owner, editor)
    monkeypatch.setattr(take_watch, "save", remade)
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    _press(editor, db, pid)
    c = _landed(app, db, editor, pid)
    assert c["made"] == "kept" and c["then"] == ""
    assert "Its remake wasn’t made" in c["said"] and "in Clips" in c["said"]


def test_a_watch_that_never_finished_offers_the_free_press(app, db, owner, editor, monkeypatch):
    from app import take_watch

    pid = _delivered(app, db, owner, editor)
    monkeypatch.setattr(take_watch, "save", lambda db_, job: None)  # its look never reports
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    _press(editor, db, pid)
    c = _landed(app, db, editor, pid)
    assert c["made"] == "kept" and c["then"].startswith("Use take ")
    assert "its watch didn’t finish" in c["said"]


def test_a_take_that_went_since_is_never_offered_or_used(app, db, owner, editor, monkeypatch):
    """QA on 234cde64: the card offered Use take N, then a new plan dropped the clip and its
    takes. The cards still read, the press is gone and says why, and pressing it is refused."""
    from app import take_watch

    pid = _delivered(app, db, owner, editor)
    monkeypatch.setattr(take_watch, "on", lambda: False)
    editor.post(f"/projects/{pid}/director/messages", json={"text": ASK})
    _press(editor, db, pid)
    assert _landed(app, db, editor, pid)["then"].startswith("Use take ")
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    row.picked_take_id = None
    db.flush()
    db.query(ClipTake).filter_by(clip_id=row.id).delete()
    db.delete(row)
    db.commit()
    assert editor.get(f"/projects/{pid}/asks").status_code == 200
    card = _card(editor, pid)
    c = card["choices"][0]
    assert c["then"] == "" and locked_line.GONE in c["said"]
    no = editor.post(f"/asks/{card['id']}/answer",
                     json={"how": "instead", "choice": "A", "option": "use"})  # fmt: skip
    assert no.status_code == 409 and no.json()["detail"].endswith(locked_line.GONE)
    bad = editor.post(f"/asks/{card['id']}/answer",
                      json={"how": "instead", "choice": "A", "option": "other"})  # fmt: skip
    assert bad.status_code == 422


def test_the_cut_isnt_made_over_a_pick_someone_made_since(app, db, owner, editor):
    pid = _delivered(app, db, owner, editor)
    row = db.query(ProjectClip).filter_by(project_id=pid, clip_id="c1").one()
    take = db.get(ClipTake, row.picked_take_id)
    other = ClipTake(clip_id=row.id, number=take.number + 1, job_id=take.job_id,
                     file_id=take.file_id, prompt=take.prompt)  # fmt: skip
    db.add(other)
    db.flush()
    row.picked_take_id = other.id  # someone picked another take since
    db.commit()
    said, cut = locked_line._cut(db, db.get(Project, pid), take, app.state.storage)
    assert not cut and said == ("Made and watched, but clip 1 now uses another take, so the cut "
                                "stays as it was.")  # fmt: skip
