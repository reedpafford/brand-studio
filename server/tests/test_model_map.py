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


def _move(app, db, video, **decision) -> str:
    user = db.get(User, video.created_by_id)
    return director_tools.run(db, user, video, decision, app.state.storage)


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
    assert "[Image" not in sent["prompt"] and sent["prompt"].endswith(model_map.SILENT)
    assert len(job["files"].get("reference_images", [])) <= 6


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
    said = _move(app, db, ugc, tool="settings", setting="video_model", model="seedance-1-lite",
                 why="Asked in the chat.")  # fmt: skip
    assert said.startswith(
        "Switched the video model to Seedance 1 Lite. The switch is free; "
        "3 clips go out of date; making what's left costs up to"
    ), said
    assert "Undo puts back Auto" in said
    clips = owner.get(f"/projects/{ugc.id}/clips").json()
    chosen = next(c["model"] for c in clips if c["model"]["id"] == "seedance-1-lite")
    assert chosen["by"] == "director" and chosen["why"].startswith("Asked in the chat.")
    shown = owner.get(f"/projects/{ugc.id}/settings").json()
    assert shown["changes"][0] | {"at": ""} == {"field": "video_model", "was": None,
                                               "now": "seedance-1-lite", "by": "director",
                                               "why": "Asked in the chat.", "at": ""}  # fmt: skip
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
    said = _move(app, db, ugc, tool="settings", setting="presenter", value="corner", why="")
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
    assert prompt.endswith(model_map.SILENT) and "only the sounds of the place" in prompt
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
    asked = _move(app, db, ugc, tool="settings", setting="presenter", value="acts",
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
