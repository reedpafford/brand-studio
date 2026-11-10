"""Brand footage (Reed, 9 Nov, the runway's item 10): a brand's real clips on its library's
Footage tab, each described once (the AI's look on the stand-in, or typed), given to every
style's director as context, a Seedance reference at its dearer rate, and in UGC a B-roll shot
of its own, cut free from the clip and laid over the talker like any B-roll. Stand-ins only."""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app import clip_prompts, clip_takes, cut, director, footage, watch_cut
from app.catalogue import get_model
from app.credits import estimate
from app.enhance import project_context
from app.models.clips import ClipTake
from app.models.files import MediaUpload, StoredFile
from app.models.jobs import Job
from app.prompts.schemas import Breakdown
from app.providers.fake_local import mp4
from app.providers.replicate import _usage
from tests.conftest import first_brand, run_writer
from tests.helpers import product
from tests.test_omni_talker import _clips, _made, _video, songs_on  # noqa: F401 - fixture


def _add(client, brand, data=None, **form):
    files = {"upload": ("demo.mp4", data or mp4("9:16", 6, sound=True), "video/mp4")}
    return client.post(f"/brands/{brand}/footage", files=files, data=form)


def _described(app, db, owner, brand, text="Opens, beeps and flashes red.", **form) -> int:
    return _add(owner, brand, description=text, **form).json()["id"]


def test_a_clip_is_added_once_and_described_by_one_ai_look_at_two_frames(app, db, owner):
    brand = first_brand(owner)
    product(db, brand, "Pocket alarm")
    db.commit()
    first = footage.products(db, brand)[0]  # the stand-in names the brand's first product
    price = owner.get(f"/brands/{brand}/footage/price").json()
    assert price["credits"] >= 1 and price["usd"] is not None  # said before the press
    added = _add(owner, brand)
    assert added.status_code == 201, added.text
    clip = added.json()
    assert clip["describing"] and clip["seconds"] == pytest.approx(6, abs=0.2)
    row = db.get(MediaUpload, clip["id"])
    assert len(row.frame_file_ids) == footage.FRAMES == 2 and clip["thumb_file_id"]
    job = db.get(Job, row.describe_job_id)  # a picture check, on the stand-in here
    assert (job.kind, job.provider, job.input["effort"]) == ("check-claude", "claude", "low")
    assert job.input["files"]["reference_images"] == row.frame_file_ids
    run_writer(app, db)
    (listed,) = owner.get(f"/brands/{brand}/footage").json()
    assert not listed["describing"] and first.name in listed["description"]
    assert listed["product_id"] == first.id  # it named one of the brand's products
    media = owner.get(f"/brands/{brand}/media").json()["items"]  # uploaded once: Media has it
    assert any(m["key"] == f"upload:{clip['id']}" for m in media)


def test_typed_words_skip_the_ai_and_can_be_changed_deleted_and_brought_back(app, db, owner):
    brand = first_brand(owner)
    picture = owner.post(
        f"/brands/{brand}/footage", files={"upload": ("a.png", (b"\x89PNG\r\n\x1a\n" + b"\0" * 64))}
    )
    assert picture.status_code == 415  # a clip, never a picture
    clip = _add(owner, brand, description=" The alarm opens. ").json()
    assert clip["description"] == "The alarm opens." and not clip["describing"]
    assert not db.query(Job).filter(Job.kind == footage.KIND).count()  # no AI call
    alarm = product(db, brand, "Pocket alarm")
    db.commit()
    url = f"/brands/{brand}/footage/{clip['id']}"
    changed = owner.patch(url, json={"description": "It flashes.", "product_id": alarm}).json()
    assert (changed["description"], changed["product_id"]) == ("It flashes.", alarm)
    assert owner.patch(url, json={"product_id": 999999}).status_code == 422
    assert owner.delete(url).status_code == 204
    assert owner.get(f"/brands/{brand}/footage").json() == []
    assert owner.post(f"{url}/restore").json()["description"] == "It flashes."  # Undo
    assert [c["id"] for c in owner.get(f"/brands/{brand}/footage").json()] == [clip["id"]]


def test_the_director_gets_only_the_clips_that_fit_in_a_few_lines_and_frames(app, db, owner):
    video = _video(db, owner)  # its script names fomo, not the alarm
    brand = video.brand_id
    app_id, alarm = product(db, brand, "fomo"), product(db, brand, "Pocket alarm")
    db.commit()
    mine = [
        _described(app, db, owner, brand, f"The fomo app on a {n} phone.", product_id=app_id)
        for n in ("red", "blue", "gold", "black", "pink", "green", "white", "grey", "teal")
    ]
    _described(app, db, owner, brand, "The alarm flashing.", product_id=alarm)  # not this video's
    told = project_context(db, video, "director")[0][-1]
    assert told.startswith("<footage>") and "alarm" not in told
    assert told.count(f"\n- {footage.KEY}") == footage.MOST  # kept compact
    assert all(f"{footage.KEY}{i} " in told for i in mine[: footage.MOST])
    assert "<footage>" not in "".join(project_context(db, video, "take_watch")[0])
    plan = project_context(db, video, "breakdown")[0][-1]  # UGC: a B-roll shot may BE one
    assert "may BE one of these clips" in plan and "first 4 images" in plan
    framed = footage.with_frames(db, video, {"files": {"reference_images": [99]}})
    assert len(framed["files"]["reference_images"]) == footage.SEEN + 1
    video.look = "house"  # every style gets them as context; only UGC uses one as a shot
    assert "may BE" not in project_context(db, video, "breakdown")[0][-1]


def _plan(*shots, clips=None) -> Breakdown:
    def one(i, **more):
        return {"id": i, "script_lines": [1], "speaker": None, "line": None, "action": "B-roll.",
                "reaction": None, "camera": "Close-up", "seconds": 3.0,
                "character_ids": ["char:1"], "place_id": None, "moment": None,
                "screen_ids": ["screen:1"], **more}  # fmt: skip

    scene = {
        "id": 1,
        "heading": "INT. ROOM",
        "look": "Plain.",
        "shots": [one(i, **more) for i, more in shots],
    }
    clips = clips or [[s[0]] for s in shots]
    return Breakdown.model_validate({"hook": "h", "scenes": [scene], "clips": [
        {"id": f"c{n}", "shot_ids": ids, "seconds": 3, "seam": "end"}
        for n, ids in enumerate(clips, 1)]})  # fmt: skip


def test_a_footage_shot_is_only_a_ugc_b_roll_clip_of_its_own_used_once(app, db, owner):
    video = _video(db, owner)
    key = f"{footage.KEY}{_described(app, db, owner, video.brand_id)}"  # a 6 s clip
    other = f"{footage.KEY}{_described(app, db, owner, video.brand_id)}"

    def use(start=1.0, end=3.0, of=key):
        return {"footage": {"id": of, "start": start, "end": end, "sound": False}}

    bd, said = footage.checked(
        db,
        video,
        _plan(
            ("1.1", use(4.0, 9.0)),
            ("1.2", {"line": "Hi.", "speaker": "MARCUS", **use()}),
            ("1.3", use()),
            ("1.4", use(of="footage:0")),
            ("1.5", {}),
            ("1.6", use(of=other)),
            clips=[["1.1"], ["1.2"], ["1.3"], ["1.4"], ["1.5", "1.6"]],
        ),
    )
    shots = {s.id: s for s in bd.scenes[0].shots}
    real = shots["1.1"]  # inside the clip, as long as its stretch, the real thing only
    assert (real.footage.start, real.footage.end, real.seconds) == (4.0, 6.0, 2.0)
    assert (real.character_ids, real.screen_ids, bd.clips[0].seconds) == ([], [], 2)
    assert [s for s in shots if shots[s].footage] == ["1.1"]
    assert said == [f"Advice: Shot {i} is made, not real footage: {why}." for i, why in (
        ("1.2", "someone speaks in it"), ("1.3", f"{key} is already shown in this video"),
        ("1.4", "that clip isn't in the brand's footage"),
        ("1.6", "it shares its clip with other shots"))]  # fmt: skip
    video.look = "disney-pixar"
    _, said = footage.checked(db, video, _plan(("1.1", use())))
    assert said == ["Advice: Shot 1.1 is made, not real footage: real footage is a shot only "
                    "in UGC."]  # fmt: skip


def test_a_narrated_footage_shot_fills_its_narration_time_and_is_never_held_frozen(app, db, owner):
    video = _video(db, owner)  # a corner presenter's narration is the clock (QA on #1513)
    a, b, c = (f"{footage.KEY}{_described(app, db, owner, video.brand_id)}" for _ in range(3))

    def use(of, start, end, seconds):
        return {"seconds": seconds, "footage": {"id": of, "start": start, "end": end,
                                                "sound": False}}  # fmt: skip

    bd, said = footage.checked(db, video, _plan(
        ("1.1", use(a, 2.0, 4.0, 3.4)), ("1.2", use(b, 4.0, 5.0, 3.4)),
        ("1.3", use(c, 0.0, 6.0, 7.0))), timed=True)  # fmt: skip
    shots = {s.id: s for s in bd.scenes[0].shots}
    one, two = shots["1.1"].footage, shots["1.2"].footage
    assert (one.start, one.end) == (2.0, 5.4)  # from its in point, as long as its narration
    assert two.end - two.start == pytest.approx(3.4) and two.start < 4.0  # moved back inside
    assert shots["1.2"].seconds == 3.4 and shots["1.3"].footage is None  # never a frozen hold
    assert said == ["Advice: Shot 1.3 is made, not real footage: the clip is 6.0 s, shorter "
                    "than the shot's 7.0 s."]  # fmt: skip


def test_a_footage_shot_is_made_again_once_the_b_roll_look_isnt_ugc(app, db, owner):
    _described(app, db, owner, first_brand(owner))
    video = _made(app, db, owner)
    ((clip, _),) = footage.uses(clip_prompts.newest(db, video).data).items()
    video.broll_look = "disney-pixar"  # switched after the plan (QA on #1513)
    with pytest.raises(HTTPException) as no:  # checked again at the cut
        cut.ready(db, video, app.state.storage)
    assert no.value.detail == footage.DROPPED
    plan = clip_prompts.newest(db, video)
    assert footage.uses(plan.data) == {}
    assert any(p.endswith(f"{footage.NOT_UGC}.") for p in plan.problems)
    assert clip not in {r.clip_id for r in _clips(db, video)}  # its prompt is written now
    assert clip in clip_prompts.to_rewrite(db, video)


def test_a_refused_ai_description_says_why_on_the_card(app, db, owner, monkeypatch):
    def refused(*_, **__):
        raise HTTPException(409, "That's past your weekly allowance.")

    monkeypatch.setattr("app.routes.jobs.enqueue", refused)
    clip = _add(owner, first_brand(owner)).json()
    assert not clip["describing"] and "past your weekly allowance" in clip["note"]


def test_a_ugc_footage_shot_is_cut_free_and_laid_over_the_talker_like_any_b_roll(
    app, db, owner, tmp_path
):
    brand = first_brand(owner)
    clip_id = _described(app, db, owner, brand)
    video = _made(app, db, owner)
    plan = clip_prompts.newest(db, video).data
    ((clip, use),) = footage.uses(plan).items()  # the stand-in director picked it
    assert use == {"id": f"{footage.KEY}{clip_id}", "start": 0.0, "end": 3.0, "sound": False}
    row = next(r for r in _clips(db, video) if r.clip_id == clip)
    take = db.get(ClipTake, row.picked_take_id)
    job = db.get(Job, take.job_id)  # cut on our server, free, never a paid take or a watch
    assert (job.kind, job.provider, job.credits) == (footage.TAKE, "local", 0)
    assert take.made_with["footage"] == use and take.watch is None
    (tmp_path / "t.mp4").write_bytes(app.state.storage.get(db.get(StoredFile, take.file_id).key))
    from app.cut_render import _probe, seconds

    assert seconds((tmp_path / "t.mp4").read_bytes()) == pytest.approx(3, abs=0.15)
    assert not _probe(tmp_path, "t.mp4", "a:0", "codec_name")  # muted, as the plan said
    tl, _ = cut.timeline(db, video)  # #1512's overlay: over the talker's picture, never between
    laid = {o["take_id"] for o in cut.laid_over(tl)}
    assert take.id in laid and clip not in {p["clip_id"] for p in tl["pieces"]}
    takes = [o["take_id"] for o in tl.get("over", [])]
    assert len(takes) == len(set(takes))  # no take shown twice
    assert clip not in clip_prompts.to_rewrite(db, video, clip)  # no prompt to write
    assert clip_takes.take_credits(db, video, row) == 0
    with pytest.raises(HTTPException) as no:  # never remade
        clip_takes.take_input(db, video, row)
    assert no.value.detail == footage.NOT_MADE
    state = next(c for c in director.video_state(db, video)["clips"] if c["clip_id"] == clip)
    assert state["footage"] == use["id"] and state["takes"][-1]["verdict"] == "clean"


def test_the_cut_watch_is_told_a_real_footage_shot_and_never_remakes_it():
    spans = [{"clip_id": "c2", "start": 0.0, "end": 3.0, "take_id": 5, "real_footage": True,
              "other_takes": []}]  # fmt: skip
    pasted = {
        "clip_id": "c2",
        "start": 0.5,
        "end": 1.0,
        "kind": "screen",
        "evidence": "picture",
        "fix": "redo",
        "says": "c2: a still pasted in",
        "note": "Make it in the scene.",
    }
    (kept,) = watch_cut.checked({"findings": [pasted]}, spans, [], "")
    assert kept["fix"] == "keep" and kept["note"] == footage.WATCHED  # how to change its stretch


def test_a_take_given_the_real_clip_as_a_reference_is_priced_at_seedances_video_rate(
    app, db, owner
):
    video = _video(db, owner)
    video.look, video.video_model = "house", "seedance-2.5"  # it takes reference videos
    key = f"{footage.KEY}{_described(app, db, owner, video.brand_id)}"
    assert footage.assets(db, video)[key][1:] == ("video", [db.get(MediaUpload, int(
        key.split(":")[1])).file_id])  # fmt: skip
    m = get_model("seedance-2.5")
    plain = {"model": m.id, "input": {"resolution": "480p"}}
    priced = estimate(db, video.workspace_id, "video", Decimal(5), plain)
    dearer = estimate(db, video.workspace_id, "video", Decimal(5),
                      {**plain, "files": {"reference_videos": [1]}})  # fmt: skip
    assert dearer == Decimal(5) * m.credits_per_unit("480p", video_in=True) > priced
    made = {
        "input": {"duration": 5, "resolution": "480p", "reference_videos": ["https://x"]},
        "metrics": {},
    }  # its real cost, as Replicate's answer is read
    assert _usage(m, made, 1).cost_usd == Decimal(5) * m.price.with_video["480p"]
    assert "reference video" in project_context(db, video, "clip_prompts")[0][-1]


def test_a_local_cut_keeps_the_footages_sound_when_the_plan_asks(tmp_path):
    folder = tmp_path / "x"
    folder.mkdir()
    made = footage.cut(mp4("9:16", 4, sound=True), 1.0, 2.5, True, folder)
    from app.cut_render import _probe, seconds

    assert seconds(made.read_bytes()) == pytest.approx(1.5, abs=0.15)
    assert _probe(folder, made.name, "a:0", "codec_name")  # under the voice like B-roll
