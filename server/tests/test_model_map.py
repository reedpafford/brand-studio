"""Reed's model map (4 Nov) and the v6 model moves: Omni only for a talker's own shots, never
B-roll or a video's model; each clip's model and why; the director's per-clip model and its
settings switch from the chat (a person's own choice stays); how a presenter appears, per video
(Reed's L3). Stand-ins only: no paid calls."""

from decimal import Decimal

import pytest

from app import director_tools, guides, host, model_map, settings_move, take_watch, talker
from app.breakdown import video_model
from app.catalogue import get_model
from app.clip_takes import take_credits, take_input
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


def test_omni_is_in_the_catalogue_at_its_real_cost_for_talkers_only(owner):
    omni = get_model(model_map.OMNI)
    assert (omni.usd_per_unit("360p"), omni.usd_per_unit("720p")) == (
        Decimal("0.05"), Decimal("0.15"))  # fmt: skip
    assert omni.talker_only and omni.fixed_seconds == 10 and omni.audio == "always"
    assert not omni.offered and model_map.OMNI not in {m["id"] for m in owner.get("/models").json()}
    video = Project(video_model=model_map.OMNI, look="ugc")
    assert video_model(video).id != model_map.OMNI  # never a video's model, so never B-roll
    assert model_map.seconds(omni, 6) == 10  # billed its fixed length, up to


def test_the_director_puts_a_talkers_shot_on_omni_and_says_why(app, db, owner, ugc, monkeypatch):
    rows, said = _rows(db, ugc), talker.clips(db, ugc)
    clip = next(r for c, r in rows.items() if c not in said)  # B-roll
    n = clip.clip_id.removeprefix("c")
    shown = {c["clip_id"]: c["model"] for c in owner.get(f"/projects/{ugc.id}/clips").json()}
    assert shown[clip.clip_id]["by"] == "map" and "UGC" in shown[clip.clip_id]["why"]
    talking = rows[sorted(said)[0]]
    assert shown[talking.clip_id]["id"] == talker.MODEL  # cut from the HeyGen take
    assert _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=model_map.OMNI,
                 why="x") == model_map.ONLY_TALKER  # B-roll: never  # fmt: skip
    assert _move(app, db, ugc, tool="clip_model", clip_id=talking.clip_id, model=model_map.OMNI,
                 why="x") == model_map.SAYS_IT  # our voice, lip-synced: HeyGen's  # fmt: skip
    assert _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=talker.MODEL,
                 why="x") == model_map.WHOLE_TAKE  # fmt: skip
    monkeypatch.setattr(model_map, "shows_talker", lambda db, p, c: c.id == clip.id)
    why = "She wipes a tear and sets the phone down: the line is about her."
    said = _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=model_map.OMNI,
                 why=why)  # fmt: skip
    assert said.startswith(f"Clip {n} is made on Gemini Omni 1.1 now: up to 14.6 credits a take")
    assert why in said  # 10 s at 720p, said before any take
    db.refresh(clip)
    job = take_input(db, ugc, clip)
    sent = job["input"]
    assert job["model"] == model_map.OMNI and set(sent) == {"prompt", "resolution", "aspect_ratio"}
    assert sent["resolution"] == "720p" and sent["prompt"].endswith(model_map.SILENT)
    assert take_credits(db, ugc, clip) >= get_model(model_map.OMNI).credits_per_unit("720p") * 10
    shown = {c["clip_id"]: c["model"] for c in owner.get(f"/projects/{ugc.id}/clips").json()}
    assert shown[clip.clip_id] == {"id": model_map.OMNI, "name": "Gemini Omni 1.1", "why": why,
                                   "by": "director"}  # fmt: skip
    back = _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=None, why="")
    assert back == f"Clip {n} is back on the video's Seedance 2.0."
    lite = _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model="seedance-1-lite",
                 why="A hand and the keys: Lite is enough.")  # fmt: skip
    assert lite.startswith(f"Clip {n} is made on Seedance 1 Lite") and "on Seedance 2.0)" in lite


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


def test_how_the_presenter_appears_is_chosen_per_video(app, db, owner, ugc, monkeypatch):
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
    clip = next(iter(_rows(db, ugc).values()))
    monkeypatch.setattr(model_map, "shows_talker", lambda db, p, c: c.id == clip.id)
    assert model_map.of_clip(ugc, clip).id == "seedance-2.0"  # acting: never Omni by default
    assert model_map.why(db, ugc, clip)["by"] == "map"
    bad = owner.post(f"/projects/{ugc.id}/settings", json={"presenter": "flies"})
    assert bad.status_code == 422


def test_a_narrated_video_keeps_its_narration_and_omni_acts_without_speaking(
    app, db, owner, ugc, monkeypatch
):
    """Reed, 5 Nov: a narrated video keeps its narration throughout; an Omni talker shot acts
    without speaking, its ambient sound kept under the voice; the talker's to-lens lines stay
    on HeyGen."""
    said = sorted(talker.clips(db, ugc))
    talking = _rows(db, ugc)[said[0]]
    move = {
        "tool": "clip_model",
        "model": model_map.OMNI,
        "why": "Her face from her photo, which Seedance refuses.",
    }  # a capability: not a move
    assert _move(app, db, ugc, **move, clip_id=talking.clip_id) == model_map.SAYS_IT
    acting = next(r for c, r in _rows(db, ugc).items() if c not in said)
    monkeypatch.setattr(model_map, "shows_talker", lambda db, p, c: c.id == acting.id)
    told = _move(app, db, ugc, **move, clip_id=acting.clip_id)
    assert told.startswith(f"Clip {acting.clip_id.removeprefix('c')} is made on Gemini Omni")
    db.refresh(acting)
    prompt = take_input(db, ugc, acting)["input"]["prompt"]
    assert prompt.endswith(model_map.SILENT) and "only the sounds of the place" in prompt
    assert "speaks" not in (acting.model or {})
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


def test_nothing_defaults_a_shot_to_omni_only_a_reasoned_move_in_a_photoreal_style(
    app, db, owner, ugc, monkeypatch
):
    """Reed, 5 Nov: silent shots, a moving character's included, are the style's Seedance;
    Omni only for what Seedance can't give (a photoreal talker's face from their picture),
    named in `why` and shown on the clip. A presenter who acts has no extra price of its own."""
    from app.breakdown import video_model
    from app.clip_prompts import newest
    from app.models.script_library import ScriptDraft

    for look in [s["id"] for s in guides.styles()]:  # every style and lane, any setting
        for kind in (None, "song", "narrated", "story"):
            assert not video_model(look=look, kind=kind).talker_only, look
    ugc.video_model = model_map.OMNI  # even set directly: the video's model is never Omni
    assert video_model(ugc).id == "seedance-2.0"
    ugc.video_model, ugc.presenter = None, "acts"
    db.flush()
    rows = _rows(db, ugc)
    monkeypatch.setattr(model_map, "shows_talker", lambda db, p, c: True)
    assert {model_map.of_clip(ugc, r).id for r in rows.values()} == {"seedance-2.0"}
    draft = db.get(ScriptDraft, ugc.script_draft_id)
    plan = len(newest(db, ugc).data["clips"])
    each = model_map.omni_take(db, ugc, 1) + take_watch.per_take(db, ugc.workspace_id)
    assert host.run_price(db, draft, 20, ugc) == plan * each  # photoreal: quoted on Omni
    assert all(model_map.expected(db, ugc, r) for r in rows.values())  # quoted, not made so
    clip = next(r for c, r in rows.items() if c not in talker.clips(db, ugc))
    move = {"tool": "clip_model", "clip_id": clip.clip_id, "model": model_map.OMNI}
    assert _move(app, db, ugc, **move, why="") == model_map.NO_REASON
    monkeypatch.setattr(model_map, "PHOTOREAL", ())  # a drawn style: Seedance keeps the face
    assert _move(app, db, ugc, **move, why="She walks to the door.") == model_map.NOT_NEEDED
    assert host.run_price(db, draft, 20, ugc) == 0  # its shots are Seedance B-roll, priced
    assert not any(model_map.expected(db, ugc, r) for r in rows.values())
    assert len(newest(db, ugc).data["clips"]) == len(rows)


def test_before_the_plan_is_approved_only_a_persons_request_switches_and_omni_waits(
    app, db, owner, ugc, monkeypatch
):
    """Reed, 4 Nov: settings follow a person's request or the approved plan, never an
    unapproved one; Omni makes only the approved plan's acting shots."""
    from app import settings_move

    monkeypatch.setattr("app.plans.status", lambda db, project: "ready")
    move = {"tool": "settings", "setting": "video_model", "model": "seedance-1-lite"}
    assert _move(app, db, ugc, **move, why="") == settings_move.NOT_YET
    asked = _move(app, db, ugc, **move, why="Note 2: they asked for Lite.")
    assert asked.startswith("Switched the video model to Seedance 1 Lite")
    clip = next(iter(_rows(db, ugc).values()))
    assert _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=model_map.OMNI,
                 why="x") == model_map.UNAPPROVED  # fmt: skip


def test_the_cost_bar_prices_a_clip_on_omni_at_its_ten_seconds(app, db, owner, ugc, monkeypatch):
    """QA on #1327: a clip still to make on Omni counts its fixed 10 s at 720p in what's left."""
    from app.routes.estimate import _stages

    clip = next(r for c, r in _rows(db, ugc).items() if c not in talker.clips(db, ugc))
    clip.picked_take_id = None
    db.flush()

    def left() -> float:
        return next(s.credits for s in _stages(db, ugc) if s.stage == "clips")

    seedance = left()
    monkeypatch.setattr(model_map, "shows_talker", lambda db, p, c: c.id == clip.id)
    assert _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=model_map.OMNI,
                 why="She takes part in the story.").startswith("Clip")  # fmt: skip
    omni = float(get_model(model_map.OMNI).credits_per_unit("720p")) * 10
    assert left() >= omni > seedance


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


def test_a_photoreal_acting_presenters_planned_shots_are_quoted_on_omni(
    app, db, owner, ugc, monkeypatch
):
    """The lead on #1346 (rule 36): with the plan approved but no clip rows yet, a photoreal
    presenter who acts has their shots quoted on Omni, the director's path for them; a drawn
    style's are quoted on its Seedance."""
    import copy

    from app.clip_prompts import newest
    from app.models.clips import ProjectClip
    from app.routes.estimate import _stages

    db.query(ProjectClip).filter_by(project_id=ugc.id).delete()
    db.flush()
    monkeypatch.setattr("app.host.host_look", lambda db, p: type("I", (), {"id": 1})())
    row = newest(db, ugc)
    data = copy.deepcopy(row.data)
    first = data["clips"][0]
    shot = next(s for sc in data["scenes"] for s in sc["shots"] if s["id"] == first["shot_ids"][0])
    shot["character_ids"] = [*(shot.get("character_ids") or []), "char:1"]  # the talker's
    row.data = data
    db.flush()

    def left() -> float:
        return next(s.credits for s in _stages(db, ugc) if s.stage == "clips")

    talks = left()
    ugc.presenter = "acts"
    db.flush()
    omni = float(model_map.omni_take(db, ugc, first["seconds"]))
    seedance = float(model_map._model("seedance-2.0").credits_per_unit("480p")) * first["seconds"]
    assert abs(left() - (talks - seedance + omni)) < 0.02  # that shot on Omni, the rest as before
    monkeypatch.setattr(model_map, "PHOTOREAL", ())
    assert abs(left() - talks) < 0.02  # a drawn style: Seedance, as ever
