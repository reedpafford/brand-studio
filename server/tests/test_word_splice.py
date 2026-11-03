"""Splice a word (Reed, after his test: "fogo" for fomo): the brand said wrong in a take is
covered at stitch time by a clean copy in the same voice. Free, and only the brand's name."""

import re
import subprocess

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app import director_tools, word_splice
from app.models.accounts import User
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from app.providers import get_providers
from app.providers.fake_local import _spread
from app.worker import run_once
from tests.test_clip_takes import FakeSeedance, _mp4, _work, clip  # noqa: F401 - fixture
from tests.test_enhance import setup  # noqa: F401 - fixture


def _said(monkeypatch, *lines):
    """The stand-in listener hears each new take say the next of `lines`."""
    left = list(lines)

    def hear(path, job):
        text = left.pop(0)
        return [{"start": 0.5, "end": 1.8, "text": text, "speaker": None,
                 "words": _spread(text, 0.5, 1.8)}]  # fmt: skip

    monkeypatch.setattr("app.providers.fake_local.hear_take", hear)
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins


def _take(app, db, editor, setup, clip):  # noqa: F811
    app.state.settings.fake_providers = True
    editor.post(f"/projects/{setup['project']}/clips/{clip['id']}/generate")
    _work(app, db, FakeSeedance([_mp4("red")]))
    for _ in range(2):  # its words check: a free listen on our server
        run_once(db, get_providers(app.state.settings, app.state.storage), app.state.storage)
    db.expire_all()


def _one_voice(db, row):
    """Every line of the clip is Mom's (the fixture's clip has two speakers)."""
    bd = db.get(BreakdownVersion, row.breakdown_id)
    for scene in bd.data["scenes"]:
        for shot in scene["shots"]:
            shot["speaker"] = "Mom"
    flag_modified(bd, "data")
    db.commit()


def _splice(app, db, setup, word):  # noqa: F811
    user = db.query(User).filter_by(email="ed@example.com").one()
    project = db.get(Project, setup["project"])
    decision = {"tool": "splice_word", "clip_id": "c1", "word": word}
    return director_tools.run(db, user, project, decision, app.state.storage)


def test_wrong_brand_is_spliced_from_same_voice(app, db, editor, setup, clip, monkeypatch):  # noqa: F811
    _said(monkeypatch, "I love fomo.", "I love Fobo.")
    _take(app, db, editor, setup, clip)
    _take(app, db, editor, setup, clip)
    row = db.get(ProjectClip, clip["id"])
    first, second = db.query(ClipTake).filter_by(clip_id=row.id).order_by(ClipTake.number)
    row.picked_take_id = second.id
    db.commit()
    _one_voice(db, row)

    state = word_splice.state(db, row)
    assert state["can_splice"] == [{"word": "fomo", "at": [1.37, 1.8]}] and not state["no_copy"]
    assert _splice(app, db, setup, "dip") == word_splice.NOT_BRAND
    assert _splice(app, db, setup, "fomo") == "Spliced “fomo” into c1 from c1."
    db.expire_all()
    (done,) = word_splice.spliced(db.get(ClipTake, second.id))
    assert (done["from_take"], done["at"], done["from"]) == (first.id, [1.37, 1.8], [1.37, 1.8])
    after = word_splice.state(db, db.get(ProjectClip, row.id))
    assert after["splices"] == [{"word": "fomo", "at": [1.37, 1.8], "from_take_id": first.id}]
    assert after["can_splice"] == []
    assert _splice(app, db, setup, "fomo") == word_splice.NOTHING.format(w="fomo", c="c1")
    assert word_splice.labels(row, db.get(ClipTake, second.id)) == ["c1/splice:1.37-1.8"]
    db.get(ProjectClip, row.id).approved = True  # the clip's take, approved as a person would
    db.commit()
    cut = editor.post(f"/projects/{setup['project']}/video")  # the stitch runs with it
    assert cut.status_code == 201, cut.text
    db.expire_all()
    from app.models.clips import FinalVideo

    (final,) = db.query(FinalVideo).filter_by(project_id=setup["project"]).all()
    assert "c1/splice:1.37-1.8" in final.cut_ins  # a new splice shows as changes waiting


def test_no_clean_copy_is_refused(app, db, editor, setup, clip, monkeypatch):  # noqa: F811
    _said(monkeypatch, "I love fomo.", "I love Fobo.")
    _take(app, db, editor, setup, clip)
    _take(app, db, editor, setup, clip)
    row = db.get(ProjectClip, clip["id"])
    row.picked_take_id = max(t.id for t in db.query(ClipTake).filter_by(clip_id=row.id))
    db.commit()  # the fixture's clip has two speakers: no copy is surely the same voice
    assert word_splice.state(db, row)["no_copy"] == [{"word": "fomo", "at": [1.37, 1.8]}]
    assert _splice(app, db, setup, "fomo") == word_splice.NO_COPY.format(w="fomo")


@pytest.mark.parametrize(("copy", "fits"), [([2.0, 2.44], True), ([2.0, 2.36], True),
                                             ([2.0, 2.6], False), ([2.0, 2.3], False)])  # fmt: skip
def test_a_copy_fits_only_within_the_speed_limit(copy, fits):
    assert word_splice._fits([1.0, 1.4], copy) is fits  # 0.4 s, give or take 15%


FFMPEG = ["ffmpeg", "-v", "error", "-y"]


def _tone(folder, name, hz, seconds=3):
    path = folder / name
    picture = ["-f", "lavfi", "-i", "color=c=red:s=64x64:r=24"]
    sound = ["-f", "lavfi", "-i", f"sine=frequency={hz}:sample_rate=44100"]
    out = ["-t", str(seconds), "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run([*FFMPEG, *picture, *sound, *out], check=True)  # noqa: S603 - our own args
    return path.read_bytes()


def _level(video: bytes, folder, start, end, band: str) -> float:
    """The loudest RMS of `band` (a highpass or lowpass) between start and end, in dB."""
    path = folder / "probe.mp4"
    path.write_bytes(video)
    window = ["-ss", str(start), "-t", str(end - start), "-i", str(path)]
    measure = ["-af", f"{band},astats=metadata=0", "-f", "null", "-"]
    done = subprocess.run(["ffmpeg", "-v", "info", *window, *measure],  # noqa: S603, S607
                          capture_output=True, text=True, check=True)  # fmt: skip
    # ffmpeg can interleave another line's text before it (" VideoHandlerRMS level dB: …"),
    # so the number is found by its label; -inf (silence) lines don't match
    levels = [float(m.group(1)) for x in done.stderr.splitlines()
              if (m := re.search(r"RMS level dB:\s*(-?[\d.]+)", x))]  # fmt: skip
    return max(levels) if levels else -200.0


def test_the_stitch_puts_the_copy_over_the_wrong_word_and_keeps_the_rest(tmp_path):
    low, high = _tone(tmp_path, "low.mp4", 300), _tone(tmp_path, "high.mp4", 2000)
    out = word_splice.apply(low, [{"at": [1.0, 1.6], "from": [0.5, 1.1], "from_take": 9}],
                            lambda take_id: high)  # fmt: skip
    hi, lo = "highpass=f=1500", "lowpass=f=600"
    assert _level(out, tmp_path, 1.1, 1.5, hi) > -30  # the copy is heard over the word
    assert _level(out, tmp_path, 1.1, 1.5, lo) < -40  # and the wrong word isn't
    assert _level(out, tmp_path, 0.2, 0.8, lo) > -30  # the rest of the take is as it was
    assert _level(out, tmp_path, 0.2, 0.8, hi) < -40
    assert _level(out, tmp_path, 2.0, 2.8, lo) > -30


def test_with_no_clean_copy_a_director_run_redoes_with_how_the_brand_is_said(
    app, db, owner, editor, monkeypatch
):
    """The fallback: the only take says the brand wrong, so there's no copy to splice; the
    take is made again with the words check's note (how it's said, never the wrong word)."""
    from tests.test_director import _made, _run

    notes = []

    def hear(path, job):  # the first take says the brand wrong, every other one says it right
        lines = [x["text"] for x in job["lines"]]
        if not notes:
            lines = [f"{lines[0]} I love Fobo.", *lines[1:]]
        notes.append(job.get("prompt", ""))
        return [{"start": 2.0 * i + 0.5, "end": 2.0 * i + 1.8, "text": t, "speaker": None,
                 "words": _spread(t, 2.0 * i + 0.5, 2.0 * i + 1.8)}
                for i, t in enumerate(lines)]  # fmt: skip

    monkeypatch.setattr("app.providers.fake_local.hear_take", hear)
    monkeypatch.setattr("app.item_checks.on", lambda: True)  # as on the test site's stand-ins
    pid = _made(app, owner, editor, db)
    editor.post(f"/projects/{pid}/director")
    _run(app, db, ticks=150)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    takes = [j for j in db.query(Job).filter(Job.project_id == pid).order_by(Job.id)
             if j.input.get("step") == "clip_take"]  # fmt: skip
    redo = takes[1].input["input"]["prompt"]
    assert "Change from the last take: Say fomo as" in redo  # told how it's said
    shown = {j["id"]: j for j in owner.get("/jobs").json()}  # Needs you's own read
    assert shown[takes[1].id]["note"] == ""  # the director's note, never quoted as a person's
    assert takes[1].input["by_director"] is True
    assert not any(t["result"].startswith("Spliced") for t in out["turns"])


def test_the_stand_in_splices_when_a_clean_copy_was_found():
    from app import director

    found = [{"word": "fomo", "at": [1.37, 1.8]}]
    c2 = {"clip_id": "c2", "stale": False, "picked_take_id": 7, "muted": [],
          "takes": [{"id": 7, "number": 1, "verdict": "flagged", "notes": []}],
          "splices": [], "no_copy": [], "can_splice": found}  # fmt: skip
    state = {"being_made": False, "held_for_owner": False, "treatment": "done", "shots": "made",
             "missing_looks": [], "stills": {"frames": 1, "drawn": 1}, "clips": [c2],
             "cut": "made", "allowed": {"redraws_used": {}, "watches_left": 1}}  # fmt: skip
    move = director.choose(state)
    assert (move["tool"], move["clip_id"], move["word"]) == ("splice_word", "c2", "fomo")
