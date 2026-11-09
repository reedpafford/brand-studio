"""Video variations (Reed, Runway #2): on a finished video, "Make variations" (2 or 3, of its
hook or its ending) asks the director once for the ideas; each becomes a video beside the
source, "<title> · variation A", keeping its words, cast, looks, stills and every take but
the changed clips'. Each waits on its own direction card, priced as those clips only, and Make
it makes only them. Stand-ins only."""

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


def test_the_owners_quoted_words_are_a_new_version_for_that_variation_only(
        app, db, owner, editor, monkeypatch):  # fmt: skip
    """Rule 31's owner exception: a hook in the owner's own quoted words is a new version of
    the script for that variation; the source and the script keep theirs. An editor's quotes
    change no word."""
    pid = _delivered(app, db, owner, editor, monkeypatch)
    source = db.get(Project, pid)
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
    assert "Line 2 of this video's script" in first.director_chat[0]["text"]


def test_a_place_made_for_the_source_is_its_variations_too(app, db, owner, editor, monkeypatch):
    from app.breakdown import _places
    from app.models.library import Kind, LibraryItem

    pid = _delivered(app, db, owner, editor, monkeypatch)
    source = db.get(Project, pid)
    place = LibraryItem(workspace_id=source.workspace_id, kind=Kind.place, name="The den",
                        owner_project_id=pid)  # fmt: skip
    db.add(place)
    db.commit()
    video = _variations(app, db, owner, pid, count=2)[0]
    assert f"place:{place.id} | The den" in _places(db, video)
