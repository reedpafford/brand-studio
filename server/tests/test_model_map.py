"""Reed's model map (4 Nov, changed 6 Nov: a UGC talker in one spot on HeyGen, everything else
in UGC on Omni 1.2, the animated styles on Seedance) and the v6 model moves: each clip's model
and why; the director's per-clip model and its
settings switch from the chat (a person's own choice stays); how a presenter appears, per video
(Reed's L3). Stand-ins only: no paid calls."""

import pytest

from app import director_tools, host, model_map, settings_move, talker
from app.breakdown import video_model
from app.catalogue import get_model
from app.clip_takes import take_input
from app.models.accounts import User
from app.models.clips import ProjectClip
from app.models.freestyles import Freestyle
from app.models.projects import Project
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import _run
from tests.test_talker import LINES


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


@pytest.fixture
def ugc(app, db, owner):
    """A delivered UGC presenter video: a HeyGen talker and its B-roll."""
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": LINES,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    _run(app, db, ticks=200)
    return db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                  execution_options={"see_hidden": True})  # fmt: skip


def _rows(db, video) -> dict[str, ProjectClip]:
    return {r.clip_id: r for r in db.query(ProjectClip).filter_by(project_id=video.id)}


def _move(app, db, video, run=None, **decision) -> str:
    user = db.get(User, video.created_by_id)
    return director_tools.run(db, user, video, decision, app.state.storage, run)


def _noted(db, video, text: str) -> dict:
    """A person's note on the video's newest run (its Note N), and that run."""
    from app import director
    from app.db import utcnow

    run = director.turns(db, video)[-1].input[director.RUN]
    video.director_chat = [
        *(video.director_chat or []),
        {"text": text, "by": video.created_by_id, "at": utcnow().isoformat(), "run": run["id"]},
    ]
    db.commit()
    return run


def test_omni_1_2_replaces_1_1_and_makes_the_realistic_style(owner):
    """Reed, 6 Nov: "1.2 replaces 1.1"; "keep seedance for the animated and expression-full ones
    for now. Omni is more for the realistic stuff": UGC on Omni, the animated styles on
    Seedance (2.5 for House, Disney Pixar and songs; 2.0 for the rest)."""
    omni = get_model(model_map.OMNI)
    assert get_model("gemini-omni-1.1") is None
    assert (omni.duration.min, omni.duration.max, omni.take_resolution, omni.audio) == (
        3, 15, "720p", "always")  # fmt: skip
    assert model_map.OMNI in {m["id"] for m in owner.get("/models").json()}
    for kind in ("narrated", "story"):
        assert video_model(look="ugc", kind=kind).id == model_map.OMNI, kind
        for look in ("skeleton", "claymation", "zack-d", "dr-pickle"):
            assert video_model(look=look, kind=kind).id == "seedance-2.0", (look, kind)
    for look in ("house", "disney-pixar"):
        assert video_model(look=look, kind="story").id == "seedance-2.5", look
    assert video_model(look="skeleton", kind="song").id == "seedance-2.5"  # songs lip-sync


AUDIO = "Audio: only the spoken lines and kitchen sounds. No music, background music, BGM."
SEEDANCE_SHAPED = (
    f"{AUDIO}\nReferences: [Image1] is the first frame. It sets the opening composition only. "
    "[Image2] is Theo.\nShots (hard cuts):\nShot 1 | 0-4 s. Theo lifts the bowl. No one "
    f"speaks.\n{AUDIO}"
)


def test_omni_reads_its_own_prompt_words_and_two_people(owner):
    """QA on #1394, docs/prompting/omni-1.2.md's "must" rows: one short sound line instead of
    Seedance's two; the opening still a guide, never "the first frame"; references named in
    words by order; one continuous shot asked for; 2 people a clip, the rest said in words."""
    from app.clip_takes import _out

    omni = get_model(model_map.OMNI)
    asked = {"prompt": SEEDANCE_SHAPED, "duration": 20, "resolution": "480p",
             "aspect_ratio": "9:16", "generate_audio": False}  # fmt: skip
    sent, files = model_map.fit(omni, asked, {"reference_images": [11, 12]})
    said = sent["prompt"]
    assert "Audio:" not in said and "[Image" not in said and said.count("Sound:") == 1
    assert said.startswith("References: the first reference picture guides the opening picture "
                           "(not an exact first frame). It sets")  # fmt: skip
    assert "the second reference picture is Theo." in said
    assert said.endswith(f"{model_map.ONE_SHOT}\n" + model_map.SILENT.format(room="kitchen sounds"))
    assert (sent["duration"], sent["resolution"], files) == (
        15,
        "720p",
        {"reference_images": [11, 12]},
    )
    assert "generate_audio" not in sent
    two = SEEDANCE_SHAPED.replace("No one speaks.\n", 'Theo: "Mm."\nShot 2 | 4-6 s. Dad nods.\n')
    spoken = model_map.fit(omni, {**asked, "prompt": two, "generate_audio": True}, {})[0]["prompt"]
    assert model_map.ONE_SHOT not in spoken
    assert spoken.endswith(model_map.SPOKEN.format(room="kitchen sounds"))
    cast = ["frame:1", "char:1", "char:15", "char:150", "screen:2"]
    assert model_map.unsent_pictures(model_map.OMNI, cast) == ("char:150",)
    assert model_map.unsent_pictures("seedance-2.5", cast) == ()
    # Past Omni's six pictures, a place, then the opening still, never a product (video 284)
    full = ["frame:1", "char:1", "char:2", "char:3", "place:3", "screen:2", "screen:7", "prop:5"]
    assert model_map.unsent_pictures(model_map.OMNI, full) == ("char:3", "place:3")
    screens = ["frame:1", "char:1", "char:2", "screen:1", "screen:2", "screen:3", "screen:4"]
    assert model_map.unsent_pictures(model_map.OMNI, screens) == ("frame:1",)
    assert not _out("char:15", ("char:150",)) and _out("char:150", ("char:",))


def test_the_ugc_sample_and_a_one_clip_freestyle_are_sent_as_omni_reads_them(db, owner):
    """QA on #1394: the UGC look sample goes at Omni's own 720p with its words, not 480p with
    Seedance's sound switch; its shown price stays as it was (prices frozen, Reed, 6 Nov). A
    one-clip Freestyle in UGC sends no sound switch either."""
    from app import look_samples
    from app.credits import estimate
    from app.models.freestyles import Freestyle
    from app.routes.freestyles import _job_input

    clip = look_samples.clip_input("ugc", 1, 7, "Sam")
    sent = clip["input"]
    assert clip["model"] == model_map.OMNI and sent["resolution"] == "720p"
    assert clip["fit_images_to"] == 1280 and clip["files"] == {"reference_images": [7]}
    assert "generate_audio" not in sent and "[Image" not in sent["prompt"]
    assert ". The first reference picture guides the opening picture" in sent["prompt"]
    quoted = look_samples.clip_input("ugc", 0, 0, "", quote=True)
    assert quoted["input"]["resolution"] == "480p"  # the price reads it as it always has
    ws = 1
    assert look_samples.price(db, ws, "ugc") > estimate(db, ws, "video", 5, clip)
    quick = _job_input(Freestyle(id=1, look="ugc", shape="9:16", brand_id=1), ["Hi, I'm Sam."])
    assert quick["model"] == model_map.OMNI and "generate_audio" not in quick["input"]


def test_omni_takes_get_its_own_inputs(app, db, owner, ugc):
    """docs/prompting/omni-1.2.md: a duration, no sound switch, references named in words; a
    narrated video's B-roll says no one speaks."""
    clip = next(r for c, r in _rows(db, ugc).items() if c not in talker.clips(db, ugc))
    assert _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=talker.MODEL,
                 why="x") == model_map.WHOLE_TAKE  # fmt: skip
    job = take_input(db, ugc, clip)
    sent = job["input"]
    assert job["model"] == model_map.OMNI
    assert set(sent) == {"prompt", "duration", "resolution", "aspect_ratio"}
    assert sent["resolution"] == "720p" and 3 <= sent["duration"] <= 15
    said = sent["prompt"].splitlines()
    assert "[Image" not in sent["prompt"] and not any(x.startswith("Audio:") for x in said)
    assert said[-1].startswith("Sound: no one speaks in this shot") and "No music" in said[-1]
    assert len(job["files"].get("reference_images", [])) <= 6


def test_a_clip_or_take_still_on_omni_1_1_reads_as_the_videos_model_not_a_crash(
    app, db, owner, ugc
):
    """QA on #1394: 1.1 left the catalogue, so a clip or take that still names it (before
    n43 moves it) shows the video's model and the take's old id, never a 500."""
    from app.models.clips import ClipTake

    clip = next(r for c, r in _rows(db, ugc).items() if c not in talker.clips(db, ugc))
    clip.model = {"id": "gemini-omni-1.1", "why": "A face kept.", "by": "director"}
    take = db.get(ClipTake, clip.picked_take_id)
    take.made_with = {**take.made_with, "model": "gemini-omni-1.1"}
    db.commit()
    got = owner.get(f"/projects/{ugc.id}/clips")
    assert got.status_code == 200
    row = next(c for c in got.json() if c["clip_id"] == clip.clip_id)
    assert row["model"]["id"] == model_map.OMNI and row["model"]["by"] == "map"
    assert next(t for t in row["takes"] if t["id"] == take.id)["model"] == "gemini-omni-1.1"


def test_a_ugc_talker_in_one_spot_is_heygen_one_who_moves_and_the_broll_are_omni(
    app, db, owner, ugc
):
    """Reed, 6 Nov: a UGC talker in one spot the whole time (talks to camera, or in a corner)
    is HeyGen Avatar IV with our MiniMax voice, and Omni 1.2 makes only the B-roll; a talker
    who moves around in the story (acts) is made on Omni 1.2; UGC's B-roll is always Omni 1.2."""
    from app import narration
    from app.models.script_library import ScriptDraft
    from app.models.songs import SongTake

    rows, said = _rows(db, ugc), talker.clips(db, ugc)
    talking, broll = rows[sorted(said)[0]], next(r for c, r in rows.items() if c not in said)
    draft = db.get(ScriptDraft, ugc.script_draft_id)

    def made_on(clip) -> str:
        return model_map.why(db, ugc, clip)["id"]

    def move(clip, model) -> str:
        return _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=model, why="x")

    shown = {c["clip_id"]: c["model"] for c in owner.get(f"/projects/{ugc.id}/clips").json()}
    assert host.how(ugc) == "talks"  # the UGC style's start: in one spot
    assert shown[talking.clip_id]["id"] == talker.MODEL  # cut from the one HeyGen take
    assert shown[broll.clip_id] | {"why": ""} == {"id": model_map.OMNI, "name": "Gemini Omni 1.2",
                                                 "by": "map", "why": ""}  # fmt: skip
    piece = next(j for j in host._jobs(db, ugc).values() if j.input["step"] == host.PIECE)
    assert piece.input["model"] == talker.MODEL and piece.input["files"]["audio"]
    assert db.get(SongTake, ugc.song_take_id).voice in narration.MINIMAX_VOICES
    assert move(talking, model_map.OMNI) == model_map.SAYS_IT
    assert move(broll, "seedance-2.5") == model_map.REAL
    ugc.presenter = "corner"  # still in one spot: one HeyGen take keyed over the B-roll
    db.flush()
    assert host.on(db, ugc) and host.run_price(db, draft, 10, ugc) > 0
    assert made_on(broll) == model_map.OMNI
    ugc.presenter = "acts"  # moves around in the story: no HeyGen take, their shots on Omni
    db.flush()
    assert not host.on(db, ugc) and host.run_price(db, draft, 10, ugc) == 0
    assert made_on(talking) == made_on(broll) == model_map.OMNI
    assert take_input(db, ugc, talking)["model"] == model_map.OMNI  # its own take, on Omni
    assert move(talking, "seedance-2.0") == model_map.REAL


def test_a_ugc_presenter_in_one_spot_reads_in_the_minimax_voice_unless_one_is_chosen(
    app, db, owner, ugc, monkeypatch
):
    """Reed, 6 Nov: a talker in one spot the whole time is HeyGen with the MiniMax voice, so a
    UGC presenter in a corner gets the same default as one talking to camera, and the director
    is told (`minimax` in its `host`). A person's pick or the presenter's own saved voice still
    wins; a presenter who acts, or one in another style, keeps narration's default."""
    from app import director, director_song, narration

    for way in ("talks", "corner"):
        ugc.presenter = way
        db.flush()
        assert director_song._voice(db, ugc) == talker.VOICE, way
        assert director.video_state(db, ugc)["host"]["minimax"] is True, way
    ugc.presenter = "acts"
    db.flush()
    assert director_song._voice(db, ugc) == narration.VOICE
    ugc.presenter, ugc.look = "corner", "house"
    db.flush()
    assert director_song._voice(db, ugc) == narration.VOICE
    assert "minimax" not in director.video_state(db, ugc)["host"]
    ugc.look = "ugc"
    own = type("Presenter", (), {"id": 1, "voice_id": None, "voice_stock_key": "Roger"})()
    monkeypatch.setattr(host, "host_look", lambda db, p: own)  # their own saved voice
    assert director_song._voice(db, ugc) == "Roger"
    ugc.voice = "stock:English_Graceful_Lady"  # a person's pick, as the settings save it
    db.flush()
    assert director_song._voice(db, ugc) == "English_Graceful_Lady"


def test_the_animated_styles_clips_stay_on_seedance(app, db, owner, ugc):
    """Reed, 6 Nov: "keep seedance for the animated and expression-full ones for now": House
    and Disney Pixar on Seedance 2.5, Skeleton on 2.0. There the director may still put a
    realistic shot on Omni, its reason shown, and put it back."""
    clip = next(r for c, r in _rows(db, ugc).items() if c not in talker.clips(db, ugc))
    n = clip.clip_id.removeprefix("c")
    for look, model in (("house", "seedance-2.5"), ("disney-pixar", "seedance-2.5"),
                        ("skeleton", "seedance-2.0")):  # fmt: skip
        ugc.look = look
        db.flush()
        assert model_map.why(db, ugc, clip)["id"] == model_map.of_clip(ugc, clip).id == model
    whole = {"tool": "settings", "setting": "video_model", "model": model_map.OMNI}
    assert _move(app, db, ugc, **whole, why="Realer.") == model_map.off_map(ugc, model_map.OMNI)
    assert "Skeleton's videos are made on Seedance" in model_map.off_map(ugc, model_map.OMNI)
    assert _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=model_map.OMNI,
                 why=" ") == model_map.NO_REASON  # fmt: skip
    why = "A real phone video of the dog's bowl, the one realistic shot."
    moved = _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=model_map.OMNI,
                  why=why)  # fmt: skip
    assert moved.startswith(f"Clip {n} is made on Gemini Omni 1.2 now: up to"), moved
    assert "on Seedance 2.0)" in moved and why in moved
    assert model_map.why(db, ugc, clip) | {"by": ""} == {
        "id": model_map.OMNI, "name": "Gemini Omni 1.2", "why": why, "by": ""}  # fmt: skip
    back = _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=None, why="")
    assert back == f"Clip {n} is back on the video's Seedance 2.0."


def test_a_persons_setting_wins_and_the_directors_switch_says_its_price(app, db, owner, ugc):
    """The director moves a whole UGC video off Omni 1.2 only for a person's note (Reed's map,
    QA on #1394); its switch says the price first."""
    lite = {"tool": "settings", "setting": "video_model", "model": "seedance-1-lite"}
    assert _move(app, db, ugc, **lite, why="Cheaper.") == model_map.off_map(ugc, "seedance-1-lite")
    assert model_map.off_map(ugc, "seedance-1-lite").startswith("Refused: UGC's videos are made")
    said = _move(app, db, ugc, **lite, why="Note 1: asked in the chat.")
    assert said.startswith(
        "Switched the video model to Seedance 1 Lite. The switch is free; "
        "1 clip goes out of date; making what's left costs up to"  # the talker's are HeyGen's
    ), said
    assert "Undo puts back Auto" in said
    clips = owner.get(f"/projects/{ugc.id}/clips").json()
    chosen = next(c["model"] for c in clips if c["model"]["id"] == "seedance-1-lite")
    assert chosen["by"] == "director" and chosen["why"].startswith("Note 1: asked in the chat.")
    shown = owner.get(f"/projects/{ugc.id}/settings").json()
    assert shown["changes"][0] | {"at": ""} == {
        "field": "video_model", "was": None, "now": "seedance-1-lite", "by": "director",
        "why": "Note 1: asked in the chat.", "at": ""}  # fmt: skip
    undo = owner.post(f"/projects/{ugc.id}/settings", json={"video_model": None, "undo": True})
    assert undo.status_code == 200 and undo.json()["settings"]["video_model"] is None
    picked = owner.post(f"/projects/{ugc.id}/settings", json={"video_model": "seedance-2.0"})
    assert picked.json()["settings"]["changes"][0]["by"] == "person"
    db.refresh(ugc)
    again = _move(app, db, ugc, tool="settings", setting="video_model", model="seedance-1-lite",
                  why="")  # fmt: skip
    assert again.startswith("Refused:") and "their choice stays" in again
    broll = next(r for c, r in _rows(db, ugc).items() if c not in talker.clips(db, ugc))
    no = _move(app, db, ugc, tool="clip_model", clip_id=broll.clip_id, model="seedance-1-lite",
               why="")  # fmt: skip
    assert no.startswith("Refused:") and "their choice stays" in no
    assert (
        _move(app, db, ugc, tool="settings", setting="language", why="") == settings_move.LANGUAGE
    )


def test_how_the_presenter_appears_is_chosen_per_video(app, db, owner, ugc):
    assert host.how(ugc) == "talks" and talker.on(db, ugc)  # the UGC style's start
    shown = owner.get(f"/projects/{ugc.id}/settings").json()
    assert (shown["presenter"], shown["presenter_now"]) == (None, "talks")
    no = _move(app, db, ugc, tool="settings", setting="presenter", value="corner", why="")
    assert no == settings_move.PRESENTER  # nobody asked (video 240)
    run = _noted(db, ugc, "Put her in a corner over the B-roll.")
    said = _move(app, db, ugc, run, tool="settings", setting="presenter", value="corner",
                 why="Note 1: put her in a corner.")  # fmt: skip
    assert said.startswith(
        "The presenter now appears in a corner over the B-roll. The switch is "
        "free; the presenter's take is made again for it, up to"
    ), said
    assert said.endswith("Undo puts back the presenter as the style starts.")
    db.refresh(ugc)
    assert host.on(db, ugc) and not talker.on(db, ugc) and host.rows(db, ugc) == []  # its own
    assert "green" in host.still_input(db, ugc, host.HostPiece(number=0))["input"]["prompt"]
    acts = owner.post(f"/projects/{ugc.id}/settings", json={"presenter": "acts"})
    assert acts.status_code == 200 and acts.json()["settings"]["presenter_now"] == "acts"
    db.refresh(ugc)
    assert not host.on(db, ugc) and host.presents(db, ugc)
    assert _move(app, db, ugc, tool="host") == f"Refused: {host.ACTS}"
    bad = owner.post(f"/projects/{ugc.id}/settings", json={"presenter": "flies"})
    assert bad.status_code == 422


def test_a_narrated_video_keeps_its_narration_and_its_omni_broll_has_no_one_speaking(
    app, db, owner, ugc
):
    """Reed, 5 Nov: a narrated video keeps its narration throughout. Omni has no sound switch,
    so its B-roll prompt says no one speaks, the place's sound kept under the voice."""
    said = talker.clips(db, ugc)
    broll = next(r for c, r in _rows(db, ugc).items() if c not in said)
    prompt = take_input(db, ugc, broll)["input"]["prompt"]
    assert prompt.splitlines()[-1].startswith("Sound: no one speaks in this shot")
    shown = owner.get(f"/projects/{ugc.id}/settings").json()
    assert "narration_only" not in shown  # nothing to switch off: the narration runs throughout


def test_a_persons_narrator_voice_for_the_video_wins_over_the_directors(app, db, owner, ugc):
    """S5-02's voice Change: projects.voice is "stock:<key>" or "voice:<id>", set like any
    setting (Undo, logged); the narration is read in it whatever the director names."""
    from app import director_song

    url = f"/projects/{ugc.id}/settings"
    for bad in ("Roger", "stock:Nobody", "voice:99999"):
        assert owner.post(url, json={"voice": bad}).status_code == 422, bad
    set_ = owner.post(url, json={"voice": "stock:English_Graceful_Lady"})
    assert set_.status_code == 200 and set_.json()["settings"]["voice"] == (
        "stock:English_Graceful_Lady")  # fmt: skip
    assert set_.json()["settings"]["changes"][0]["by"] == "person"
    db.refresh(ugc)
    said = _move(app, db, ugc, tool="narration", voice="English_FriendlyPerson",
                 emotion="sad", why="")  # fmt: skip
    assert said.startswith("Making the narration"), said
    takes = sorted(director_song.song_takes.for_video(db, ugc), key=lambda t: -t.id)
    assert takes[0].voice == "English_Graceful_Lady"  # the person's, not the director's
    undo = owner.post(url, json={"voice": None, "undo": True})
    assert undo.status_code == 200 and undo.json()["settings"]["voice"] is None


def test_a_persons_voice_is_this_brands_and_not_a_removed_one(app, db, owner, ugc):
    """QA on #1327: another brand's voice and a removed voice are refused in plain words."""
    from app.db import utcnow
    from app.models.voices import Voice

    other = owner.post("/brands", json={"name": "Other Brand"}).json()["id"]
    theirs = Voice(workspace_id=ugc.workspace_id, brand_id=other, name="Theirs",
                   kind="cloned", provider="minimax", provider_voice_id="R8_X",
                   speech_model="minimax-speech-02-hd", cloned_at=utcnow(),
                   last_used_at=utcnow())  # fmt: skip
    gone = Voice(workspace_id=ugc.workspace_id, brand_id=ugc.brand_id, name="Gone",
                 kind="cloned", provider="minimax", provider_voice_id="R8_Y",
                 speech_model="minimax-speech-02-hd", cloned_at=utcnow(),
                 last_used_at=utcnow(), archived_at=utcnow())  # fmt: skip
    db.add_all([theirs, gone])
    db.commit()
    url = f"/projects/{ugc.id}/settings"
    refused = owner.post(url, json={"voice": f"voice:{theirs.id}"})
    assert refused.status_code == 422 and "voice:" not in refused.json()["detail"]
    removed = owner.post(url, json={"voice": f"voice:{gone.id}"})
    assert removed.status_code == 422 and "Gone was removed" in removed.json()["detail"]


def test_a_persons_presenter_stays_unless_they_ask(app, db, owner, ugc):
    """QA on #1327: a person's switch (or a value set before the log, e.g. a PATCH) stays
    theirs; the director may change it only for their note in the chat; Undo puts it back."""
    url = f"/projects/{ugc.id}/settings"
    assert owner.post(url, json={"presenter": "corner"}).status_code == 200
    db.refresh(ugc)
    no = _move(app, db, ugc, tool="settings", setting="presenter", value="acts", why="")
    assert no.startswith("Refused:") and "their choice stays" in no
    run = _noted(db, ugc, "Have her act in the story.")
    asked = _move(app, db, ugc, run, tool="settings", setting="presenter", value="acts",
                  why="Note 1: they asked for her acting in the story.")  # fmt: skip
    assert asked.startswith("The presenter now appears acting in the story")
    undo = owner.post(url, json={"presenter": "corner", "undo": True}).json()["settings"]
    assert undo["presenter"] == "corner"
    owner.patch(f"/projects/{ugc.id}", json={"aspect_ratio": "16:9"})
    db.refresh(ugc)
    assert ugc.settings_log[-1] | {"at": ""} == {
        "field": "aspect_ratio", "was": "9:16", "now": "16:9", "by": "person",
        "by_id": ugc.created_by_id, "why": "", "at": ""}  # fmt: skip
    shape = _move(app, db, ugc, tool="settings", setting="aspect_ratio", value="9:16", why="")
    assert "their choice stays" in shape


def test_before_the_plan_is_approved_only_a_persons_request_switches(
    app, db, owner, ugc, monkeypatch
):
    """Reed, 4 Nov: settings follow a person's request or the approved plan, never an
    unapproved one."""
    from app import settings_move

    monkeypatch.setattr("app.plans.status", lambda db, project: "ready")
    move = {"tool": "settings", "setting": "video_model", "model": "seedance-1-lite"}
    assert _move(app, db, ugc, **move, why="") == settings_move.NOT_YET
    asked = _move(app, db, ugc, **move, why="Note 2: they asked for Lite.")
    assert asked.startswith("Switched the video model to Seedance 1 Lite")


def test_the_cost_bar_prices_a_clip_on_its_own_model(app, db, owner, ugc):
    """QA on #1327: a clip still to make counts at its own model's price in what's left."""
    from app.routes.estimate import _stages

    clip = next(r for c, r in _rows(db, ugc).items() if c not in talker.clips(db, ugc))
    clip.picked_take_id = None
    db.flush()

    def left() -> float:
        return next(s.credits for s in _stages(db, ugc) if s.stage == "clips")

    on_omni = left()
    assert on_omni >= float(get_model(model_map.OMNI).credits_per_unit("720p")) * clip.seconds
    ugc.look = "house"  # an animated style, where the director may move a clip
    db.flush()
    on_seedance = left()
    assert _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model="seedance-1-lite",
                 why="A hand and the keys: Lite is enough.").startswith("Clip")  # fmt: skip
    assert left() < on_seedance


def test_undo_puts_back_how_the_presenter_appears_and_the_old_host(app, db, owner, ugc):
    """Undo of a person's switch: the style's start again, with the host made for it."""
    url = f"/projects/{ugc.id}/settings"
    made = len(host.rows(db, ugc))
    assert made and owner.post(url, json={"presenter": "corner"}).status_code == 200
    db.refresh(ugc)
    assert host.how(ugc) == "corner" and host.rows(db, ugc) == []  # its own take to make
    undo = owner.post(url, json={"presenter": None, "undo": True}).json()["settings"]
    assert (undo["presenter"], undo["presenter_now"]) == (None, "talks")
    db.refresh(ugc)
    assert len(host.rows(db, ugc)) == made


def test_the_narrator_is_the_persons_then_the_directors_then_the_videos_own(app, db, owner, ugc):
    """QA on #1327: projects.voice (a setting or a voice card's answer) wins; a removed one
    falls through to the director's pick, then the video's own voice."""
    from app import director_song
    from app.db import utcnow
    from app.models.voices import Voice

    def read(**decision) -> str:
        said = _move(app, db, ugc, tool="narration", why="", **decision)
        assert said.startswith("Making the narration"), said
        take = max(director_song.song_takes.for_video(db, ugc), key=lambda t: t.id)
        return take.voice

    gone = Voice(
        workspace_id=ugc.workspace_id,
        brand_id=ugc.brand_id,
        name="Gone",
        kind="cloned",
        provider="minimax",
        provider_voice_id="R8_G",
        speech_model="minimax-speech-02-hd",
        cloned_at=utcnow(),
        last_used_at=utcnow(),
    )
    db.add(gone)
    db.commit()
    url = f"/projects/{ugc.id}/settings"
    assert owner.post(url, json={"voice": "stock:English_Graceful_Lady"}).status_code == 200
    db.refresh(ugc)
    assert read(voice="English_FriendlyPerson", emotion="calm") == "English_Graceful_Lady"
    _run(app, db, ticks=10)  # that narration is made
    ugc.voice, gone.archived_at = f"voice:{gone.id}", utcnow()  # removed since it was chosen
    db.commit()
    assert read(voice="English_Upbeat_Woman", emotion="sad") == "English_Upbeat_Woman"


def _dialogue(db, editor, look: str, mark: str = "") -> tuple[Project, ProjectClip, ProjectClip]:
    """A dialogue video in `look`: clip c1 with MOM speaking (on camera, or as `mark` says in
    her script label: " (O.S.)"), c2 with nobody."""
    from app.models.breakdowns import BreakdownVersion

    brand = editor.get("/brands").json()[0]["id"]
    made = {"brand_id": brand, "name": "Dip", "planned_seconds": 10}
    pid = editor.post("/projects", json=made).json()["id"]
    text = f"MOM{mark}: Where is your money?\nShe sighs."
    editor.put(f"/projects/{pid}/script", json={"text": text})
    video = db.get(Project, pid)
    video.look = look
    shot = {"camera": "Close", "seconds": 4, "character_ids": [], "place_id": None, "moment": None,
            "screen_ids": [], "script_lines": [], "reaction": None}  # fmt: skip
    data = {"hook": "", "scenes": [{"id": 1, "heading": "KITCHEN", "look": "", "shots": [
        {**shot, "id": "1.1", "speaker": "MOM", "line": "Where is your money?",
         "action": "Mom asks.", "script_lines": [1]},
        {**shot, "id": "1.2", "speaker": None, "line": None, "action": "She sighs."}]}],
        "clips": [{"id": "c1", "shot_ids": ["1.1"], "seconds": 4, "seam": ""},
                  {"id": "c2", "shot_ids": ["1.2"], "seconds": 4, "seam": ""}]}  # fmt: skip
    bd = BreakdownVersion(project_id=pid, script_version=1, source="claude", data=data)
    db.add(bd)
    db.flush()
    rows = [ProjectClip(project_id=pid, breakdown_id=bd.id, clip_id=c, seconds=4, prompt="p")
            for c in ("c1", "c2")]  # fmt: skip
    db.add_all(rows)
    db.commit()
    return video, *rows


def test_a_spoken_shot_on_a_style_that_cant_lip_sync_is_made_on_its_seedance_that_can(db, editor):
    """The critic's report (5.7): Claymation, Skeleton and Zack D offer on-camera dialogue on
    Seedance 2.0, which can't lip-sync. A clip where someone speaks on camera is made on
    Seedance 2.5, with the reason shown; a clip with nobody speaking stays on the style's 2.0."""
    video, spoken, quiet = _dialogue(db, editor, "claymation")
    assert video_model(video).id == "seedance-2.0" and not video_model(video).lip_sync
    assert model_map.of_clip(video, spoken).id == "seedance-2.5"
    said = model_map.why(db, video, spoken)
    assert (said["id"], said["by"]) == ("seedance-2.5", "map")
    assert said["why"] == model_map.LIP_SYNCED.format(was="Seedance 2.0", now="Seedance 2.5")
    assert said["why"].startswith("Someone speaks on camera here and Seedance 2.0 can't lip-sync")
    assert take_input(db, video, spoken)["model"] == "seedance-2.5"  # the take itself
    assert model_map.of_clip(video, quiet).id == "seedance-2.0"  # nobody speaks: unchanged
    assert model_map.why(db, video, quiet)["id"] == "seedance-2.0"


def test_a_lip_syncing_style_a_persons_model_and_a_clips_own_model_stay_as_they_are(db, editor):
    video, spoken, _ = _dialogue(db, editor, "disney-pixar")
    assert model_map.of_clip(video, spoken).id == "seedance-2.5"  # its own default lip-syncs
    assert model_map.lip_synced(video, spoken) is None
    clay, said, _ = _dialogue(db, editor, "claymation")
    said.model = {"id": "seedance-1-lite", "why": "A hand.", "by": "director"}
    assert model_map.of_clip(clay, said).id == "seedance-1-lite"  # the clip's own model
    said.model = None
    clay.video_model = "seedance-2.0"
    settings_move.log(clay, db.get(User, clay.created_by_id), "video_model", None, "seedance-2.0",
                      "person")  # fmt: skip
    assert model_map.of_clip(clay, said).id == "seedance-2.0"  # a person's own choice stays


@pytest.mark.parametrize("mark", [" (O.S.)", " (O.C.)", " (V.O.)", " (ON PHONE)", " (PRE-LAP)"])
def test_a_line_said_off_camera_never_moves_to_a_lip_sync_model(db, editor, mark):
    """QA on #1404: "(O.S.)", "(ON PHONE)" and the like are heard, not seen: no lips to sync,
    so the clip stays on the style's own Seedance (its take keeps its sound as before)."""
    video, spoken, _ = _dialogue(db, editor, "claymation", mark)
    assert model_map.of_clip(video, spoken).id == "seedance-2.0", mark


def test_a_style_whose_guide_says_no_lip_sync_keeps_its_own_seedance(db, editor, monkeypatch):
    """A guide opts out with `lip_sync: no` (Paper's puppets illustrate a narration, flap
    mouths): its speakers stay on its own Seedance. Every guide without the key keeps it on."""
    from app import guides

    assert guides.style("paper")["lip_sync"] and guides.style("claymation")["lip_sync"]
    video, spoken, _ = _dialogue(db, editor, "claymation")
    real = guides.style
    monkeypatch.setattr(guides, "style", lambda i: {**real(i), "lip_sync": False})
    assert model_map.of_clip(video, spoken).id == "seedance-2.0"


def test_a_clip_made_on_another_model_is_asked_charged_and_recorded_at_what_that_model_makes(
    app, db, owner, ugc
):
    """Reed (accurate spend): a 3 s clip fitted to Omni 1.2, moved to a Seedance whose shortest
    clip is 4 s, was quoted, charged and recorded at 3 s while it was asked for (and billed)
    at 4. It's quoted, charged and recorded at the seconds it's asked for on its own model:
    Another take, the director's remake and Change this clip alike."""
    from decimal import Decimal

    from app.clip_takes import take_credits
    from app.credits import estimate
    from app.models.jobs import Job

    lite = get_model("seedance-1-lite")
    assert (model_map.billed(lite, 3), model_map.billed(lite, 20)) == (4, 12)
    assert model_map.billed(get_model(model_map.OMNI), 3) == 3
    clip = next(r for c, r in _rows(db, ugc).items() if c not in talker.clips(db, ugc))
    ugc.look = "house"  # an animated style, where the director may move a clip
    db.flush()
    assert _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=lite.id,
                 why="A hand and the keys: Lite is enough.").startswith("Clip")  # fmt: skip
    clip.seconds = 3
    db.commit()
    asked = take_input(db, ugc, clip)
    assert (asked["model"], asked["input"]["duration"]) == (lite.id, 4)
    job = {"model": lite.id, "input": {"resolution": model_map.resolution(lite)}}
    four = estimate(db, ugc.workspace_id, "video", Decimal(4), job)
    assert take_credits(db, ugc, clip) >= four  # (with its watch, when watches are on)
    from app import change

    assert change._draw(db, ugc, clip, check=False)[2] == 4  # "Change this clip": its new take
    assert change._then(db, ugc, clip, check=False) >= four  # quoted at 4 s too (QA on #1425)
    made = owner.post(f"/projects/{ugc.id}/clips/{clip.id}/generate")
    assert made.status_code == 201, made.text
    assert db.get(Job, made.json()["id"]).credits == four  # charged, and so recorded, at 4 s


def test_the_director_never_switches_how_the_presenter_appears_unasked(app, db, owner, ugc):
    """Video 240 (7 Nov, T32): the director switched its talker to acting in the story ("The
    switch is free") to get past a plan that had lost its talker shots. How the presenter
    appears changes only for a person's open note in this run: never with none, a note that
    isn't there, or one already answered."""
    assert host.how(ugc) == "talks"
    made_up = _move(app, db, ugc, tool="settings", setting="presenter", value="acts",
                    why="Note 3: acting suits the story.")  # fmt: skip
    assert made_up == settings_move.PRESENTER  # no such note
    run = _noted(db, ugc, "Make the music quieter.")
    other = _move(app, db, ugc, run, tool="settings", setting="presenter", value="acts",
                  why="Note 2: acting suits the story.")  # fmt: skip
    assert other == settings_move.PRESENTER  # note 2 isn't there: only note 1 is
    db.refresh(ugc)
    assert host.how(ugc) == "talks"  # nothing switched
