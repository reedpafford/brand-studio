"""Video variations (Reed, Runway #2): on a finished video, "Make variations" (2 or 3, of its
hook or its ending) asks the director once for the ideas; each becomes a video beside the
source, "<title> · variation A", keeping its words, cast, looks, stills and every take but
the changed clips'. Each waits on its own direction card, priced as those clips only, and Make
it makes only them. Stand-ins only."""

import json

from app import director, video_variations
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.scripts import ScriptVersion
from tests.test_director import _run
from tests.test_line_change import _delivered, _last_job
from tests.test_revision_price import _card, _prices


def _variations(app, db, client, pid, **body) -> list[Project]:
    asked = client.post(f"/projects/{pid}/variations", json=body)
    assert asked.status_code == 201, asked.text
    _run(app, db, ticks=12, start=False)  # its one call, then each run up to its card
    out = client.get(f"/projects/{pid}/variations").json()
    assert out["state"] == "done", out
    return [db.get(Project, v["id"]) for v in out["videos"]]


def _picked(db, pid) -> dict[str, int | None]:
    """Each clip's picked take's file."""
    rows = db.query(ProjectClip).filter_by(project_id=pid).all()
    return {r.clip_id: (db.get(ClipTake, r.picked_take_id).file_id if r.picked_take_id else None)
            for r in rows}  # fmt: skip


def test_three_hooks_are_three_videos_beside_it_each_priced_as_its_first_clip(
        app, db, owner, editor, monkeypatch):  # fmt: skip
    pid = _delivered(app, db, owner, editor, monkeypatch)
    source = db.get(Project, pid)
    whole = _prices(db, pid)[1]
    since = _last_job(db)
    made = _variations(app, db, owner, pid, count=3, part="hook", note="Open on the money.")
    assert [v.name for v in made] == [f"{source.name} · variation {x}" for x in "ABC"]
    assert {v.folder_id for v in made} == {source.folder_id}
    calls = db.query(Job).filter(Job.id > since, Job.input["step"].as_string()
                                 == video_variations.STEP).all()  # fmt: skip
    assert len(calls) == 1 and calls[0].project_id == pid  # one director call proposes them
    kept = _picked(db, pid)
    for v in made:
        assert _picked(db, v.id) == {**kept, "c1": None}  # the same files; clip 1 made again
        steps = {j.input.get("step") for j in db.query(Job).filter(Job.project_id == v.id)}
        assert steps == {"treatment", "review_stills", director.STEP}  # nothing made yet
        held = director.turns(db, v)[-1]  # its direction card, waiting for Make it
        assert held.input[director.RUN].get(director.REVISION) and held.input.get(director.START)
        assert held.status == JobStatus.needs_owner_approval
        up_to = _prices(db, v.id)[1]
        assert 0 < up_to < whole  # its first clip, not the whole video
        assert abs(_card(owner, v.id)["money"]["up_to"]["credits"] - float(up_to)) <= 1
        hook = director.treatment(db, v)["hook"]
        assert hook.startswith("A practice opening") and hook != director.treatment(
            db, source)["hook"]  # fmt: skip


def test_make_it_on_a_variation_makes_only_its_changed_clip(app, db, owner, editor, monkeypatch):
    from tests.test_line_change import _charged

    pid = _delivered(app, db, owner, editor, monkeypatch)
    video = _variations(app, db, editor, pid, count=2, part="ending")[0]
    before = _picked(db, video.id)
    assert before["c2"] is None and before["c1"] == _picked(db, pid)["c1"]  # the ending's clip
    price = _card(editor, video.id)["money"]["up_to"]["credits"]
    since = _last_job(db)
    _run(app, db, ticks=80)  # Make it on its card, then the run
    out = owner.get(f"/projects/{video.id}/director").json()
    assert out["status"] == "delivered", (out["ended"], [t["result"] for t in out["turns"]])
    after = _picked(db, video.id)
    assert after["c1"] == before["c1"] and after["c2"] is not None  # only its clip was made
    takes = db.query(Job).filter(Job.id > since, Job.input["step"].as_string() == "clip_take")
    assert {db.get(ProjectClip, j.input["project_clip_id"]).clip_id for j in takes} == {"c2"}
    assert pid not in {j.project_id for j in takes}  # the source stays as it was
    assert db.query(FinalVideo).filter_by(project_id=video.id).count() == 1
    assert _charged(db, video.id, since) <= price  # never past its card


def test_only_a_delivered_video_with_its_director_idle_gets_variations(app, db, owner, editor,
                                                                      monkeypatch):  # fmt: skip
    from tests.test_director import _made

    pid = _made(app, owner, editor, db)
    no = owner.post(f"/projects/{pid}/variations", json={"count": 2})
    assert (no.status_code, no.json()["detail"]) == (409, video_variations.NOT_DONE)
    pid = _delivered(app, db, owner, editor, monkeypatch)
    assert owner.post(f"/projects/{pid}/variations", json={"count": 2}).status_code == 201
    again = owner.post(f"/projects/{pid}/variations", json={"count": 2})
    assert (again.status_code, again.json()["detail"]) == (409, video_variations.WRITING)
    assert owner.get(f"/projects/{pid}/variations").json()["state"] == "writing"
    turns = len(director.turns(db, db.get(Project, pid)))  # they copy the video as it is: no
    owner.post(f"/projects/{pid}/director/messages", json={"text": "Make clip 1 warmer."})
    assert len(director.turns(db, db.get(Project, pid))) == turns  # new run until they're made
    assert owner.get(f"/projects/{pid}/director").json()["start_blocked"] == (
        video_variations.WRITING)  # fmt: skip
    asked = db.query(Job).filter(Job.input["step"].as_string() == video_variations.STEP).one()
    asked.status = JobStatus.cancelled  # the owner said no: it says so, never "no idea fit"
    db.commit()
    assert owner.get(f"/projects/{pid}/variations").json()["state"] == "declined"


def test_an_idea_that_remakes_every_clip_or_misses_its_end_is_never_made(app, db, owner, editor,
                                                                        monkeypatch):  # fmt: skip
    """A variation keeps the video's clips: an idea naming them all, or a hook that leaves
    the opening clip as it was, isn't one."""
    from app.providers.fake_local import FakeWriter

    pid = _delivered(app, db, owner, editor, monkeypatch)
    ideas = [{"title": t, "direction": "x", "clips": c, "note": "x"} for t, c in
             (("All", ["c1", "c2"]), ("Late", ["c2"]), ("Fits", ["c1"]))]  # fmt: skip
    monkeypatch.setattr(FakeWriter, "_video_variations", lambda self, p: {"variations": ideas})
    made = _variations(app, db, owner, pid, count=3, part="hook")
    assert [v.name.rsplit(" ", 1)[1] for v in made] == ["A"]  # only the one that fits
    assert _picked(db, made[0].id)["c1"] is None


def test_a_variation_in_the_owners_words_reaches_its_shot_and_delivers(app, db, owner, editor,
                                                                      monkeypatch):  # fmt: skip
    """QA on #1491: a line with a note in brackets (#1490) gets the owner's words in its shot
    too, the note kept in the script, and the run says it as Change the line does, so its
    take's note passes the words check and it delivers."""
    from app.clip_prompts import newest

    pid = _delivered(app, db, owner, editor, monkeypatch)
    words = db.query(ScriptVersion).filter_by(project_id=pid).order_by(
        ScriptVersion.version.desc()).first()  # fmt: skip
    words.text = words.text.replace("MOM: Nate,", "MOM: [quietly] Nate,")
    db.commit()
    video = _variations(app, db, owner, pid, count=2, part="hook",
                        note="Open on “Nate, show me the money!”")[0]  # fmt: skip
    text = db.query(ScriptVersion).filter_by(project_id=video.id).order_by(
        ScriptVersion.version.desc()).first().text  # fmt: skip
    assert "MOM: [quietly] Nate, show me the money!" in text
    shots = [s for sc in newest(db, video).data["scenes"] for s in sc["shots"]]
    assert shots[0]["line"] == "Nate, show me the money!"
    assert _card(owner, video.id)["money"]["up_to"]["credits"] > 0  # its clip 1, priced
    since = _last_job(db)
    _run(app, db, ticks=80)
    out = owner.get(f"/projects/{video.id}/director").json()
    assert out["status"] == "delivered", (out["ended"], [t["result"] for t in out["turns"]])
    takes = [json.dumps(j.input) for j in db.query(Job).filter(
        Job.id > since, Job.project_id == video.id,
        Job.input["step"].as_string() == "clip_take")]  # fmt: skip
    assert takes and all("show me the money" in t and "where is all your money" not in t
                         for t in takes)  # its prompt was written again: the new words  # fmt: skip


def test_the_owners_quoted_words_are_a_new_version_for_that_variation_only(
        app, db, owner, editor, monkeypatch):  # fmt: skip
    """Rule 31's owner exception: a hook in the owner's own quoted words is a new version of
    the script for that variation; the source and the script keep theirs. An editor's quotes
    change no word."""
    from app.providers.fake_local import FakeWriter

    pid = _delivered(app, db, owner, editor, monkeypatch)
    source = db.get(Project, pid)
    plain = {"title": "x", "direction": "x", "clips": ["c1"], "note": "x", "line": 2,
             "words": "the money"}  # fmt: skip
    with monkeypatch.context() as m:  # words that aren't in quotes are never the owner's
        m.setattr(FakeWriter, "_video_variations", lambda self, p: {"variations": [plain] * 2})
        unquoted = _variations(app, db, owner, pid, count=2, note="Open on the money.")
    assert {v.script_draft_id for v in unquoted} == {source.script_draft_id}
    _run(app, db, ticks=80)
    note = "Open on “Nate, show me the money!”"
    by_editor = _variations(app, db, editor, pid, count=2, part="hook", note=note)
    assert {v.script_draft_id for v in by_editor} == {source.script_draft_id}
    _run(app, db, ticks=80)  # their runs end, so the source can be varied again
    first, second = _variations(app, db, owner, pid, count=2, part="hook", note=note)
    words = db.query(ScriptVersion).filter_by(project_id=first.id).order_by(
        ScriptVersion.version.desc()).first().text  # fmt: skip
    assert "MOM: Nate, show me the money!" in words and first.script_draft_id != (
        source.script_draft_id)  # fmt: skip
    assert "Nate, where is all your money?" in db.get(ScriptDraft, source.script_draft_id).text
    assert second.script_draft_id == source.script_draft_id  # its idea kept the words
    assert "The owner wrote line 2 of the script again" in first.director_chat[0]["text"]


def test_a_place_made_for_the_first_video_is_every_later_variations_too(
        app, db, owner, editor, monkeypatch):  # fmt: skip
    """A variation of a variation keeps the first video's places, and is named after it:
    "… · variation A1", never "… · variation A · variation A"."""
    from app.breakdown import _places
    from app.models.library import Kind, LibraryItem

    pid = _delivered(app, db, owner, editor, monkeypatch)
    source = db.get(Project, pid)
    place = LibraryItem(workspace_id=source.workspace_id, kind=Kind.place, name="The den",
                        owner_project_id=pid)  # fmt: skip
    db.add(place)
    db.commit()
    first = _variations(app, db, owner, pid, count=2)[0]
    _run(app, db, ticks=80)  # Make it: A and B are delivered
    again = _variations(app, db, owner, first.id, count=2)[0]
    assert again.name == f"{source.name} · variation A1"
    for video in (first, again):
        assert f"place:{place.id} | The den" in _places(db, video)


def test_a_look_its_variations_still_use_isnt_removed_from_the_source(app, db, owner, editor,
                                                                     monkeypatch):  # fmt: skip
    from app.models.library import Kind, LibraryItem

    pid = _delivered(app, db, owner, editor, monkeypatch)
    source = db.get(Project, pid)
    video = _variations(app, db, owner, pid, count=2)[0]
    look = LibraryItem(workspace_id=source.workspace_id, kind=Kind.character, name="Old Mom",
                       owner_project_id=pid)  # fmt: skip
    db.add(look)
    db.flush()
    video.cast_ids = [*video.cast_ids, look.id]  # the source swapped it out; its variation didn't
    db.commit()
    gone = owner.delete(f"/library/character/{look.id}")
    assert gone.status_code == 409
    assert gone.json()["detail"] == (f"Swap the role to another look first: “{video.name}” "
                                     "still uses it.")  # fmt: skip


def test_an_editors_variation_card_and_its_hold_say_one_price(app, db, owner, editor,
                                                             monkeypatch):  # fmt: skip
    """QA on #1491: the hold was priced before the run was a revision (the whole video, up to
    110 credits) beside the card's own up to 88. Both are the variation's own price now."""
    from app import asks

    pid = _delivered(app, db, owner, editor, monkeypatch)
    held_at, start = {}, director.start

    def priced(db_, user, video, **kw):  # the price its hold is worked out from, as it starts
        held_at[video.id] = asks.run_price(db_, video)
        return start(db_, user, video, **kw)

    monkeypatch.setattr(director, "start", priced)
    whole = asks.run_price(db, db.get(Project, pid))
    for video in _variations(app, db, editor, pid, count=2):
        card = _card(editor, video.id)["money"]["up_to"]["credits"]
        assert abs(float(held_at[video.id]) - card) <= 1 and held_at[video.id] < whole


def test_releasing_an_unfinished_variation_keeps_its_sources_hold_on_the_version(
        app, db, owner, editor, monkeypatch):  # fmt: skip
    pid = _delivered(app, db, owner, editor, monkeypatch)
    draft = db.get(ScriptDraft, db.get(Project, pid).script_draft_id)
    holder = draft.reserved_by_id
    video = _variations(app, db, owner, pid, count=2)[0]
    assert owner.post(f"/projects/{video.id}/release").status_code == 200
    db.expire_all()
    assert draft.reserved_by_id == holder and db.get(Project, pid).script_draft_id == draft.id
    assert owner.post(f"/projects/{video.id}/restore").status_code == 200  # Undo still works


def test_an_editors_variations_of_a_freestyle_video_wait_for_the_owner(app, db, owner, editor,
                                                                      monkeypatch):  # fmt: skip
    """QA on #1491 (rule 5): every editor send in Freestyle waits for Reed. Make variations on
    an editor's Freestyle video is held, nothing spent, until the owner's OK runs the ideas
    call; each variation's run then waits on the owner's OK too. Its name is cut at a word."""
    from app import asks
    from app.models.accounts import User
    from app.models.freestyles import Freestyle
    from app.routes.freestyles import HELD
    from tests.test_freestyle_dialogue import BODY
    from tests.test_freestyle_dialogue import _run as fs_run

    monkeypatch.setattr(director, "own_limit", lambda: director.OWN_CREDITS * 2)
    long = "and the chart keeps climbing while everyone at the table laughs at me again, " * 3
    text = "\n".join(f"{who}: {first}, {long}so." for who, first in (  # two clips or more
        ("MIA", "The market opened"), ("LEO", "We were ready"), ("MIA", "It dipped"),
        ("LEO", "We bought")))  # fmt: skip
    made = editor.post("/freestyles", json={**BODY, "text": text}).json()
    fs_run(app, db, ticks=4, start=False)
    (first,) = owner.get("/jobs", params={"status": "needs_owner_approval"}).json()
    assert owner.post(f"/jobs/{first['id']}/approve").status_code == 200
    fs_run(app, db)
    fs = db.get(Freestyle, made["id"])
    title = "A very long title for a freestyle video that goes on and on about the market " * 2
    editor.patch(f"/freestyles/{fs.id}", json={"title": title[:118]})
    pid = fs.project_id
    since = _last_job(db)
    asked = editor.post(f"/projects/{pid}/variations", json={"count": 2, "part": "hook"})
    assert asked.status_code == 201, asked.text
    _run(app, db, ticks=6, start=False)
    assert asked.json()["state"] == "held" and editor.get(  # nothing ran or was charged
        f"/projects/{pid}/variations").json()["state"] == "held"  # fmt: skip
    (ideas,) = db.query(Job).filter(Job.id > since).all()
    assert ideas.status == JobStatus.needs_owner_approval and ideas.input.get("held") == HELD
    assert owner.post(f"/jobs/{ideas.id}/approve").status_code == 200  # the owner's OK
    _run(app, db, ticks=8, start=False)
    videos = [db.get(Project, v["id"]) for v in owner.get(
        f"/projects/{pid}/variations").json()["videos"]]  # fmt: skip
    assert len(videos) == 2
    for video in videos:
        assert director.turns(db, video)[0].input[director.RUN]["hold"] == HELD
        maker = db.get(User, video.created_by_id)
        assert not maker.is_owner and asks.start_hold(db, maker, video) == HELD  # later runs
        stem = video.name.rsplit(" · variation ", 1)[0]
        assert stem.endswith("…") and title.startswith(stem[:-1])  # cut at a word
        assert title[len(stem) - 1] == " "
