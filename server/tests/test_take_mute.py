"""Mute a span of a take in the final cut: free (ffmpeg), the take and its approval untouched."""

import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from app import take_mute
from app.models.clips import ClipTake, ProjectClip
from app.models.projects import Project
from app.take_words import compare
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


def test_stretches_are_kept_as_added_inside_the_take_and_joined_only_in_the_cut():
    take = ClipTake(made_with={})
    take_mute.add(take, 1.0, 2.0, longest=8)
    take_mute.add(take, 1.5, 3.0, longest=8)  # overlaps: kept as its own, for Undo
    take_mute.add(take, -1, 0.5, longest=8)  # before the start: from 0
    assert take_mute.add(take, 7.5, 12, longest=8) == [[1.0, 2.0], [1.5, 3.0], [0.0, 0.5],
                                                       [7.5, 8]]  # fmt: skip
    clip_row = ProjectClip(clip_id="c2")
    assert take_mute.labels(clip_row, take) == ["c2/mute:0.0-0.5", "c2/mute:1.0-3.0",
                                                "c2/mute:7.5-8"]  # fmt: skip
    with pytest.raises(ValueError, match="Pick a stretch"):
        take_mute.add(take, 9, 10, longest=8)  # past the end: nothing left
    with pytest.raises(ValueError, match="Pick a stretch"):
        take_mute.add(take, 0.5, float("nan"), longest=8)
    assert take_mute.remove(take, 1) == [[1.0, 2.0], [0.0, 0.5], [7.5, 8]]  # Undo: just that one
    for i in range(5):
        take_mute.add(take, 3.5 + i * 0.7, 3.7 + i * 0.7, longest=8)
    with pytest.raises(ValueError, match="8 muted stretches at most"):
        take_mute.add(take, 6.9, 7.1, longest=8)


def _loudness(video: bytes, start: float, seconds: float) -> float:
    """The loudest sample's level, in dB, over start–start+seconds."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "v.mp4"
        path.write_bytes(video)
        args = ["-ss", str(start), "-t", str(seconds), "-i", str(path), "-af", "volumedetect",
                "-f", "null", "-"]  # fmt: skip
        out = subprocess.run(["ffmpeg", *args], capture_output=True, text=True, check=True)  # noqa: S603, S607
    out = out.stderr
    found = re.search(r"max_volume: (-?[\d.]+|-inf) dB", out)
    return float("-inf") if found[1] == "-inf" else float(found[1])


def test_the_take_is_silent_over_the_span_and_heard_elsewhere():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tone.mp4"
        args = ["-v", "error", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=3", "-f", "lavfi",
                "-i", "sine=frequency=440:duration=3", "-shortest", "-c:v", "libx264", "-c:a",
                "aac", str(path)]  # fmt: skip
        subprocess.run(["ffmpeg", *args], check=True)  # noqa: S603, S607
        video = path.read_bytes()
    muted = take_mute.apply(video, [[1.0, 2.0]])
    assert _loudness(muted, 1.2, 0.6) < -60  # silent over the span
    assert _loudness(muted, 0.1, 0.6) > -30 and _loudness(muted, 2.3, 0.5) > -30  # heard around
    assert take_mute.apply(video, []) is video  # nothing to mute: the take as it is


def test_an_unscripted_line_offers_its_stretch_to_mute():
    lines = [{"who": "MIA", "text": "Fomo made me rich!"}]
    heard = [{"start": 0.5, "end": 1.8, "text": "Fomo made me rich!"},
             {"start": 2.5, "end": 3.8, "text": "Let's go home."}]  # fmt: skip
    (extra,) = compare(lines, heard, "fomo", "FOH-moh", ["Mia waves."])
    assert extra["span"] == [2.5, 3.8]


def test_mute_and_undo_from_the_clip_keep_its_approval(app, db, editor, setup, clip):  # noqa: F811
    clips = f"/projects/{setup['project']}/clips"
    assert editor.post(f"{clips}/{clip['id']}/mute", json={"start": 1, "end": 2}).status_code == 409
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    editor.post(f"{clips}/{clip['id']}/approve")
    shown = editor.post(f"{clips}/{clip['id']}/mute", json={"start": 1.0, "end": 2.0}).json()
    assert shown["takes"][0]["mutes"] == [[1.0, 2.0]] and shown["approved"] is True
    bad = editor.post(f"{clips}/{clip['id']}/mute", json={"start": 99, "end": 100})
    assert bad.status_code == 422  # past the clip's end
    nan = editor.post(f"{clips}/{clip['id']}/mute", content='{"start": 0.5, "end": NaN}',
                      headers={"content-type": "application/json"})  # fmt: skip
    assert nan.status_code == 422
    back = editor.delete(f"{clips}/{clip['id']}/mute/0").json()
    assert back["takes"][0]["mutes"] == []
    assert editor.delete(f"{clips}/{clip['id']}/mute/0").status_code == 404
    db.get(Project, setup["project"]).archived_at = db.get(ProjectClip, clip["id"]).created_at
    db.commit()
    archived = editor.post(f"{clips}/{clip['id']}/mute", json={"start": 1, "end": 2})
    assert archived.status_code == 409


LINE = "Two of these every morning. Oil of oregano with black seed oil."


def _words(*spans):
    """Heard words, each (text, start): one word a tenth of a second."""
    return [{"word": w, "start": round(t + n / 10, 2), "end": round(t + (n + 1) / 10, 2)}
            for text, t in spans for n, w in enumerate(text.split())]  # fmt: skip


def test_a_line_heard_in_two_pieces_is_never_called_unscripted():
    """Video 284: c3's line was heard as "Two of these every morning." and "Oil of oregano with
    black seed oil.", and the first piece was called unscripted, to mute: the line's only
    copy. A piece heard twice is still a repeat."""
    lines = [{"who": "JESS", "text": LINE}]
    apart = [{"start": 1.1, "end": 2.5, "text": "Two of these every morning."},
             {"start": 2.7, "end": 5.0, "text": "Oil of oregano with black seed oil."}]  # fmt: skip
    assert compare(lines, apart, "Resilia", "", ["Jess holds up the pouch."]) == []
    twice = [{"start": 0.0, "end": 1.0, "text": "Two of these every morning."}, *apart]
    (extra,) = compare(lines, [twice[0], {**apart[0], "text": LINE}], "Resilia", "", [])
    assert extra["kind"] == "extra" and extra["span"] == [0.0, 1.0]


def test_a_mute_never_silences_a_lines_only_copy_and_the_director_undoes_its_own(
    app,
    db,
    editor,
    setup,  # noqa: F811
    clip,  # noqa: F811
    monkeypatch,
):
    """Video 284: the director muted "Two of these every morning", the line's only copy, and
    said it couldn't lift the mute. A mute (anyone's) that leaves a scripted line heard
    nowhere in the cut is refused, saying why; a repeat can still be muted; and the director
    can unmute what it muted, never a person's mute."""
    from app import director_tools
    from app.models.accounts import User

    clips = f"/projects/{setup['project']}/clips"
    editor.post(f"{clips}/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    heard = _words(("Two of these every morning.", 1.1), ("Oil of oregano with black seed oil.",
                                                          2.7))  # fmt: skip
    monkeypatch.setattr("app.word_splice._heard", lambda db, take: (heard, ""))
    monkeypatch.setattr(take_mute, "_lines", lambda db, row: [("Jess", LINE)])
    only = editor.post(f"{clips}/{clip['id']}/mute", json={"start": 1.0, "end": 1.6})
    assert only.status_code == 409, only.text
    assert only.json()["detail"] == take_mute.LOST_LINE.format(who="Jess's ", line=LINE)
    heard[:0] = _words(("Two of these every morning.", 0.0))  # said twice: a repeat to mute
    assert (
        editor.post(f"{clips}/{clip['id']}/mute", json={"start": 0.0, "end": 0.5}).status_code
        == 200
    )
    row = db.get(ProjectClip, clip["id"])
    take = db.get(ClipTake, row.picked_take_id)
    db.refresh(take)
    take.made_with = {**take.made_with, "director_mutes": [[0.0, 0.5]]}  # the director's
    db.commit()
    person = editor.post(f"{clips}/{clip['id']}/mute", json={"start": 3.6, "end": 3.9})
    assert person.status_code == 200, person.text  # a person's own mute
    db.expire_all()  # the person's mute was made in the app's own session
    project = db.get(Project, setup["project"])
    ed = db.query(User).filter_by(email="ed@example.com").one()
    move = {"tool": "unmute", "clip_id": row.clip_id}
    said = director_tools.run(db, ed, project, move, app.state.storage)
    assert said.startswith("Unmuted the stretch you muted in clip 1"), said
    db.refresh(take)
    assert take_mute.spans(take) == [[3.6, 3.9]]  # the person's stays
    again = director_tools.run(db, ed, project, move, app.state.storage)
    assert again.startswith("Refused: nothing you muted is left in clip 1")


def test_the_delivery_note_never_says_a_line_the_cut_has_isnt_heard():
    """Video 284's note said "Not heard: Jess: “Your gut's backed up.”" from a take check,
    while the final cut's transcript has it."""
    from app.delivery import _heard_in_cut

    missing = {"kind": "missing", "text": "Not heard: Jess: “Your gut's backed up.”"}
    cut = ["granny", "means", "well", "your", "gut's", "backed", "up", "mine", "was", "too"]
    assert _heard_in_cut(missing, cut)
    assert not _heard_in_cut(missing, ["granny", "means", "well"])
    assert not _heard_in_cut({**missing, "kind": "extra"}, cut) and not _heard_in_cut(missing, None)
