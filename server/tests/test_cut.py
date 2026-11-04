"""The cut editor (app/cut.py, cut_edits.py, cut_render.py; v6 S7-01 to S7-07, S3-12, P-12):
numbered cuts made on the worker while the one before plays, a timeline the edits replay over,
each edit with its own Undo, and a failed cut's one-click fix. Free, on the stand-ins."""

import subprocess
from datetime import timedelta

import pytest

from app import cut, cut_edits, cut_render
from app.models.clips import FinalVideo
from app.models.files import StoredFile
from app.models.projects import Project
from app.models.songs import SongTake
from app.providers.local import LocalProvider
from app.routes.cut import SAME_AGAIN
from app.worker import run_once
from tests.conftest import make_cut
from tests.helpers import assert_hidden
from tests.test_cut_in import _seconds, approved  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_freestyle_dialogue import _run
from tests.test_freestyle_song import NARRATION, _sent
from tests.test_host import _video


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def _tone(seconds: float) -> bytes:
    return subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",  # noqa: S603, S607
                           f"sine=d={seconds}", "-f", "mp3", "-"],
                          capture_output=True, check=True).stdout  # fmt: skip


@pytest.fixture
def presenter(app, db, owner):
    """A presenter video the director delivered (narration, host, its cuts), with a music bed
    under the narration."""
    fs = _sent(owner, "presenter", NARRATION)
    _run(app, db, ticks=160)
    assert owner.get(f"/freestyles/{fs['id']}").json()["status"] == "delivered"
    video = _video(db, fs)
    voice = db.get(SongTake, video.song_take_id)
    key = f"{video.workspace_id}/bed"
    app.state.storage.put(key, _tone(20))
    bed = StoredFile(workspace_id=video.workspace_id, key=key, filename="bed.mp3",
                     content_type="audio/mpeg", size=1, sha256="0" * 64)  # fmt: skip
    db.add(bed)
    db.flush()
    voice.music_file_id = bed.id
    db.commit()
    return f"/projects/{video.id}"


def _local(app, db):
    run_once(db, {"local": LocalProvider(app.state.storage)}, app.state.storage, only={"local"})
    db.expire_all()


def _edit(client, base, **body):
    return client.post(f"{base}/cut/edits", json=body)


def test_the_cut_reads_as_its_timeline(owner, presenter):
    got = owner.get(f"{presenter}/cut").json()
    tl = got["timeline"]
    n = got["number"]  # the director cut, watched and cut again
    assert (got["changes"], got["edits"], got["making"]) == (0, [], None)
    assert got["sound_usd"] > 0  # the owner sees "up to $0.01"
    assert [v["number"] for v in got["versions"]] == list(range(1, n + 1))
    assert not got["out_of_date"]
    assert tl["mode"] == "narrated" and tl["pieces"][0]["start"] == 0
    assert all(a["end"] == b["start"] for a, b in zip(tl["pieces"], tl["pieces"][1:], strict=False))
    assert tl["pieces"][-1]["end"] == tl["length"] and tl["words"]
    assert tl["voice"]["label"].endswith("’s voice") and NARRATION.split()[0] in tl["voice"]["text"]
    assert (tl["music"]["quieter_db"], tl["music"]["gaps"], tl["music"]["loop"]) == (
        18,
        "rise",
        True,
    )
    spans = tl["presenter"]["spans"]
    assert spans[0]["start"] == 0 and spans[-1]["end"] == tl["length"]
    assert {s["size"] for s in spans} == {"medium"} and not any(s["hidden"] for s in spans)
    assert all(p["said"] for p in tl["pieces"])  # the words heard over each piece


def test_each_edit_has_its_undo_and_puts_the_cut_out_of_date(owner, presenter):
    tl = owner.get(f"{presenter}/cut").json()["timeline"]
    first, last = tl["pieces"][0], tl["pieces"][-1]
    made = _edit(owner, presenter, kind="presenter", piece=first["id"], side="left")
    assert made.status_code == 201, made.text
    got = made.json()
    name = tl["presenter"]["name"]
    assert got["edits"][0]["said"] == f"{name} moved left" and got["edits"][0]["at"] == 0
    assert got["changes"] == 1 and got["out_of_date"] and got["can_undo"]
    assert got["timeline"]["presenter"]["spans"][0]["side"] == "left"
    edit_id = got["edits"][0]["id"]
    music = _edit(owner, presenter, kind="music", quieter_db=6).json()
    assert music["timeline"]["music"]["quieter_db"] == 6 and music["changes"] == 2
    back = owner.post(f"{presenter}/cut/edits/{edit_id}/undo").json()  # the first, by name
    assert back["timeline"]["presenter"]["spans"][0]["side"] == "right"
    assert back["timeline"]["music"]["quieter_db"] == 6 and back["changes"] == 1
    assert [e["undone"] for e in back["edits"]] == [True, False] and back["can_redo"]
    owner.post(f"{presenter}/cut/undo")  # the newest
    redone = owner.post(f"{presenter}/cut/redo").json()
    assert redone["timeline"]["music"]["quieter_db"] == 6
    early = _edit(owner, presenter, kind="trim", piece=last["id"], end=0.5)
    assert early.status_code == 422 and "before the last word" in early.json()["detail"]
    nowhere = _edit(owner, presenter, kind="retime", piece="c99")
    assert (nowhere.status_code, nowhere.json()["detail"]) == (
        422,
        "There's no clip 99 in the cut.",
    )
    gone = owner.post(f"{presenter}/cut/undo-all").json()
    assert gone["changes"] == 0 and not gone["out_of_date"] and gone["can_redo"]
    back = owner.post(f"{presenter}/cut/redo").json()  # what Undo all took (the first was
    assert [e["undone"] for e in back["edits"]] == [True, False]  # undone by hand before it)


def test_split_retime_swap_and_trim_move_the_pieces(owner, presenter):
    tl = owner.get(f"{presenter}/cut").json()["timeline"]
    a = tl["pieces"][0]
    mid = round((a["start"] + a["end"]) / 2, 2)
    split = _edit(owner, presenter, kind="split", at=mid).json()
    one, two = split["timeline"]["pieces"][:2]
    assert (one["end"], two["start"], two["clip_id"]) == (mid, mid, a["clip_id"])
    assert two["id"].startswith(f"{a['id']}.") and two["in_point"] == round(mid - a["start"], 2)
    assert split["edits"][-1]["said"] == f"Clip {a['id'][1:]} split at 0:0{int(mid)}"
    if len(tl["pieces"]) > 1:
        other = tl["pieces"][1]
        swapped = _edit(owner, presenter, kind="swap", piece=two["id"], take_id=other["take_id"])
        piece = swapped.json()["timeline"]["pieces"][1]
        assert (piece["take_id"], piece["source"], piece["changed"]) == (
            other["take_id"], f"Clip {other['id'][1:]}", True)  # fmt: skip
        kinds = {s["kind"] for s in owner.get(f"{presenter}/cut/swaps/{two['id']}").json()}
        assert {"in_cut", "clip"} <= kinds
        b = tl["pieces"][1]
        moved = _edit(owner, presenter, kind="trim", piece=b["id"], start=b["start"] + 0.2)
        pieces = moved.json()["timeline"]["pieces"]
        assert pieces[1]["end"] == pieces[2]["start"] == round(b["start"] + 0.2, 2)  # shared edge
    retimed = _edit(owner, presenter, kind="retime", piece=tl["pieces"][-1]["id"]).json()
    assert retimed["edits"][-1]["said"].endswith("re-timed to the words")
    undone = owner.post(f"{presenter}/cut/edits/{split['edits'][-1]['id']}/undo").json()
    if len(tl["pieces"]) > 1:
        assert any(not e["applies"] for e in undone["edits"])
    else:  # the re-timed first half would become the ending, before the last word: refused
        assert undone["detail"].startswith("The cut can't end before the last word")


def test_the_next_cut_is_made_while_the_one_before_plays(app, db, owner, presenter):
    n = owner.get(f"{presenter}/cut").json()["number"]
    _edit(owner, presenter, kind="music", gaps="down")
    asked = owner.post(f"{presenter}/cut")
    assert asked.status_code == 202, asked.text
    got = asked.json()
    assert (got["number"], got["making"]["number"], got["making"]["changes"]) == (n, n + 1, 1)
    assert got["making"]["percent"] == 0 and got["making"]["about_seconds"] >= 5
    assert got["making"]["doing"].startswith("laying ") and "music under the voice" in got[
        "making"]["doing"]  # fmt: skip
    assert owner.post(f"{presenter}/cut").json()["detail"] == cut.MAKING.format(n + 1)
    _local(app, db)
    done = owner.get(f"{presenter}/cut").json()
    assert (done["number"], done["making"], done["changes"], done["out_of_date"]) == (
        n + 1, None, 0, False)  # fmt: skip
    assert len(done["versions"]) == n + 1 and done["edits"][0]["in_cut"]
    data = owner.get(f"/files/{done['file_id']}").content
    assert abs(_seconds(data) - done["timeline"]["length"]) < 0.3
    assert owner.get(f"{presenter}/video").json()["number"] == n + 1


def test_music_that_stops_early_fails_with_one_click_fixes(app, db, owner, presenter):
    project = db.get(Project, int(presenter.rsplit("/", 1)[1]))
    bed = db.get(StoredFile, db.get(SongTake, project.song_take_id).music_file_id)
    app.state.storage.put(bed.key, _tone(1))  # a 1 s bed
    n = owner.get(f"{presenter}/cut").json()["number"]
    _edit(owner, presenter, kind="music", loop=False)
    owner.post(f"{presenter}/cut")
    _local(app, db)
    failed = owner.get(f"{presenter}/cut").json()
    assert failed["number"] == n and failed["making"] is None
    assert failed["failed"]["why"].startswith(
        f"Cut {n + 1} couldn't be made: the music file stops at 0:01, and the cut runs to 0:07"
    )
    assert failed["failed"]["why"].endswith("Nothing was charged.")
    assert failed["failed"]["fixes"] == ["loop_music", "remove_music"]
    again = owner.post(f"{presenter}/cut")  # nothing changed: it would fail the same way
    assert again.status_code == 409 and again.json()["detail"].endswith(SAME_AGAIN)
    fixed = owner.post(f"{presenter}/cut/fix", json={"fix": "loop_music"})
    assert fixed.status_code == 202 and fixed.json()["timeline"]["music"]["loop"] is True
    _local(app, db)
    done = owner.get(f"{presenter}/cut").json()
    assert (done["number"], done["failed"]) == (n + 1, None)


def test_a_story_cut_trims_and_ripples_and_never_cuts_a_word(
    app,
    db,
    editor,
    approved,  # noqa: F811
    monkeypatch,
):
    from types import SimpleNamespace

    from app import cut_edits

    base, _ = approved
    first = make_cut(app, db, editor, base).json()
    got = editor.get(f"{base}/cut").json()
    (piece,) = got["timeline"]["pieces"]
    assert got["timeline"]["mode"] == "takes" and got["number"] == first["number"] == 1
    monkeypatch.setattr(cut_edits, "_speaks", lambda db, take: True)  # a take that talks
    unheard = _edit(editor, base, kind="trim", piece=piece["id"], start=0.2, end=0.8)
    assert (unheard.status_code, unheard.json()["detail"]) == (422, cut_edits.UNHEARD)
    monkeypatch.setattr(
        "app.item_checks.latest",
        lambda db, target, ids: {i: SimpleNamespace(status="done", job_id=None) for i in ids},
    )
    monkeypatch.setattr(cut_edits, "_heard", lambda db, take: [
        {"word": "Get", "start": 0.3, "end": 0.5}])  # fmt: skip
    cuts = _edit(editor, base, kind="trim", piece=piece["id"], start=0.4)
    assert (cuts.status_code, cuts.json()["detail"]) == (
        422, "Clip 1 would lose the word “Get”. Every spoken word stays.")  # fmt: skip
    trimmed = _edit(editor, base, kind="trim", piece=piece["id"], start=0.2, end=0.8).json()
    (piece,) = trimmed["timeline"]["pieces"]
    assert (piece["start"], piece["end"], piece["in_point"]) == (0, 0.6, 0.2)
    assert make_cut(app, db, editor, base).json()["number"] == 2
    made = db.query(FinalVideo).order_by(FinalVideo.id.desc()).first()
    assert abs(_seconds(editor.get(f"/files/{made.file_id}").content) - 0.6) < 0.15
    retime = _edit(editor, base, kind="retime", piece=piece["id"]).json()  # onto "Get"
    (piece,) = retime["timeline"]["pieces"]
    assert (piece["in_point"], piece["end"]) == (0.15, 0.65)  # 0.15 s before it, 0.15 after
    assert _edit(editor, base, kind="presenter", side="left").json()["detail"] == cut.NO_HOST
    assert _edit(editor, base, kind="music", quieter_db=6).json()["detail"] == cut.NO_MUSIC
    assert _edit(editor, base, kind="split").json()["detail"] == cut_edits.SAY["split"]
    shown = editor.get(f"{base}/cut").json()  # an editor sees credits, never dollars
    assert shown["sound_credits"] > 0 and shown["sound_usd"] is None
    # the take now also says "now" at 0.9 s, past the trim (as a new pick would): no word is lost
    words = [{"word": "Get", "start": 0.3, "end": 0.5}, {"word": "now", "start": 0.9, "end": 1.0}]
    monkeypatch.setattr(cut_edits, "_heard", lambda db, take: words)
    lost = editor.post(f"{base}/cut")
    assert lost.status_code == 409 and "would lose the word “now”" in lost.json()["detail"]
    undo = editor.post(f"{base}/cut/undo")  # back to the trim, which loses it too: refused
    assert undo.status_code == 422 and "would lose the word “now”" in undo.json()["detail"]
    assert editor.post(f"{base}/cut/undo-all").status_code == 422  # the cut's own trim loses it


def test_only_its_maker_or_the_owner_edits_it(app, db, editor, outsider, approved):  # noqa: F811
    base, _ = approved
    assert_hidden(
        outsider,
        [
            ("GET", f"{base}/cut"),
            ("POST", f"{base}/cut"),
            ("POST", f"{base}/cut/edits", {"kind": "retime", "piece": "c1"}),
        ],
    )


def test_the_music_dips_under_each_line_and_rises_between_or_stays_down():
    rise = cut_render.level({"quieter_db": 18, "gaps": "rise", "lines": [[1, 2], [2.3, 3], [6, 7]]})
    assert rise.count("clip(") == 2  # lines closer than the ramps hold it down between them
    assert "0.8741*" in rise  # 1 - 10^(-18/20)
    assert cut_render.level({"quieter_db": 18, "gaps": "down", "lines": [[1, 2]]}) == (
        "volume=0.0378")  # 0.30 at -18 dB, the whole way  # fmt: skip


def _piece(i: int, start: float, end: float) -> dict:
    return {"id": f"c{i}", "clip_id": f"c{i}", "take_id": i, "source": f"Clip {i}",
            "start": start, "end": end, "from": 0.0, "whole": False, "edited": False,
            "director": False}  # fmt: skip


def test_edits_replay_in_order_and_skip_what_no_longer_applies():
    from app.models.clips import CutEdit

    tl = {"mode": "narrated", "length": 9.0, "music": None, "words": [], "presenter": {
        "name": "Dr. Pickle", "spans": [{"start": 0, "end": 9.0, "side": "right",
                                         "size": "medium", "hidden": False, "director": False}]},
          "pieces": [_piece(1, 0, 3.0), _piece(2, 3.0, 6.0), _piece(3, 6.0, 9.0)]}  # fmt: skip
    split = CutEdit(id=5, kind="split", director=False, data={"piece": "c2", "at": 4.0})
    swap = CutEdit(id=6, kind="swap", director=True,
                   data={"piece": "c2.5", "take_id": 9, "source": "Take 1"})  # fmt: skip
    edge = CutEdit(id=7, kind="trim", director=False, data={"piece": "c3", "start": 6.5})
    hide = CutEdit(id=8, kind="presenter", director=True,
                   data={"start": 4.0, "end": 6.5, "hidden": True})  # fmt: skip
    got, lost = cut.replay(tl, [split, swap, edge, hide])
    ids = [(p["id"], p["start"], p["end"], p["take_id"]) for p in got["pieces"]]
    assert ids == [("c1", 0, 3.0, 1), ("c2", 3.0, 4.0, 2), ("c2.5", 4.0, 6.5, 9),
                   ("c3", 6.5, 9.0, 3)] and not lost  # fmt: skip
    assert got["pieces"][2]["director"] and got["pieces"][2]["from"] == 0.0  # its dot
    assert [(s["start"], s["end"], s["hidden"]) for s in got["presenter"]["spans"]] == [
        (0, 4.0, False), (4.0, 6.5, True), (6.5, 9.0, False)]  # fmt: skip
    _, lost = cut.replay(tl, [swap, edge])  # the split undone: its swap no longer applies
    assert lost == {6}
    tiny = CutEdit(id=9, kind="trim", director=False, data={"piece": "c1", "end": 2.8})
    assert cut.replay(tl, [tiny])[0]["pieces"][1]["start"] == 2.8  # the edge moves together
    with pytest.raises(cut.Refused):
        cut._one(cut.replay(tl, [])[0], CutEdit(id=10, kind="trim", director=False,
                                                data={"piece": "c1", "end": 5.9}))  # fmt: skip


def test_asked_in_the_chat_the_director_edits_the_cut_with_an_undo_each(
    app, db, owner, monkeypatch
):
    from app.models.clips import CutEdit
    from app.models.freestyles import Freestyle

    fs = _sent(owner, "presenter", NARRATION)
    _run(app, db, ticks=160)
    video = _video(db, fs)
    before = owner.get(f"/projects/{video.id}/cut").json()["number"]
    monkeypatch.setattr("app.director.GAP", timedelta(0))  # two notes a moment apart
    for text in ("Move the presenter to the left.", "Tighten it, the middle drags a bit."):
        said = owner.post(f"/freestyles/{fs['id']}/messages", json={"text": text})
        assert said.status_code == 201, said.text
        _run(app, db, ticks=120)
        out = owner.get(f"/freestyles/{fs['id']}").json()
        assert out["status"] == "delivered", [t["text"] for t in out["thread"]]
    edits = db.query(CutEdit).filter(CutEdit.project_id == video.id).order_by(CutEdit.id).all()
    assert [(e.kind, e.director) for e in edits] == [("presenter", True), ("retime", True)]
    assert edits[0].said.endswith("moved left")
    moves = [t for t in out["thread"] if t.get("edit")]
    assert [m["edit"]["id"] for m in moves] == [e.id for e in edits]
    assert moves[1]["text"].startswith(edits[1].said)
    got = owner.get(f"/projects/{video.id}/cut").json()
    assert got["number"] > before and got["changes"] == 0  # cut again with both, and watched
    assert got["timeline"]["presenter"]["spans"][0]["side"] == "left"
    assert all(e["director"] and e["in_cut"] for e in got["edits"])
    assert db.get(Freestyle, fs["id"]).project_id == video.id


def test_a_lip_synced_piece_keeps_its_picture_on_the_words():
    from app.models.clips import CutEdit

    tl = {"mode": "narrated", "length": 9.0, "music": None, "words": [], "presenter": None,
          "pieces": [_piece(1, 0, 3.0), {**_piece(2, 3.0, 6.0), "lipsync": True, "picture": 3.0},
                     _piece(3, 6.0, 9.0)]}  # fmt: skip

    def trim(**data):
        return cut.replay(tl, [CutEdit(id=1, kind="trim", director=False, data=data)])

    later, lost = trim(piece="c1", end=3.5)  # its start moves later: its picture with it
    assert not lost and (later["pieces"][1]["start"], later["pieces"][1]["from"]) == (3.5, 0.5)
    assert trim(piece="c1", end=2.5)[1] == {1}  # earlier than its take begins: out of sync
    assert trim(piece="c2", **{"from": 1.0})[1] == {1}  # its picture is the words' own
    other, _ = trim(piece="c2", end=5.5)  # a B-roll piece's start moves its picture too
    assert (other["pieces"][2]["start"], other["pieces"][2]["from"]) == (5.5, 0.0)
    assert trim(piece="c3", start=6.5)[1] == {1}  # longer than its picture: it'd be slowed
    assert trim(piece="c2", end=6.8)[1] == {1}
    swap = CutEdit(id=2, kind="swap", director=False,
                   data={"piece": "c2", "take_id": 9, "source": "Take 2"})  # fmt: skip
    moved = CutEdit(id=1, kind="trim", director=False, data={"piece": "c1", "end": 3.5})
    kept, _ = cut.replay(tl, [moved, swap])
    assert kept["pieces"][1]["from"] == 0.5  # another take of its clip, still on the words


def test_a_song_cut_must_reach_its_last_good_line_not_every_word_heard():
    tl = {
        "mode": "song",
        "length": 20.0,
        "seconds": 30.0,
        "last_word": 19.0,
        "words": [{"word": "yeah", "start": 24.0, "end": 24.5}],
    }  # an ad-lib after the end
    cut_edits._fits(tl)  # the song's own end, a breath after its last line: fine
    with pytest.raises(cut.Refused):
        cut_edits._fits({**tl, "length": 18.5})


def test_the_end_fades_only_after_the_last_word():
    assert cut_render.fade_out(10.0, 0) == "st=8.50:d=1.50"  # the usual 1.5 s
    assert cut_render.fade_out(7.29, 6.99) == "st=6.99:d=0.30"  # a shorter end: after the word
    assert cut_render.fade_out(7.0, 7.0) == "st=7.00:d=0.05"


def test_redo_after_undo_all_brings_the_oldest_edit_back_first(owner, presenter):
    first = _edit(owner, presenter, kind="music", quieter_db=6).json()["edits"][-1]["id"]
    _edit(owner, presenter, kind="music", gaps="down")
    owner.post(f"{presenter}/cut/undo-all")
    back = owner.post(f"{presenter}/cut/redo").json()
    assert [e["id"] for e in back["edits"] if not e["undone"]] == [first]
