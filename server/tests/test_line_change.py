"""The owner changes a published line on a video already made (Reed, 7 Nov: rule 31's owner
exception). S3-14's card offers the owner "Change the line": a new version of the script with
that line changed, and only the clips whose shots carry it made again (their prompts and
takes; a narrated video's narration read again), then the cut and its watch. Every other clip
and take stays. An editor's card is S3-14's. On the stand-ins (no paid call)."""

import copy

from app import director, line_change, locked_line
from app.models.asks import Ask
from app.models.clips import ClipTake, FinalVideo, ProjectClip
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.scripts import ScriptVersion
from tests import test_cast_roles
from tests.conftest import make_cut
from tests.test_breakdown import BREAKDOWN
from tests.test_director import _made, _run
from tests.test_narration import narrated  # noqa: F401

ASK = "Change “bought the dip” to “bought the top”"


def _two_clips(monkeypatch) -> None:
    """The plan the video lands with: Mom's line in clip 1, Nate's in clip 2."""
    bd = copy.deepcopy(BREAKDOWN)
    one, two = bd["scenes"][0]["shots"]
    one["script_lines"], two["script_lines"] = [2], [3]
    bd["clips"] = [{"id": "c1", "shot_ids": ["1.1"], "seconds": 4, "seam": "Nate answers."},
                   {"id": "c2", "shot_ids": ["1.2"], "seconds": 4, "seam": "End."}]  # fmt: skip
    monkeypatch.setattr(test_cast_roles, "BREAKDOWN", bd)


def _delivered(app, db, owner, editor, monkeypatch) -> int:
    _two_clips(monkeypatch)
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    assert editor.get(f"/projects/{pid}/director").json()["status"] == "delivered"
    return pid


def _card(client, pid: int) -> dict:
    return next(a for a in client.get(f"/projects/{pid}/asks").json() if a["kind"] == "instead")


def _takes(db, pid: int) -> dict[str, list[int]]:
    rows = db.query(ProjectClip).filter_by(project_id=pid).all()
    return {r.clip_id: sorted(t.id for t in db.query(ClipTake).filter_by(clip_id=r.id))
            for r in rows}  # fmt: skip


def test_the_owner_changes_a_line_and_only_its_clip_is_made_again(app, db, owner, editor,
                                                                 monkeypatch):  # fmt: skip
    pid = _delivered(app, db, owner, editor, monkeypatch)
    project = db.get(Project, pid)
    was_draft, before = project.script_draft_id, _takes(db, pid)
    cuts = db.query(FinalVideo).filter_by(project_id=pid).count()
    out = owner.post(f"/projects/{pid}/director/messages", json={"text": ASK}).json()
    assert out["status"] == "delivered"  # answered at once: the card
    card = _card(owner, pid)
    assert card["question"] == locked_line.OWNS.format("bought the dip")
    change = card["choices"][0]
    assert (change["title"], change["do"]) == (line_change.TITLE, line_change.DO)
    assert change["why"] == ("A new version of the script says “bought the top” for “bought "
                             "the dip”. Only clip 2 is made again, then the cut")  # fmt: skip
    assert change["price"]["usd"] > 0  # the owner reads dollars, "up to" as every press
    seen = _card(editor, pid)  # an editor's card is S3-14's: no Change the line
    assert line_change.DO not in [c["do"] for c in seen["choices"]]
    assert seen["question"].startswith("The script’s words are set for this script")
    no = editor.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
    assert no.status_code in (403, 409)  # never the editor's press

    pressed = owner.post(f"/asks/{card['id']}/answer", json={"how": "instead", "choice": "A"})
    assert pressed.status_code == 200, pressed.text
    db.expire_all()
    project = db.get(Project, pid)
    newest = db.query(ScriptVersion).filter_by(project_id=pid).order_by(
        ScriptVersion.version.desc()).first()  # fmt: skip
    assert "NATE: I bought the top." in newest.text and newest.source == "owner_line"
    assert project.script_draft_id != was_draft  # a new version of the script for this video
    assert "bought the dip" in db.get(ScriptDraft, was_draft).text  # the script's own stays
    _run(app, db, ticks=80, start=False)  # no start card: the owner's press was the OK
    db.expire_all()
    out = owner.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    after = _takes(db, pid)
    assert after["c1"] == before["c1"]  # every other clip and its takes stay
    assert len(after["c2"]) > len(before["c2"])  # only the line's clip made again
    assert db.query(FinalVideo).filter_by(project_id=pid).count() > cuts  # cut again
    assert _card(owner, pid)["choices"][0]["made"] == "done"
    assert db.query(Ask).filter_by(project_id=pid, kind="start").count() == 1  # no new card
    run = director.turns(db, project)[-1].input[director.RUN]
    assert run["ok"] and run.get(director.REVISION)
    from app.clip_prompts import newest

    shots = [s for sc in newest(db, project).data["scenes"] for s in sc["shots"]]
    assert [s["line"] for s in shots] == ["Nate, where is all your money?", "I bought the top."]


def test_in_a_narrated_video_the_narration_is_read_again_and_only_its_clips_made(
    app,
    db,
    owner,
    editor,
    narrated,  # noqa: F811
):
    """A narrated line: the narration is read again with the new words (its voice kept), the
    shots follow its times, the clips under the other lines keep their takes on the new
    times, and only the changed line's clips are made again."""
    from app.models.songs import SongTake
    from tests.test_narration import _work
    from tests.test_song_final_cut import _clips_made
    from tests.test_song_takes import _approve_plan

    owner.post(f"{narrated}/songs", json={})
    _work(app, db, ticks=8)
    owner.post(f"{narrated}/approve")
    owner.post(f"{narrated.rsplit('/drafts', 1)[0]}/publish")
    video = f"/projects/{owner.post(f'{narrated}/produce').json()['project_id']}"
    _work(app, db)
    _approve_plan(app, db, owner, video)
    _clips_made(app, db, owner, video)
    pid = int(video.rsplit("/", 1)[1])
    assert make_cut(app, db, owner, video).status_code == 200
    project = db.get(Project, pid)
    old_take = db.get(SongTake, project.song_take_id)
    before = _takes(db, pid)
    owner.post(f"{video}/director/messages", json={"text": "Change “a mess” to “a wreck”"})
    card = _card(owner, pid)
    change = next(c for c in card["choices"] if c["do"] == line_change.DO)
    assert "the narration are made again" in change["why"], change["why"]
    pressed = owner.post(f"/asks/{card['id']}/answer",
                         json={"how": "instead", "choice": change["key"]})  # fmt: skip
    assert pressed.status_code == 200, pressed.text
    _run(app, db, ticks=120, start=False)
    db.expire_all()
    project = db.get(Project, pid)
    out = owner.get(f"{video}/director").json()
    assert out["status"] == "delivered", (out["ended"], [t["result"] for t in out["turns"]])
    take = db.get(SongTake, project.song_take_id)
    assert take.id != old_take.id and "a wreck" in take.lyrics and take.voice == old_take.voice
    after = _takes(db, pid)
    redone = {c for c in after if after[c] != before.get(c)}
    assert redone == {"c1"} and after["c1b"] == before["c1b"], (before, after)  # only its clip
    assert _card(owner, pid)["choices"][0]["made"] == "done"
