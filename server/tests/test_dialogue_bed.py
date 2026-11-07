"""A music bed under a Dialogue cut (session 35, item 3, design A): free, from the brand's own
beds. House's references have a bed under every second; a Dialogue cut had only its takes'
sound, so 226 ended on 14 s of silence and the director's "lay the bed" was refused. On the
stand-ins, with real ffmpeg."""

import subprocess

import pytest

from app import cut, cut_edits
from app.models.files import StoredFile
from app.models.jobs import Job
from app.models.script_library import Script, ScriptDraft
from app.models.songs import SongTake
from tests.conftest import make_cut
from tests.test_cut import _edit, _tone
from tests.test_cut_in import _seconds, approved  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture
from tests.test_script_library import _make


def _bed(app, db, owner) -> int:
    """A narrated script's take in the same brand, with its music bed (a 3 s tone)."""
    made = _make(owner, text="NARRATOR: The dip came back.")
    draft = db.query(ScriptDraft).filter_by(script_id=made["id"], slot=0).one()
    ws = db.get(Script, made["id"]).workspace_id
    job = Job(workspace_id=ws, kind="sound", provider="fake", input={"step": "narration_bed"},
              status="succeeded")  # fmt: skip
    db.add(job)
    key = f"{ws}/bed-tone"
    app.state.storage.put(key, _tone(3))
    bed = StoredFile(workspace_id=ws, key=key, filename="bed.mp3", content_type="audio/mpeg",
                     size=1, sha256="0" * 64)  # fmt: skip
    db.add(bed)
    db.flush()
    db.add(SongTake(draft_id=draft.id, number=1, kind="narration", job_id=job.id, lyrics="",
                    style_line="", music_file_id=bed.id))  # fmt: skip
    db.commit()
    return bed.id


def _loudness(data: bytes) -> float:
    """The cut's mean volume in dB (-91 for digital silence)."""
    args = ["ffmpeg", "-hide_banner", "-i", "pipe:0", "-af", "volumedetect", "-f", "null", "-"]
    said = subprocess.run(args, input=data, capture_output=True).stderr.decode()  # noqa: S603
    return float(said.split("mean_volume:")[1].split("dB")[0])


def test_a_dialogue_cut_lays_the_brands_bed_under_it_free(app, db, owner, editor, approved):  # noqa: F811
    base, _ = approved
    make_cut(app, db, editor, base)
    first = editor.get(f"/files/{editor.get(f'{base}/cut').json()['file_id']}").content
    assert _loudness(first) < -80  # its take is silent
    none = _edit(editor, base, kind="music", removed=False)
    assert (none.status_code, none.json()["detail"]) == (422, cut_edits.NO_BED)
    assert _edit(editor, base, kind="music", quieter_db=6).json()["detail"] == cut.NO_MUSIC

    bed = _bed(app, db, owner)
    assert [m["file_id"] for m in editor.get(f"{base}/cut/music").json()] == [bed]  # beds only
    laid = _edit(editor, base, kind="music", removed=False).json()
    music = laid["timeline"]["music"]
    assert (music["file_id"], music["loop"], music["removed"]) == (bed, True, False)
    assert laid["edits"][-1]["said"] == "A music bed under the cut"  # its name: just "Music"
    quieter = _edit(editor, base, kind="music", quieter_db=12).json()
    assert quieter["timeline"]["music"]["quieter_db"] == 12  # a bed's level, as a narration's

    made = make_cut(app, db, editor, base).json()
    assert made["number"] == 2
    file_id = editor.get(f"{base}/cut").json()["file_id"]
    data = editor.get(f"/files/{file_id}").content
    assert _loudness(data) > -40  # the bed plays under the silent take, looped past its 3 s
    assert abs(_seconds(data) - _seconds(first)) < 0.2  # as long as the cut, picture copied


def test_the_bed_dips_under_a_dialogue_cuts_lines():
    """Its lines are the cut's words run together across a short pause, so the bed stays down
    through a quick reply and rises between lines."""
    words = [{"word": "I", "start": 0.0, "end": 0.3}, {"word": "do.", "start": 0.35, "end": 0.8},
             {"word": "Hell", "start": 1.0, "end": 1.4}, {"word": "no!", "start": 1.4, "end": 1.9},
             {"word": "What?!", "start": 4.0, "end": 4.6}]  # fmt: skip
    assert cut.spoken(words) == [[0.0, 1.9], [4.0, 4.6]]
    tl = {"music": {"removed": False}, "presenter": None, "mode": "takes"}
    assert cut.doing(tl) == "putting the clips together, music under them"


def test_the_director_lays_a_bed_only_when_a_person_asks():
    """Reed, 7 Nov: "Music gets added in post." The tool stays for a person's note; the
    director never lays a bed for a style's guide, and the guides say music is in post."""
    from app import guides, prompts

    director = prompts.system("director")
    assert (
        "in a dialogue cut with no music yet, `removed` false lays the brand's newest" in director
    )
    assert "only when a person's note asks for music, whatever the style's guide says" in director
    assert "as House's does" not in director
    assert "never call a missing bed a fault or ask for one" in director
    house = guides.style("house")["sections"]
    sound = next(line for part in house.values() for line in part.splitlines()
                 if line.startswith("- Sound:"))  # fmt: skip
    assert sound.startswith("- Sound: Music is added in post (Reed, 7 Nov)")
    assert "never where a person removed the music, set its level or swapped it" in director


def test_a_narrated_video_waiting_for_its_narration_offers_no_bed_yet(monkeypatch):
    """QA on #1415: its music comes with its narration, so a bed isn't offered before it."""
    from app import narration

    monkeypatch.setattr(cut_edits, "song", lambda db, project: None)
    monkeypatch.setattr(narration, "video_kind", lambda db, project: "narrated")
    assert cut_edits.music_choices(None, None) == []
    monkeypatch.setattr(narration, "video_kind", lambda db, project: "song")
    assert cut_edits.music_choices(None, None) == []


def test_a_persons_music_choice_stays_theirs(app, db, owner, editor, approved):  # noqa: F811
    """QA on #1415: a person removed the bed, or set it 24 dB under, and the director's music
    edit put it back. A person's newest music edit (a removal, a level, a swap) is theirs:
    the director's music edit, or its undo of it, is refused unless a person's note asks."""
    from types import SimpleNamespace

    from app import director_tools
    from app.models.accounts import User
    from app.models.projects import Project

    base, _ = approved
    _bed(app, db, owner)
    pid = int(base.rsplit("/", 1)[1])
    project, ed = db.get(Project, pid), db.query(User).filter_by(email="ed@example.com").one()
    cut_edits.add(db, ed, project, "music", {"removed": False}, director=True)  # the director's
    db.commit()
    gone = _edit(editor, base, kind="music", removed=True).json()  # the person's "no"
    assert gone["timeline"]["music"]["removed"] is True
    theirs = max(gone["edits"], key=lambda e: e["id"])
    with pytest.raises(cut.Refused) as no:
        cut_edits.add(db, ed, project, "music", {"removed": False}, director=True)
    assert str(no.value) == cut_edits.PERSONS_MUSIC.format("Music removed")
    db.rollback()
    with pytest.raises(cut.Refused):
        cut_edits.add(db, ed, project, "music", {"quieter_db": 6}, director=True)
    db.rollback()
    me = {"project_id": pid, "user": ed, "db": db}
    request = SimpleNamespace(app=app)
    undo = {"kind": "undo", "edit_id": theirs["id"]}
    said = director_tools._edit_cut(db, project, undo, request, me, {"id": "r"}, "b6: music.")
    assert said == f"Refused: {cut_edits.PERSONS_MUSIC.format('Music removed')}"
    level = _edit(editor, base, kind="music", quieter_db=24).json()  # the person's level
    assert level["timeline"]["music"]["quieter_db"] == 24
    marked = cut_edits.PERSON_ASKED.set(True)  # a person's note asks for the bed back
    try:
        cut_edits.add(db, ed, project, "music", {"removed": False}, director=True)
    finally:
        cut_edits.PERSON_ASKED.reset(marked)
    db.commit()
    assert editor.get(f"{base}/cut").json()["timeline"]["music"]["removed"] is False
    assert _edit(editor, base, kind="music", quieter_db=20).status_code == 201  # a person may


def _pcm(data: bytes) -> list[int]:
    """The sound as 16-bit mono samples."""
    import array

    args = ["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", "44100", "-f", "s16le",
            "-"]  # fmt: skip
    raw = subprocess.run(args, input=data, capture_output=True, check=True).stdout  # noqa: S603
    return array.array("h", raw).tolist()


def test_a_looped_bed_crossfades_at_each_repeat_with_no_click(tmp_path):
    """QA on #1415: `-stream_loop` jumped about 9x the normal sample step at the loop (a
    click). A 0.77 s tone (it ends mid-cycle) looped under a 3 s cut: the biggest step from
    one sample to the next stays a normal one for that tone, seams included."""
    from app import cut_render

    tone = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",  # noqa: S603, S607
                           "sine=frequency=440:duration=0.77", "-f", "wav", "-"],
                          capture_output=True, check=True).stdout  # fmt: skip
    black = "color=c=black:s=64x64:d=3"
    video = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", black,  # noqa: S603, S607
                            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "3",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"],
                           capture_output=True, check=True).stdout  # fmt: skip
    mix = {"loop": True, "quieter_db": 0, "gaps": "down", "last_word": 3.0}

    def steepest(data: bytes) -> tuple[int, int]:  # inside the cut: its first and last ms aside
        out = _pcm(data)[882:-2205]
        steps = sorted(abs(b - a) for a, b in zip(out, out[1:], strict=False))
        return steps[-1], steps[int(len(steps) * 0.99)]  # the biggest, and the tone's own

    top, usual = steepest(cut_render.bedded(video, tone, mix))
    assert usual > 0 and top < 1.6 * usual, (top, usual)
    (tmp_path / "bed.wav").write_bytes(tone)
    plain = subprocess.run(["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", "bed.wav",  # noqa: S603, S607
                            "-t", "3", "-f", "wav", "-"], cwd=tmp_path, capture_output=True,
                           check=True).stdout  # fmt: skip
    top, usual = steepest(cut_render.bedded(video, plain, {**mix, "loop": False}))
    assert top > 5 * usual  # the check hears a plain loop's click (about 11x here)
    name = cut_render.looped(tmp_path, "bed.wav", 3.0)  # the narrated mix's loop too
    assert name == "looped.wav" and cut_render._length(tmp_path, name) >= 3.0


def test_only_an_open_note_written_after_a_persons_music_choice_unlocks_it(
    app,
    db,
    owner,
    editor,
    approved,  # noqa: F811
):
    """QA on #1415: the run's Note 1 said "Make the hook punchier"; a person then removed
    the music, and the director's "Note 1: bring the music back." went through. Only a
    person's note written after their music edit, and not answered yet, unlocks it."""
    from datetime import timedelta
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app import director, director_tools
    from app.db import utcnow
    from app.models.accounts import User
    from app.models.projects import Project

    base, _ = approved
    _bed(app, db, owner)
    pid = int(base.rsplit("/", 1)[1])
    project, ed = db.get(Project, pid), db.query(User).filter_by(email="ed@example.com").one()
    cut_edits.add(db, ed, project, "music", {"removed": False}, director=True)
    db.commit()
    before = (utcnow() - timedelta(minutes=5)).isoformat()
    _edit(editor, base, kind="music", removed=True)  # the person's "no", after Note 1
    after = (utcnow() + timedelta(minutes=1)).isoformat()
    project.director_chat = [
        {"by": ed.id, "text": "Make the hook punchier.", "at": before, "run": "r1"},
        {"by": ed.id, "text": "Bring the music back.", "at": after, "run": "r1"},
        {"by": ed.id, "text": "Music back, please.", "at": after, "run": "r1"},
    ]  # fmt: skip
    db.add(
        director.Job(
            workspace_id=project.workspace_id,
            kind="claude",
            provider="fake",
            project_id=pid,
            status="succeeded",
            input={"step": director.STEP, director.RUN: {"id": "r1"}, "result": "ok"},
            output={"tool": "wait", "why": "Note 3: on it."},
        )
    )  # Note 3 answered
    db.commit()
    me = {"project_id": pid, "user": ed, "db": db}
    request = SimpleNamespace(app=app)
    back = {"kind": "music", "removed": False}

    def move(why: str) -> str:  # as the director's own move (its route marks it)
        from app.routes.jobs import DIRECTOR_TOOL

        marked = DIRECTOR_TOOL.set(True)
        try:
            return director_tools._edit_cut(db, project, dict(back), request, me,
                                            {"id": "r1"}, why)  # fmt: skip
        except HTTPException as no:
            return f"Refused: {no.detail}"
        finally:
            DIRECTOR_TOOL.reset(marked)
            db.commit()

    refused = f"Refused: {cut_edits.PERSONS_MUSIC.format('Music removed')}"
    assert move("Note 1: bring the music back.") == refused  # older than the removal
    assert move("Note 3: bring the music back.") == refused  # answered already
    assert move("Note 2: bring the music back.").startswith("Music back")  # newer and open


def test_a_published_scripts_ending_is_its_own_words():
    """Reed, 7 Nov: "The words in the script are the end-all be-all." Craft's question and
    call to action guide writing a new script only; a published script ends on its own words."""
    from app import prompts

    director = prompts.system("director")
    assert "Writing a new script: one simple question viewers can argue over" in director
    assert "A published script's ending is its own last words" in director
    assert "never a question or a call to action it doesn't have" in director
