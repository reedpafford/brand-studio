"""Reed's model map (4 Nov) and the v6 model moves: Omni only for a talker's own shots, never
B-roll or a video's model; each clip's model and why; the director's per-clip model and its
settings switch from the chat (a person's own choice stays); how a presenter appears, per video
(Reed's L3). Stand-ins only: no paid calls."""

from decimal import Decimal
from pathlib import Path

import pytest

from app import director_tools, host, model_map, settings_move, talker
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
    assert model_map.of_clip(ugc, clip).id == model_map.OMNI  # the talker's shots: Omni
    assert model_map.why(db, ugc, clip)["why"].startswith("The presenter acts in the story")
    bad = owner.post(f"/projects/{ugc.id}/settings", json={"presenter": "flies"})
    assert bad.status_code == 422


def test_a_talker_speaks_a_moment_on_omni_in_one_described_voice(app, db, owner, ugc):
    """Reed, 4 Nov: speech through Omni for a dramatic moment, the script's words exactly, the
    narration muted only while they're said, one voice described the same in every clip,
    never a silent change of voice; "narration only" turns it off."""
    from app.clip_takes import _narrated_mix
    from app.video_settings import made_stale

    said = sorted(talker.clips(db, ugc))
    clip = _rows(db, ugc)[said[0]]
    move = {"tool": "clip_model", "clip_id": clip.clip_id, "model": model_map.OMNI,
            "value": "speaks", "why": "The reveal: she says it to his face."}  # fmt: skip
    assert _move(app, db, ugc, **move) == model_map.NO_VOICE  # described first
    voice = "a woman about 60, low and warm, a slight Midwest accent, close to tears"
    told = _move(app, db, ugc, **move, note=voice)
    assert "Omni's own voice" in told and voice in told  # the change of voice, said first
    db.refresh(clip)
    words, start, end = model_map.said(db, ugc, clip)
    assert clip.clip_id not in talker.clips(db, ugc) and not talker.says(db, ugc, clip)
    sent = take_input(db, ugc, clip)["input"]["prompt"]
    assert f'word for word and nothing else: "{words}"' in sent and voice in sent
    assert model_map.spoken(db, ugc, [clip]) == {0: (start, end)}
    graph = ";".join(_narrated_mix(Path("."), [end + 1], False, "st=0:d=1", {0: (start, end)}))
    assert f"between(t,{start:.3f},{end:.3f})':volume=0" in graph  # muted only then
    assert _move(app, db, ugc, **move, note="a young man").startswith(
        "Refused: the talker's Omni voice is already"
    )  # one voice, described the same
    lite = {**move, "model": "seedance-1-lite"}
    assert _move(app, db, ugc, **lite) == model_map.OMNI_ONLY
    made = {"model": model_map.OMNI, "speaks": True, "aspect_ratio": "9:16", "products": {}}
    take = type("T", (), {"made_with": made})()
    assert not made_stale(ugc, clip, take)
    said_off = _move(app, db, ugc, tool="settings", setting="narration_only", value="on", why="")
    assert said_off.startswith("Narration only is on. The switch is free;"), said_off
    db.refresh(ugc)
    assert made_stale(ugc, clip, take) and model_map.spoken(db, ugc, [clip]) == {}


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


def test_a_persons_presenter_and_narration_only_stay_unless_they_ask(app, db, owner, ugc):
    """QA on #1327: a person's switch (or a value set before the log, e.g. a PATCH) stays
    theirs; the director may change it only for their note in the chat; Undo puts it back."""
    url = f"/projects/{ugc.id}/settings"
    assert owner.post(url, json={"presenter": "corner"}).status_code == 200
    assert owner.post(url, json={"narration_only": True}).status_code == 200
    db.refresh(ugc)
    for setting, value in (("presenter", "acts"), ("narration_only", "off")):
        no = _move(app, db, ugc, tool="settings", setting=setting, value=value, why="")
        assert no.startswith("Refused:") and "their choice stays" in no
    asked = _move(app, db, ugc, tool="settings", setting="presenter", value="acts",
                  why="Note 1: they asked for her acting in the story.")  # fmt: skip
    assert asked.startswith("The presenter now appears acting in the story")
    undo = owner.post(url, json={"narration_only": False, "undo": True}).json()["settings"]
    assert undo["narration_only"] is False
    owner.patch(f"/projects/{ugc.id}", json={"aspect_ratio": "16:9"})
    db.refresh(ugc)
    assert ugc.settings_log[-1] | {"at": ""} == {
        "field": "aspect_ratio", "was": "9:16", "now": "16:9", "by": "person",
        "by_id": ugc.created_by_id, "why": "", "at": ""}  # fmt: skip
    shape = _move(app, db, ugc, tool="settings", setting="aspect_ratio", value="9:16", why="")
    assert "their choice stays" in shape


def test_the_acts_price_bills_every_clip_omnis_ten_seconds_and_a_refusal_keeps_no_voice(
    app, db, owner, ugc
):
    """QA on #1327 (rule 36): a short clip on Omni still bills 10 s, so a presenter who acts
    is quoted every clip at 10 s; a refused speaking move keeps no voice."""
    from app.clip_prompts import newest
    from app.models.script_library import ScriptDraft

    clips = len(newest(db, ugc).data["clips"])
    ugc.presenter = "acts"
    db.flush()
    draft = db.get(ScriptDraft, ugc.script_draft_id)
    omni = get_model(model_map.OMNI)
    assert host.run_price(db, draft, 20, ugc) == clips * 10 * omni.credits_per_unit("720p")
    ugc.presenter, ugc.aspect_ratio = None, "1:1"  # Omni makes 9:16 or 16:9 only
    db.flush()
    clip = _rows(db, ugc)[sorted(talker.clips(db, ugc))[0]]
    no = _move(app, db, ugc, tool="clip_model", clip_id=clip.clip_id, model=model_map.OMNI,
               value="speaks", why="x", note="a calm older woman")  # fmt: skip
    assert no.startswith("Refused:") and ugc.omni_voice is None and clip.model is None


def test_the_music_stays_ducked_while_the_talker_speaks_on_omni(tmp_path):
    """QA on #1327: muting the narration under an Omni line mustn't un-duck the music."""
    import re
    import subprocess

    from app.clip_takes import song_cut
    from app.providers import fake_local

    def tone(name: str, freq: int, level: float) -> bytes:
        out = tmp_path / name
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603, S607
                        f"sine=frequency={freq}:duration=6,volume={level}", str(out)],
                       check=True)  # fmt: skip
        return out.read_bytes()

    video = song_cut([fake_local.mp4("9:16", 3), fake_local.mp4("9:16", 3)], [3.0, 3.0],
                     tone("voice.wav", 1000, 0.5), True, tone("bed.wav", 100, 0.9),
                     spoken={1: (3.0, 6.0)})  # fmt: skip
    (tmp_path / "cut.mp4").write_bytes(video)

    def bed(start: float) -> float:
        said = subprocess.run(["ffmpeg", "-i", str(tmp_path / "cut.mp4"), "-ss", str(start),  # noqa: S603, S607
                               "-t", "1.5", "-af", "lowpass=f=200,volumedetect", "-f", "null",
                               "-"], capture_output=True, text=True).stderr  # fmt: skip
        return float(re.findall(r"mean_volume: (-?[\d.]+) dB", said)[-1])

    assert abs(bed(4.0) - bed(1.0)) < 2.0  # ducked the same under the muted line


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
