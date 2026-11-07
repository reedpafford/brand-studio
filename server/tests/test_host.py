"""The Presenter format (Reed's F1): a host says the narration on camera over the B-roll. The
director makes the narration, then the host (a still on green, then one HeyGen take of the
whole narration, priced like a take: Reed, 4 Nov), then keys it over the cut. Stand-ins only."""

from decimal import Decimal

import pytest

from app import director_song, guides, host, p_video, song_breakdown, song_takes, talker
from app.catalogue import get_model
from app.models.accounts import User
from app.models.clips import FinalVideo
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.songs import SongTake
from app.prompts.schemas import SongBreakdown
from app.routes.estimate import run_price
from tests import helpers
from tests.test_freestyle_dialogue import _run
from tests.test_freestyle_song import NARRATION, _sent


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def _video(db, fs) -> Project:
    return db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                  execution_options={"see_hidden": True})  # fmt: skip


def _jobs(db, video, step):
    return [j for j in db.query(Job).filter(Job.project_id == video.id).order_by(Job.id)
            if j.input.get("step") == step]  # fmt: skip


def test_presenter_is_a_narrated_format_with_a_host():
    form = guides.format_("presenter")
    assert (form["engine"], form["host"], form["on"]) == ("narrated", True, True)
    assert not any(f["host"] for f in guides.formats() if f["id"] != "presenter")


def test_the_director_makes_the_host_after_the_narration_and_lays_it_over_the_cut(app, db, owner):
    fs = _sent(owner, "presenter", NARRATION)
    _run(app, db, ticks=160)
    out = owner.get(f"/freestyles/{fs['id']}").json()
    moves = helpers.moves(db, db.get(Freestyle, fs["id"]).project_id)
    assert out["status"] == "delivered", moves
    said = next(i for i, m in enumerate(moves) if m.startswith("Making the narration"))
    drawn = next(i for i, m in enumerate(moves) if m.startswith("Drawing the host"))
    cut = next(i for i, m in enumerate(moves) if m.startswith("Making Cut 1"))
    assert said < drawn < cut
    video = _video(db, fs)
    (still,) = _jobs(db, video, host.STILL)
    assert "chroma-key green" in still.input["input"]["prompt"] and still.kind == "image"
    (job,) = _jobs(db, video, host.PIECE)  # one HeyGen take of the whole narration
    still, row = host.rows(db, video)
    assert row.file_id and row.start == 0 and _jobs(db, video, "song_take")
    sent = job.input["input"]
    assert (job.provider, job.input["model"], sent["resolution"]) == ("heygen", talker.MODEL,
                                                                      "720p")  # fmt: skip
    assert sent["motion_prompt"] == f"{host.TALK} {host.GREEN}"  # stays on the green
    note = "Blunt and fed up: a slow head shake, then a jab of the finger at the lens. " * 12
    host.make(db, db.get(User, video.created_by_id), video, app.state.storage, number=1,
              motion=note)  # a director's note on a corner host keeps the green  # fmt: skip
    again = _jobs(db, video, host.PIECE)[-1].input["input"]["motion_prompt"]
    assert again.startswith("Blunt and fed up") and again.endswith(host.GREEN)
    assert len(again) <= talker.LONGEST_MOTION
    assert job.input["files"] == {"image": [still.file_id], "audio": [row.audio_file_id]}
    assert job.credits == Decimal(sent["duration"]) * get_model(talker.MODEL).credits_per_unit(
        "720p")  # its "up to", as a take  # fmt: skip
    assert not [j for j in db.query(Job).all() if j.input.get("model") == p_video.ID]
    final = db.query(FinalVideo).filter(FinalVideo.project_id == video.id).all()[-1]
    assert [x for x in final.cut_ins if x.startswith("host:")]  # a new piece: out of date
    said = owner.get(f"/projects/{video.id}/host").json()  # the Cast tab's Presenter (S5-02)
    who, take = host.host_look(db, video), db.get(SongTake, video.song_take_id)
    assert (said["presenter_id"], said["voice"]) == (who.id if who else None, take.voice)
    assert owner.get("/presenter-ways/corner.jpg").headers["content-type"] == "image/jpeg"
    assert owner.get("/presenter-ways/other.jpg").status_code == 422


def test_a_failed_piece_is_tried_again_once_then_make_again_makes_it(app, db, owner, monkeypatch):
    fs = _sent(owner, "presenter", NARRATION)
    _run(app, db, ticks=160)
    video = _video(db, fs)
    monkeypatch.setattr("app.clip_takes.fits", lambda *a: "")  # the whole take, made again
    piece = host.rows(db, video)[1]
    first = owner.post(f"/projects/{video.id}/host/{piece.number}")
    assert first.status_code == 201, first.text
    (job,) = [j for j in _jobs(db, video, host.PIECE) if j.status == JobStatus.queued]
    job.status, job.error = JobStatus.failed, "The video service failed."
    from app.steps import step_failed

    step_failed(db, job)
    db.commit()
    (retry,) = [j for j in _jobs(db, video, host.PIECE) if j.retry_of_id == job.id]
    assert retry.auto
    retry.status, retry.error = JobStatus.failed, "The video service failed."
    step_failed(db, retry)  # no second automatic retry
    db.commit()
    shown = owner.get(f"/projects/{video.id}/host").json()
    (mine,) = [p for p in shown["pieces"] if p["number"] == piece.number]
    assert mine["error"] and mine["credits"] > 0  # Make again, at its price (rule 22)
    assert not [j for j in _jobs(db, video, host.PIECE) if j.retry_of_id == retry.id]
    assert owner.post(f"/projects/{video.id}/host/{piece.number}").status_code == 201


def test_the_earlier_presenter_comes_back_free_and_back_again(app, db, owner):
    fs = _sent(owner, "presenter", NARRATION)
    _run(app, db, ticks=160)
    video = _video(db, fs)
    url = f"/projects/{video.id}/host"
    assert owner.post(f"{url}/back").status_code == 409  # nothing earlier yet
    rows = host.rows(db, video)
    now = [r.file_id for r in rows]
    for r, f in zip(rows, now, strict=True):  # as after Make the presenter again
        r.earlier, r.file_id = [f], f + 1000
    db.commit()
    shown = owner.post(f"{url}/back").json()
    assert [p["file_id"] for p in shown["pieces"]] == now  # the one before, free
    again = owner.post(f"{url}/back").json()  # pressed again: the newer one (Undo)
    assert [p["file_id"] for p in again["pieces"]] == [f + 1000 for f in now]


def test_a_presenter_runs_up_to_holds_the_host_on_heygen(app, db, owner):
    fs = _sent(owner, "narrated", NARRATION)
    draft = db.get(ScriptDraft, _video(db, fs).script_draft_id)
    plain = run_price(db, draft)
    draft_script = draft.script_id
    from app.models.script_library import Script

    db.get(Script, draft_script).format = "presenter"
    db.flush()
    rate = get_model(talker.MODEL).credits_per_unit("720p")
    assert run_price(db, draft) - plain >= rate * 4  # every second of the narration, at least


def test_a_narrated_quote_is_for_its_words_at_our_slowest_narrator_then_the_narrations_length(
    app, db, owner
):
    """The dry run: a script read in 104 s was quoted at 70 s (4.8 words a second)."""
    from app.models.songs import SongTake
    from app.narration import longest

    video = _video(db, _sent(owner, "presenter", NARRATION))
    draft = db.get(ScriptDraft, video.script_draft_id)
    draft.text = "Pickles keep for weeks. " * 65  # 260 words: 54 s at 4.8, 100 s at 2.6
    assert longest(db, draft, video) == 100  # the host's seconds, and the B-roll's clock
    video.look = "ugc"  # "3.3–3.5 words a second" while speaking, the voice on 84% at least
    assert longest(db, draft, video) == 94  # 260 words / (3.3 x 0.84)
    video.look = "house"
    made = SongTake(draft_id=draft.id, project_id=video.id, number=1, kind="narration",
                    job_id=db.query(Job).first().id, lyrics=draft.text, style_line="",
                    seconds=112.3)  # fmt: skip
    db.add(made)
    db.flush()
    video.song_take_id = made.id
    assert longest(db, draft, video) == 113  # the narration made: its real length


def test_a_narrated_quotes_b_roll_allows_every_short_shot_at_the_models_shortest_clip(
    app, db, owner
):
    """Rule 36 (F7): a 1 s shot is made as a 4 s Seedance clip, and the quote counted 1 s."""
    from app.models.breakdowns import BreakdownVersion
    from app.routes.estimate import quoted_seconds

    video = _video(db, _sent(owner, "presenter", NARRATION))
    draft = db.get(ScriptDraft, video.script_draft_id)
    draft.text = "Pickles keep for weeks. " * 65  # 100 s at our slowest narrator
    for model, times in (("seedance-1-lite", 2), ("p-video", 1)):  # shortest clip 4 s, 1 s
        video.video_model = model
        assert quoted_seconds(db, draft, video) == 100 * times  # before a plan: ~2 s shots
    video.video_model = "seedance-1-lite"
    shots = [{"id": f"1.{n}", "seconds": s} for n, s in enumerate([1, 1.5] * 10 + [6], 1)]
    db.add(BreakdownVersion(project_id=video.id, script_version=1, source="edit",
                            data={"scenes": [{"shots": shots}], "clips": []}))  # fmt: skip
    db.flush()
    assert quoted_seconds(db, draft, video) == 20 * 4 + 6  # the plan's shots, each at least 4 s


def test_neighbouring_b_roll_shots_share_one_clip_up_to_the_models_longest():
    """F7, as Reed revised it (7 Nov): neighbouring short B-roll shots share one multi-shot
    clip, up to the video model's longest, instead of a clip a shot at its shortest. It splits
    past the longest, where a talker's lip-synced shot starts or ends, and where the place
    changes; a song's clips stay as planned."""
    shots = {"s1": {"start": 0, "end": 1.5}, "s2": {"start": 1.5, "end": 3.0},
             "s3": {"start": 3.0, "end": 9.0}}  # fmt: skip
    data = {"scenes": [{"shots": [{"id": s} for s in shots]}],
            "clips": [{"id": "c1", "shot_ids": ["s1", "s2", "s3"]}],
            "song": {"take_id": 1, "shots": shots}}  # fmt: skip
    one = song_breakdown.fit(data, broll=True, longest=15)["clips"]
    assert [(c["id"], c["shot_ids"], c["seconds"]) for c in one] == [("c1", ["s1", "s2", "s3"], 9)]
    assert song_breakdown.slice_of({**data, "clips": one}, "c1") == {
        "start": 0,
        "end": 9.0,
        "sung_shots": [],
    }  # cut to the narration's own times
    longer = song_breakdown.fit(data, broll=True, longest=5)["clips"]  # past the longest
    assert [(c["id"], c["shot_ids"]) for c in longer] == [("c1", ["s1", "s2"]), ("c1b", ["s3"])]
    talks = {**shots, "s2": {**shots["s2"], "sung": True}}  # a talker's own take in the middle
    apart = song_breakdown.fit({**data, "song": {"take_id": 1, "shots": talks}}, broll=True,
                               longest=15)["clips"]  # fmt: skip
    assert [c["shot_ids"] for c in apart] == [["s1"], ["s2"], ["s3"]]
    places = {**data, "scenes": [{"shots": [{"id": "s1", "place_id": "place:1"},
                                            {"id": "s2", "place_id": "place:1"},
                                            {"id": "s3", "place_id": "place:2"}]}]}  # fmt: skip
    moved = song_breakdown.fit(places, broll=True, longest=15)["clips"]
    assert [c["shot_ids"] for c in moved] == [["s1", "s2"], ["s3"]]
    assert len(song_breakdown.fit(data)["clips"]) == 1  # a song's clips stay as planned


SHOTS_251 = [1.48, 1.98, 2.0, 1.86, 1.54, 0.54, 2.08, 1.3, 2.32, 0.88, 0.84, 0.74, 1.14, 1.56,
             0.64, 1.24, 0.9]  # Dr. Pickle 251: 17 shots, 23.04 s of narration  # fmt: skip
SCENES_251 = [2, 2, 2, 2, 4, 5]  # its six scenes' shot counts, one planned clip a scene


def _plan_251() -> SongBreakdown:
    at, n, scenes = 0.0, 0, []
    for k, count in enumerate(SCENES_251, 1):
        shots = []
        for m in range(1, count + 1):
            end = round(at + SHOTS_251[n], 2)
            shots.append({"id": f"{k}.{m}", "script_lines": [k], "speaker": None, "line": None,
                          "action": "B-roll.", "reaction": None, "camera": "Close-up, static.",
                          "seconds": SHOTS_251[n], "character_ids": [], "place_id": None,
                          "moment": None, "screen_ids": [], "song_start": at, "song_end": end,
                          "sung": False})  # fmt: skip
            at, n = end, n + 1
        scenes.append({"id": k, "heading": f"SCENE {k}", "look": "", "shots": shots})
    clips = [{"id": f"c{k}", "shot_ids": [s["id"] for s in sc["shots"]], "seconds": 4, "seam": ""}
             for k, sc in enumerate(scenes, 1)]  # fmt: skip
    return SongBreakdown.model_validate({"hook": "", "scenes": scenes, "clips": clips})


def test_dr_pickle_251s_shape_makes_six_clips_not_seventeen():
    """Reed (7 Nov): "Good idea, make sure it works then do it." 251's 17 shots (5 under a
    second) were 17 Seedance clips of 4 s: 68 s made for 23 s used. Shared multi-shot clips,
    one a scene, make 6 clips and 27 s; every clip's slice still sits on the narration."""
    plan, song = song_breakdown.split(_plan_251(), 1, broll=True, shortest=4, longest=15)
    data = {**plan.model_dump(), "song": song}
    assert len(plan.clips) == 6 and sum(c.seconds for c in plan.clips) == 27
    starts = [song_breakdown.slice_of(data, c.id)["start"] for c in plan.clips]
    ends = [song_breakdown.slice_of(data, c.id)["end"] for c in plan.clips]
    assert starts[0] == 0 and starts[1:] == ends[:-1] and ends[-1] == 23.04  # back to back
    one_a_shot = [{**c.model_dump(), "id": s, "shot_ids": [s]} for c in plan.clips
                  for s in c.shot_ids]  # fmt: skip
    joined = song_breakdown._joined({**data, "clips": one_a_shot}, song["shots"], 4, 15)
    assert [c["shot_ids"] for c in joined] == [c.shot_ids for c in plan.clips]  # one-shot
    # clips a plan made too short are joined within their scene, never across one


def test_a_short_b_roll_shot_is_made_at_the_video_models_own_shortest_clip(app, db, owner):
    """Video 240 (7 Nov): every Omni 1.2 clip of a UGC narration was made at 4 s, though Omni
    makes 3 s (17 clips: 68 s made for 24 s used). Each short shot is now made at its video
    model's shortest clip, as the quote already counts it: Omni 3 s, Seedance 4 s."""
    from app.models.breakdowns import BreakdownVersion

    shots = {"s1": {"start": 0, "end": 1.5, "sung": False},
             "s2": {"start": 1.5, "end": 3.0, "sung": False},
             "s3": {"start": 3.0, "end": 9.0, "sung": False}}  # fmt: skip
    data = {"scenes": [{"shots": [{"id": s} for s in shots]}],
            "clips": [{"id": "c1", "shot_ids": ["s1", "s2", "s3"]}],
            "song": {"take_id": 0, "shots": shots}}  # fmt: skip
    one = {**data, "clips": [{"id": f"c{n}", "shot_ids": [s]} for n, s in enumerate(shots, 1)]}
    omni = song_breakdown.fit(one, broll=True, shortest=3)["clips"]  # a plan's one-shot clips
    assert [(c["id"], c["seconds"]) for c in omni] == [("c1", 3), ("c2", 3), ("c3", 6)]
    from decimal import Decimal

    from app.models.songs import SongTake

    video = _video(db, _sent(owner, "presenter", NARRATION))
    job = Job(workspace_id=1, created_by_id=1, kind="audio", provider="fake", input={},
              credits=Decimal(0), status=JobStatus.succeeded)  # fmt: skip
    db.add(job)
    db.flush()
    take = SongTake(draft_id=video.script_draft_id, project_id=video.id, number=1,
                    kind="narration", job_id=job.id, lyrics="", style_line="")  # fmt: skip
    db.add(take)
    db.flush()
    data = {**one, "song": {"take_id": take.id, "shots": shots}}  # under a narration
    for look, least in (("ugc", 3), ("house", 4)):
        video.look, video.video_model = look, None
        db.flush()
        assert song_breakdown.least(db, video.id) == least
        row = BreakdownVersion(project_id=video.id, script_version=1, source="edit", data=data)
        db.add(row)
        db.flush()  # a plan saved with its song part is fitted at the model's shortest
        assert [c["seconds"] for c in row.data["clips"]] == [least, least, 6], look  # an
        # edit never regroups the clips it carries


def test_the_host_stands_away_from_the_action():
    assert host.side("A skull-faced man waves from the right side of the frame.") == "left"
    assert host.side("Fat melts off his belly, centred.") == "right"


def test_seedance_1_lite_is_offered_for_b_roll_and_never_sent_a_sound_switch():
    lite = get_model("seedance-1-lite")
    assert (lite.usd_per_unit("480p"), lite.usd_per_unit("720p")) == (
        Decimal("0.018"), Decimal("0.036"))  # fmt: skip
    assert not lite.default and lite.audio is None and lite.take_resolution == "480p"
    sent, _ = p_video.fit("seedance-1-lite", {"prompt": "x", "generate_audio": True}, {})
    assert "generate_audio" not in sent
    assert p_video.fit("seedance-2.5", {"generate_audio": True}, {})[0]["generate_audio"]


def test_a_saved_presenter_is_in_the_cast_with_its_own_voice_before_make_it(app, db, owner):
    """QA (S5-02): a presenter video whose presenter is saved in the brand (Mark, his own voice
    Roger). Before Make it, the Cast tab's Presenter reads the voice it will be read in (his,
    never another saved voice), and Mark is in the cast list with the OK the chat card asks."""
    from tests.conftest import first_brand, upload
    from tests.helpers import with_sheet

    brand = first_brand(owner)
    mark = owner.post("/library/character", json={
        "name": "Mark", "voice_stock_key": "Roger", "brand_ids": [brand],
        "image_file_ids": [upload(owner)]}).json()  # fmt: skip
    with_sheet(db, mark["id"])
    body = {"type": "presenter", "look": "house", "shape": "9:16", "text": NARRATION,
            "brand_id": brand, "cast_ids": [mark["id"]]}  # fmt: skip
    sent = owner.post("/freestyles", json=body)
    assert sent.status_code == 201, sent.text
    _run(app, db, ticks=6, start=False)  # its plan, then its start card: nothing made yet
    pid = owner.get(f"/freestyles/{sent.json()['id']}").json()["project_id"]
    said = owner.get(f"/projects/{pid}/host").json()
    assert (said["presenter_id"], said["voice"]) == (mark["id"], "Roger")  # his, not a clone
    rows = owner.get(f"/projects/{pid}/assets").json()
    (row,) = [r for r in rows if r["library_item_id"] == mark["id"]]
    assert row["kind"] == "character" and row["name"] == "Mark"
    cast = owner.get(f"/projects/{pid}/cast").json()
    assert [i["library_item_id"] for i in cast["items"] if i["kind"] == "character"] == [mark["id"]]
    # QA (#1395): the director names Sarah (director.md's first narration); his own voice is
    # kept, so the narration is read in the voice the Cast tab showed
    video = db.get(Project, pid, execution_options={"see_hidden": True})
    me = db.get(User, video.created_by_id)
    made = director_song.run(db, me, video, {"tool": "narration", "voice": "Sarah"}, {})
    assert made == "Making the narration.", made
    (take,) = song_takes.for_video(db, video)
    assert take.voice == "Roger" == owner.get(f"/projects/{pid}/host").json()["voice"]


def test_a_dr_pickle_presenter_keeps_its_clone_when_the_director_names_another(app, db, owner):
    """QA (#1395): a presenter with no voice of his own in a style with one (Dr. Pickle's
    clone). The director names Sarah; the clone is kept, as the Cast tab showed. (A House video
    with neither takes the director's pick: test_freestyle_song.)"""
    from app.models.voices import Voice
    from tests.conftest import first_brand

    body = {"type": "presenter", "look": "dr-pickle", "shape": "9:16", "text": NARRATION,
            "brand_id": first_brand(owner)}  # fmt: skip
    sent = owner.post("/freestyles", json=body)
    assert sent.status_code == 201, sent.text
    _run(app, db, ticks=6, start=False)  # its plan, then its start card: nothing made yet
    video = _video(db, sent.json())
    clone = f"voice:{db.query(Voice).filter_by(look='dr-pickle').one().id}"
    assert owner.get(f"/projects/{video.id}/host").json()["voice"] == clone
    me = db.get(User, video.created_by_id)
    made = director_song.run(db, me, video, {"tool": "narration", "voice": "Sarah"}, {})
    assert made == "Making the narration.", made
    (take,) = song_takes.for_video(db, video)
    assert take.voice == clone == owner.get(f"/projects/{video.id}/host").json()["voice"]
