"""The director watches and listens to its cut (watch_cut): a free pass makes its strips,
measurements and spectrogram (app/deep_watch), one look on the director's own limit says
what's off, and the findings it can act on are checked first. On the free stand-ins."""

import pytest
from fastapi import HTTPException

from app import watch_cut
from app.models.accounts import User
from app.models.jobs import Job
from app.models.projects import Project
from app.providers.fake_local import hear_cut
from app.providers.local import LocalProvider
from app.worker import run_once
from tests.conftest import make_cut, run_writer
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture

CUT = [{"clip_id": "c1", "start": 0.0, "end": 4.0, "take_id": 1,
        "other_takes": [{"take_id": 7, "number": 2, "verdict": "clean"}]},
       {"clip_id": "c2", "start": 4.0, "end": 9.0, "take_id": 2, "other_takes": []}]  # fmt: skip
WORDS = [{"word": "Get", "start": 4.5, "end": 4.8, "clip_id": "c2"},
         {"word": "fomo.", "start": 4.8, "end": 5.3, "clip_id": "c2"},
         {"word": "Ugh!", "start": 7.0, "end": 7.4, "clip_id": "c2"}]  # fmt: skip


def test_each_clip_sits_where_the_cut_put_it_and_the_strips_spread_over_it():
    spans = watch_cut.spans_of([("c1", 1, 4.0), ("c2", 2, 6.0)], 9.0)  # re-encoded: 9 s, not 10
    assert [(s["clip_id"], s["start"], s["end"], s["seconds"]) for s in spans] == [
        ("c1", 0.0, 3.6, 4.0), ("c2", 3.6, 9.0, 6.0)]  # fmt: skip
    assert [watch_cut.count_for(n) for n in (6, 30, 90)] == [16, 24, 48]  # 0.8 a second
    assert watch_cut.clip_at(spans, 5.0) == "c2"
    assert (watch_cut._clips(spans, 0.0, 2.0), watch_cut._clips(spans, 2.0, 5.0)) == ("c1", "c1–c2")


def test_only_findings_the_director_can_act_on_reach_it():
    found = {"findings": [
        {"clip_id": "c2", "start": 6.9, "end": 7.5, "says": "c2: a groan", "fix": "mute",
         "note": "Ugh!"},
        {"clip_id": "c2", "start": 4.4, "end": 5.4, "says": "c2: the line", "fix": "mute"},
        {"clip_id": "c1", "start": 3.5, "end": 4.5, "says": "across", "fix": "mute"},
        {"clip_id": "c1", "start": 0, "end": 4, "says": "c1: better", "fix": "pick", "take_id": 7},
        {"clip_id": "c1", "start": 0, "end": 4, "says": "c1: no such", "fix": "pick", "take_id": 9},
        {"clip_id": "c2", "start": 4, "end": 9, "says": "c2: face", "fix": "redo",
         "kind": "cast", "evidence": "picture", "take_id": 7,
         "note": "Keep her face as on her sheet."},
    ]}  # fmt: skip
    kept = watch_cut.checked(found, CUT, WORDS, "MIA: Get fomo.")
    assert [(f["says"], f["fix"]) for f in kept] == [
        ("c2: a groan", "mute"),
        ("c1: better", "pick"),
        ("c2: face", "redo"),
    ]
    groan, pick, redo = kept
    assert groan["mute"] == [2.9, 3.5]  # in c2's own take seconds, for POST …/mute
    assert (pick["take_id"], pick["mute"]) == (7, None) and redo["take_id"] is None
    nowhere = {"clip_id": "c3", "start": 0, "end": 1, "says": "nowhere", "fix": "redo"}
    assert watch_cut.checked({"findings": [nowhere]}, CUT, WORDS, "") == []
    old = watch_cut.checked({"findings": [{**found["findings"][3], "fix": "other_take"}]},
                            CUT, WORDS, "")  # fmt: skip
    assert old[0]["fix"] == "pick"  # the schema's first name, said as the director reads it


def test_a_mute_never_covers_a_script_word_even_misheard():
    """QA-6 on #1133: "Get fogo." heard for "Get fomo.": the brand word is still the script's."""
    fogo = [{**w, "word": "fogo."} if w["word"] == "fomo." else w for w in WORDS]
    mute = {"clip_id": "c2", "start": 4.8, "end": 5.3, "says": "c2: he says fogo", "fix": "mute"}
    assert watch_cut.checked({"findings": [mute]}, CUT, fogo, "MIA: Get fomo.") == []
    near = {**mute, "start": 5.25, "end": 5.6}  # the line's tail, still on it
    assert watch_cut.checked({"findings": [near]}, CUT, fogo, "MIA: Get fomo.") == []
    for said in (["Foh-moh."], ["Pho", "mo."]):  # the brand word alone, heard in pieces (QA-6)
        alone = [{"word": w, "start": 6.0 + n * 0.2, "end": 6.2 + n * 0.2, "clip_id": "c2"}
                 for n, w in enumerate(said)]  # fmt: skip
        mute_it = {**mute, "start": 5.9, "end": 6.5}
        assert watch_cut.checked({"findings": [mute_it]}, CUT, alone, "MIA: Get fomo.") == []
    hmm = [{"word": "Hmm.", "start": 6.0, "end": 6.3, "clip_id": "c2"}]  # "MOM" isn't a word said
    lone = {**mute, "start": 5.9, "end": 6.4}
    assert watch_cut.checked({"findings": [lone]}, CUT, hmm, "MOM: Get fomo.")[0]["mute"]
    groan = {**mute, "start": 6.9, "end": 7.5}  # its own line after a pause: may be muted
    assert watch_cut.checked({"findings": [groan]}, CUT, fogo, "MIA: Get fomo.")[0]["mute"]


def test_a_mute_lands_in_take_seconds_when_the_cut_ran_short():
    cut = [{**CUT[1], "start": 3.6, "end": 9.0, "seconds": 6.0}]  # 6 s of take in 5.4 s of cut
    mute = {"clip_id": "c2", "start": 8.0, "end": 8.5, "says": "c2: a thud", "fix": "mute"}
    (kept,) = watch_cut.checked({"findings": [mute]}, cut, [], "")
    assert kept["mute"] == [4.89, 5.44]  # not [4.4, 4.9]: scaled back to the take


def test_the_director_watches_its_cut_and_reads_what_to_fix(app, db, editor, setup, clip):  # noqa: F811
    project = db.get(Project, setup["project"])
    user = db.query(User).filter_by(email=editor.get("/auth/me").json()["email"]).one()
    with pytest.raises(HTTPException, match="Make the cut first."):
        watch_cut.start(db, user, project, None)
    base = f"/projects/{setup['project']}"
    editor.post(f"{base}/clips/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    editor.post(f"{base}/clips/{clip['id']}/approve")
    assert make_cut(app, db, editor, base).status_code == 200
    run = {"id": "r1", "turn": 3, "redos": {}}
    assert watch_cut.start(db, user, project, run) == "Watching the cut."
    db.commit()
    assert watch_cut.state(db, project)["state"] == "watching"
    run_once(db, {"local": LocalProvider(app.state.storage, hear_cut=hear_cut)},
             app.state.storage, only={"local"})  # fmt: skip
    look = db.query(Job).filter(Job.kind == "check-claude").order_by(Job.id.desc()).first()
    assert look.input["step"] == "watch_cut" and look.input["director_run"] == run
    pictures = look.input["files"]["reference_images"]
    assert len(pictures) == 2  # a 1 s square cut: one strip of 16 frames, and its sound
    said = look.input["prompt"]
    assert "[Image1] c1, 0.0–" in said and "sampled frames over the whole" in said
    assert "[Image2] c1, 0.0–1.1 s: the sound as a spectrogram" in said
    assert "<cut>" in said and "<measured>" in said and "Loudness" in said
    assert "Music bed: none in this cut" in said  # a dialogue cut: its quiet is the clips
    assert "which is right: music is added in post" in said  # never a fault (Reed, 7 Nov)
    assert look.credits > 0  # priced "up to", on the director's own limit
    run_writer(app, db)
    db.expire_all()
    watch = watch_cut.state(db, project)
    assert (watch["state"], watch["current"], watch["lands"]) == ("done", True, True)
    redo, mute = watch["findings"]
    assert (redo["clip_id"], redo["fix"], redo["mute"]) == ("c1", "redo", None)
    start, end = mute["mute"]  # in c1's take seconds, half a second
    assert mute["fix"] == "mute" and 0 < start and abs(end - start - 0.5) <= 0.05
    editor.post(f"{base}/clips/{clip['id']}/generate")  # a new take: the cut is out of date
    _work(app, db, FakeSeedance([_mp4("blue")]))
    db.expire_all()
    assert watch_cut.state(db, project)["current"] is False


def test_a_redo_only_the_sound_suggests_is_kept_and_said_unconfirmed():
    """Reed, 4 Nov: uncertain evidence alone never triggers a paid remake."""
    music = {"clip_id": "c2", "start": 4, "end": 9, "says": "c2: music under the line",
             "fix": "redo", "kind": "sound", "evidence": "sound", "note": "No music."}  # fmt: skip
    (kept,) = watch_cut.checked({"findings": [music]}, CUT, WORDS, "MIA: Get fomo.")
    assert (kept["fix"], kept["says"]) == ("keep", "c2: music under the line (not confirmed)")
    seen = {**music, "kind": "picture", "evidence": "picture", "says": "c2: a hand melts"}
    assert watch_cut.checked({"findings": [seen]}, CUT, WORDS, "")[0]["fix"] == "redo"
    for kind in ("lipsync", "voice", "sound", "words"):  # a kind the frames can't show
        doubt = {**seen, "kind": kind, "says": "c2: the lips look late"}
        assert watch_cut.checked({"findings": [doubt]}, CUT, WORDS, "")[0]["fix"] == "keep"
    bare = {k: v for k, v in seen.items() if k != "evidence"}  # no evidence: never paid
    assert watch_cut.checked({"findings": [bare]}, CUT, WORDS, "")[0]["fix"] == "keep"


def test_a_cut_redo_on_the_transcript_alone_is_kept_unconfirmed():
    fogo = {"clip_id": "c2", "start": 4.4, "end": 5.4, "says": "c2: 'fogo' for fomo",
            "fix": "redo", "evidence": "words", "note": "Say fomo right."}  # fmt: skip
    (kept,) = watch_cut.checked({"findings": [fogo]}, CUT, WORDS, "MIA: Get fomo.")
    assert kept["fix"] == "keep" and kept["says"].endswith("(not confirmed)")


def test_the_watch_is_told_whether_the_cut_has_a_music_bed(db):
    """Video 245 (7 Nov): one note said there's no music under the video, the next that "the
    music bed seems to fall out". The watch reads whether the cut has a bed, so a quiet
    stretch with none is the clips' own sound."""
    from app.models.clips import FinalVideo

    none = FinalVideo(project_id=1, file_id=1, take_ids=[], timeline={"music": None})
    removed = FinalVideo(project_id=1, file_id=1, take_ids=[],
                         timeline={"music": {"removed": True}})  # fmt: skip
    bed = FinalVideo(project_id=1, file_id=1, take_ids=[], timeline={"music": {"removed": False}})
    db.add_all([none, removed, bed])
    db.flush()
    assert watch_cut._bed(db, none.id) == watch_cut._bed(db, removed.id) == watch_cut.NO_BED
    assert watch_cut._bed(db, bed.id) == watch_cut.BED
    assert watch_cut._bed(db, None) == ""  # an older watch: nothing said
    song = FinalVideo(project_id=1, file_id=1, take_ids=[],
                      timeline={"mode": "song", "music": None})  # fmt: skip
    db.add(song)
    db.flush()
    assert watch_cut._bed(db, song.id) == ""  # a song's cut: the song is its sound (QA on #1429)
