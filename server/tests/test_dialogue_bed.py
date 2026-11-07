"""A music bed under a Dialogue cut (session 35, item 3, design A): free, from the brand's own
beds. House's references have a bed under every second; a Dialogue cut had only its takes'
sound, so 226 ended on 14 s of silence and the director's "lay the bed" was refused. On the
stand-ins, with real ffmpeg."""

import subprocess

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
    assert laid["edits"][-1]["said"].startswith("Music “") and "under the cut" in (
        laid["edits"][-1]["said"])  # fmt: skip
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


def test_the_director_lays_the_bed_where_the_style_puts_music_under_every_second():
    from app import prompts

    director = prompts.system("director")
    assert (
        "in a dialogue cut with no music yet, `removed` false lays the brand's newest" in director
    )
    assert "never in a style whose guide wants none" in director
