"""A full-screen UGC talker is filmed on Omni 1.2 (Reed, 9 Nov: "Full screen UGC should be
omni, yes. Meaning the talking head is filmed in omni"): their lines said on camera in their
own Omni pieces, no voice-over and no HeyGen take; the B-roll laid over their picture, silent;
a corner presenter stays HeyGen. Stand-ins only: no paid calls."""

from decimal import Decimal

import pytest

from app import cut, cut_render, director_song, host, model_map, narration, one_frame, talker
from app.breakdown import video_model
from app.catalogue import get_model
from app.models.clips import ClipTake, ProjectClip
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from app.models.script_library import Script, ScriptDraft
from app.providers.fake_local import mp4
from app.routes import estimate
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import _run

LINES = (
    "MARCUS: I owe my brother-in-law a public apology.\n"
    "MARCUS: Every Thanksgiving I laughed at him for staring at his phone at the table.\n"
    "MARCUS: Called him the crypto guy. In front of everybody.\n"
    "MARCUS: This year he finally showed me. Small trades on fomo, ten minutes a day.\n"
    "MARCUS: Then he showed me the balance.\n"
    "MARCUS: I didn't say a word for the rest of dinner.\n"
    "MARCUS: I downloaded it in the parking lot.\n"
    "MARCUS: Danny, you were right. Link's in my bio."
)  # fmt: skip (video 315's script)
SAYS = "Marcus says"  # a talker piece's line in the stand-in's clip prompt
VOICE = "a man in his late 30s, mid-low and a little gravelly, plain everyday American"


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def _video(db, owner, presenter=None) -> Project:
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": LINES,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    video.presenter = presenter
    db.commit()
    return video


def _made(app, db, owner, presenter=None) -> Project:
    video = _video(db, owner, presenter)
    _run(app, db, ticks=200)
    fs = db.query(Freestyle).filter_by(project_id=video.id).one()
    assert owner.get(f"/freestyles/{fs.id}").json()["status"] == "delivered"
    return video


def _jobs(db, video, step) -> list[Job]:
    return [j for j in db.query(Job).filter(Job.project_id == video.id).order_by(Job.id)
            if j.input.get("step") == step]  # fmt: skip


def _clips(db, video) -> list[ProjectClip]:
    return list(db.query(ProjectClip).filter_by(project_id=video.id).order_by(ProjectClip.id))


def _sent(db, row: ProjectClip) -> dict:
    return db.get(Job, db.get(ClipTake, row.picked_take_id).job_id).input


def test_a_full_screen_ugc_talker_says_their_lines_in_their_own_omni_pieces(app, db, owner):
    video = _made(app, db, owner)
    assert talker.omni(db, video) and narration.video_kind(db, video) == "story"
    assert not _jobs(db, video, "song_take") and not video.song_take_id  # no voice-over
    assert not _jobs(db, video, host.STILL) and not _jobs(db, video, host.PIECE)  # no HeyGen
    pieces = [r for r in _clips(db, video) if SAYS in r.prompt]
    assert len(pieces) > 1  # 8 lines, about 22 s: in pieces of up to 15 s
    for row in pieces:  # lips, voice and room from one Omni take
        sent = _sent(db, row)
        assert sent["model"] == model_map.OMNI and sent["input"]["duration"] <= 15
        assert model_map.SPOKEN.split("{")[0] in sent["input"]["prompt"]
    tl, _ = cut.timeline(db, video)  # the talker's pieces are the cut, in script order
    assert [p["clip_id"] for p in tl["pieces"]] == [r.clip_id for r in pieces]


def test_a_corner_presenter_stays_heygen_over_our_voice_track(app, db, owner):
    video = _made(app, db, owner, presenter="corner")
    assert not talker.omni(db, video) and narration.video_kind(db, video) == "narrated"
    (voice,) = [j for j in _jobs(db, video, "song_take") if j.kind == "speech"]
    assert voice.input["model"] == narration.MINIMAX
    (piece,) = _jobs(db, video, host.PIECE)
    assert (piece.input["model"], piece.provider) == (talker.MODEL, "heygen")
    for row in _clips(db, video):  # nobody speaks on Omni: the voice track is the sound
        assert model_map.SILENT.split("{")[0] in _sent(db, row)["input"]["prompt"]
    video.presenter = None  # talks to camera now, but its voice track was made: still HeyGen
    assert not talker.omni(db, video) and talker.on(db, video)


def test_the_b_roll_is_silent_and_laid_over_the_talker_while_they_talk(app, db, owner, tmp_path):
    video = _made(app, db, owner)
    broll = [r for r in _clips(db, video) if SAYS not in r.prompt]
    assert broll
    for row in broll:  # nobody speaks in it
        assert model_map.SILENT.split("{")[0] in _sent(db, row)["input"]["prompt"]
    tl, _ = cut.timeline(db, video)
    laid = cut.laid_over(tl)  # over the picture, never a piece of its own
    assert {o["take_id"] for o in laid} == {r.picked_take_id for r in broll}
    assert not {p["clip_id"] for p in tl["pieces"]} & {r.clip_id for r in broll}
    recipe = cut_render.recipe(db, video, tl)
    assert [(o["start"], o["length"]) for o in recipe["over"]] == [
        (o["start"], o["length"]) for o in laid]  # fmt: skip
    out = cut_render.cut_away([(mp4("9:16", 3), 1.0, 1.5)], mp4("9:16", 4, sound=True))
    (tmp_path / "out.mp4").write_bytes(out)
    assert cut_render._probe(tmp_path, "out.mp4", "a:0", "codec_name")  # their voice runs on
    assert cut_render.seconds(out) == pytest.approx(4, abs=0.2)


def test_each_piece_says_the_voice_line_and_opens_on_one_still(app, db, owner, monkeypatch):
    monkeypatch.setattr("app.voices.on_omni", lambda db, project: [(["Marcus"], VOICE)])
    video = _made(app, db, owner)
    rows = _clips(db, video)
    first, *more = pieces = [r for r in rows if SAYS in r.prompt]
    assert one_frame.shared(db, video) == {r.clip_id: first.clip_id for r in more}  # #1494
    said = f"Marcus's voice: {VOICE}."  # #1487: word for word in every piece
    assert all(said in _sent(db, r)["input"]["prompt"] for r in pieces)
    assert all(said not in r.prompt for r in rows if r not in pieces)
    opening = {_sent(db, r)["files"]["reference_images"][0] for r in pieces}
    assert len(opening) == 1  # the one still, at rest


def test_each_piece_is_trimmed_to_its_words_at_the_cut(app, db, owner, monkeypatch):
    video = _made(app, db, owner)
    heard = [{"word": "I", "start": 0.9, "end": 1.1}, {"word": "lot", "start": 2.0, "end": 2.4}]
    monkeypatch.setattr("app.cut._heard", lambda db, take: heard)
    tl = cut.base(db, video)
    for p in tl["pieces"]:  # a breath before the first word, and after the last
        assert (p["from"], p["whole"]) == (round(0.9 - cut.LEAD, 2), False)
        assert p["end"] - p["start"] == pytest.approx(2.4 + cut.TAIL - p["from"], abs=0.01)
    assert tl["pieces"][1]["start"] == tl["pieces"][0]["end"]  # no gap between them


def test_the_estimate_prices_the_talker_on_omni_not_heygen_and_a_voice_track(
    db, owner, monkeypatch
):
    video = _video(db, owner)  # quoted before its plan
    draft = db.get(ScriptDraft, video.script_draft_id)
    script = db.get(Script, draft.script_id)
    m = video_model(video, script.look, script.kind)
    assert (m.id, m.take_resolution) == (model_map.OMNI, "720p")
    assert get_model(m.id).price.usd["720p"] == Decimal("0.11")  # about $0.11 a second
    said = narration.longest(db, draft, video)
    talks = estimate.quoted_seconds(db, draft, video)
    monkeypatch.setattr(director_song, "price", lambda db, draft: Decimal(10_000))
    omni = estimate.run_price(db, draft, video)
    assert host.run_price(db, draft, said, video) == 0 and omni < 10_000  # no HeyGen, no voice
    video.presenter = "corner"
    assert host.run_price(db, draft, said, video) > 0  # the corner's HeyGen take
    assert estimate.quoted_seconds(db, draft, video) == talks - said  # its pieces, on Omni
    assert estimate.run_price(db, draft, video) > 10_000  # and our voice track


def test_a_sitting_talker_in_two_short_pieces_is_advised_into_one():
    shot = {"line": "Hi.", "character_ids": ["char:1"], "place_id": "place:1", "screen_ids": []}
    data = {"scenes": [{"heading": "INT. CAR", "shots": [
        {**shot, "id": "1.1"}, {**shot, "id": "1.2", "line": None, "character_ids": []},
        {**shot, "id": "1.3"}]}],
        "clips": [{"id": "c1", "shot_ids": ["1.1"], "seconds": 6},
                  {"id": "c2", "shot_ids": ["1.2"], "seconds": 3},
                  {"id": "c3", "shot_ids": ["1.3"], "seconds": 7}]}  # fmt: skip
    (said,) = talker.fewer(data, 15)  # B-roll between them is laid over, never a reason
    assert said.startswith("Advice: clips c1 and c3") and "13 s" in said
    assert talker.fewer(data, 12) == []  # one piece couldn't hold both
