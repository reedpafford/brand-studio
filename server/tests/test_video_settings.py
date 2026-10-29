"""Video settings (flows VS1): the choices with their prices, the confirm, the switch with its
refusals and Undo, what goes out of date (and comes back), a no-lip-sync model on a song
video, the script's language and the brand's default cast. Free, on the stand-ins."""

from sqlalchemy import select

from app import video_settings as vs
from app.models.brands import BrandScreen
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ClipTake, ProjectClip
from app.models.credits import CreditLimits
from app.models.jobs import Job
from app.models.projects import Project
from app.models.storyboards import StoryboardFrame
from app.routes.video_settings import NOT_YOURS
from tests.test_breakdown import BREAKDOWN
from tests.test_looks import _a_file
from tests.test_script_produce import _published
from tests.test_song_takes import _video, _work, song  # noqa: F401 - fixture

AUTO = {"model": "seedance-2.5", "aspect_ratio": "9:16", "products": {}}


def _made(owner, editor, db, take_products=None):
    """A video with one still and one picked take, both made with today's settings."""
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    pid = editor.post(f"{base}/drafts/0/produce").json()["project_id"]
    bd = db.query(BreakdownVersion).filter_by(project_id=pid).one()
    job = Job(workspace_id=1, kind="video", provider="fake", input={}, credits=0)
    db.add(job)
    db.flush()
    db.add(StoryboardFrame(project_id=pid, breakdown_id=bd.id, clip_id="c1", shot_id="1.1",
                           prompt="A still.", file_id=_a_file(db), approved=True,
                           made_with={**AUTO, "model": "nano-banana-2.1"}))  # fmt: skip
    clip = ProjectClip(project_id=pid, breakdown_id=bd.id, clip_id="c1", seconds=5,
                       prompt="A clip.", approved=True)  # fmt: skip
    db.add(clip)
    db.flush()
    take = ClipTake(clip_id=clip.id, number=1, job_id=job.id, file_id=_a_file(db),
                    made_with={**AUTO, "products": take_products or {}})  # fmt: skip
    db.add(take)
    db.flush()
    clip.picked_take_id, clip.file_id = take.id, take.file_id
    db.commit()
    return f"/projects/{pid}", pid


def test_the_choices_carry_their_prices_and_the_scripts_language(owner, editor, db):
    video, _ = _made(owner, editor, db)
    got = editor.get(f"{video}/settings").json()
    assert got["video_model"] is None and got["image_model"] is None  # Auto
    models = {m["id"]: m for m in got["video_models"]}
    assert models["seedance-2.5"]["default"] and models["seedance-2.5"]["lip_sync"]
    assert not models["seedance-2.0"]["lip_sync"]  # "No lip-sync"
    assert (
        models["seedance-2.0"]["credits_per_second"] < models["seedance-2.5"]["credits_per_second"]
    )
    assert {m["id"] for m in got["image_models"]} == {"nano-banana-2.1", "nano-banana-pro"}
    assert got["language"] == "en" and "1:1" in got["shapes"]


def test_a_model_switch_outdates_its_clips_and_switching_back_brings_them_back(owner, editor, db):
    video, pid = _made(owner, editor, db)
    url = f"{video}/settings"
    seen = editor.post(f"{url}/preview", json={"video_model": "seedance-2.0"}).json()
    assert (seen["clips_out_of_date"], seen["stills_out_of_date"]) == (1, 0)
    assert seen["to_finish_credits"] > seen["was_credits"] and not seen["reason"]
    switched = editor.post(url, json={"video_model": "seedance-2.0"}).json()
    assert switched["settings"]["video_model"] == "seedance-2.0"
    assert switched["was"] == {"video_model": None}
    (clip,) = editor.get(f"{video}/clips").json()
    assert clip["take_stale"] and not clip["approved"]
    assert editor.get(f"{video}/storyboard").json()[0]["approved"]  # a still isn't a clip
    made = editor.post(f"{video}/video")
    assert (made.status_code, made.json()["detail"]) == (409, vs.OTHER.format("1 clip was"))
    assert db.get(Project, pid).video_model == "seedance-2.0"

    editor.post(url, json=switched["was"])  # Undo: Auto again, the take is current
    assert editor.get(f"{video}/clips").json()[0]["approved"]


def test_a_shape_switch_outdates_everything_made_and_undo_brings_it_back(owner, editor, db):
    video, _ = _made(owner, editor, db)
    seen = editor.post(f"{video}/settings/preview", json={"aspect_ratio": "1:1"}).json()
    assert (seen["stills_out_of_date"], seen["clips_out_of_date"]) == (1, 1)
    was = editor.post(f"{video}/settings", json={"aspect_ratio": "1:1"}).json()["was"]
    assert editor.get(f"{video}/storyboard").json()[0]["still_stale"]
    editor.post(f"{video}/settings", json=was)
    assert not editor.get(f"{video}/storyboard").json()[0]["still_stale"]


def test_a_flavour_switch_outdates_only_what_shows_the_bag(owner, editor, db):
    video, pid = _made(owner, editor, db, take_products={"bag": "Chicken"})
    brand = db.get(Project, pid).brand_id
    for variant in ("Chicken", "Peanut butter"):
        db.add(BrandScreen(brand_id=brand, name=f"Bag {variant}", file_id=_a_file(db),
                           product="bag", variant=variant))  # fmt: skip
    db.commit()
    seen = editor.post(f"{video}/settings/preview",
                       json={"product_variants": {"bag": "Peanut butter"}}).json()  # fmt: skip
    assert (seen["stills_out_of_date"], seen["clips_out_of_date"]) == (0, 1)
    assert editor.post(f"{video}/settings/preview",
                       json={"product_variants": {"bag": "Kale"}}).status_code == 422  # fmt: skip


def test_over_the_cap_is_refused_with_the_reason(owner, editor, db):
    video, _ = _made(owner, editor, db)
    db.add(CreditLimits(workspace_id=1, per_video_max_credits=1))
    db.commit()
    seen = editor.post(f"{video}/settings/preview", json={"aspect_ratio": "1:1"}).json()
    assert seen["over_cap"] and seen["reason"] == vs.OVER_CAP.format(1)
    no = editor.post(f"{video}/settings", json={"aspect_ratio": "1:1"})
    assert (no.status_code, no.json()["detail"]) == (409, vs.OVER_CAP.format(1))
    # Undo puts back what the video already had, even over the limit (Flow-QA's case)
    was = editor.post(f"{video}/settings", json={"aspect_ratio": "1:1", "undo": True})
    assert was.status_code == 200 and was.json()["was"] == {"aspect_ratio": "9:16"}
    back = editor.post(f"{video}/settings", json={**was.json()["was"], "undo": True})
    assert back.json()["settings"]["aspect_ratio"] == "9:16"


def test_who_may_switch_and_what_may_be_sent(app, owner, editor, db):
    from fastapi.testclient import TestClient

    from tests.conftest import PASSWORD

    video, _ = _made(owner, editor, db)
    url = f"{video}/settings"
    assert owner.post(url, json={"image_model": "nano-banana-pro"}).status_code == 200  # any
    token = owner.post("/team/invites", json={"email": "other@example.com"}).json()["token"]
    with TestClient(app) as other:
        other.post("/auth/accept-invite", json={"token": token, "name": "O", "password": PASSWORD})
        no = other.post(url, json={"aspect_ratio": "1:1"})
        assert (no.status_code, no.json()["detail"]) == (403, NOT_YOURS)
        assert other.get(url).status_code == 200  # reading is fine
    assert editor.post(url, json={"aspect_ratio": "1:1", "look": "house"}).status_code == 422
    assert editor.post(url, json={"video_model": "nope"}).status_code == 422
    off = editor.post(url, json={"look": "zack-d"})  # the look's own rules: Off for editors
    assert off.status_code == 409


def test_a_no_lip_sync_model_turns_sung_shots_to_b_roll_and_undo_turns_them_back(
    app,
    db,
    owner,
    editor,
    song,  # noqa: F811
):
    video = _video(app, db, owner, editor, song)
    pid = int(video.rsplit("/", 1)[1])
    row = db.scalars(select(BreakdownVersion).where(BreakdownVersion.project_id == pid)
                     .order_by(BreakdownVersion.id.desc())).first()  # fmt: skip
    first, second = list(row.data["song"]["shots"])[:2]
    shots = {sid: {**t, "sung": sid in (first, second)}
             for sid, t in row.data["song"]["shots"].items()}  # fmt: skip
    row.data = {**row.data, "song": {**row.data["song"], "shots": shots}}
    db.commit()

    seen = editor.post(f"{video}/settings/preview", json={"video_model": "seedance-2.0"}).json()
    assert seen["sung_to_broll"] == 2
    was = editor.post(f"{video}/settings", json={"video_model": "seedance-2.0"}).json()["was"]
    db.expire_all()
    newest = db.scalars(select(BreakdownVersion).where(BreakdownVersion.project_id == pid)
                        .order_by(BreakdownVersion.id.desc())).first()  # fmt: skip
    assert not any(t["sung"] for t in newest.data["song"]["shots"].values())

    plan = {k: v for k, v in newest.data.items() if k != "song"}  # the editor changes one shot
    for scene in plan["scenes"]:
        for shot in scene["shots"]:
            if shot["id"] == second:
                shot["action"] = "The dog runs to the bowl instead."
    assert editor.put(f"{video}/breakdown", json=plan).status_code == 200

    editor.post(f"{video}/settings", json=was)  # Undo: back to Auto, which lip-syncs
    db.expire_all()
    newest = db.scalars(select(BreakdownVersion).where(BreakdownVersion.project_id == pid)
                        .order_by(BreakdownVersion.id.desc())).first()  # fmt: skip
    song_shots = newest.data["song"]["shots"]
    assert song_shots[first]["sung"]  # back to Sung
    assert not song_shots[second]["sung"]  # the editor changed it: stays B-roll
    assert db.get(Project, pid).sung_flipped == []


def test_a_new_script_is_in_its_brands_language_and_a_new_video_has_its_cast(owner):
    brand = owner.get("/brands").json()[0]
    owner.patch(f"/brands/{brand['id']}", json={"default_language": "es"})
    made = owner.post("/scripts", json={"brand_id": brand["id"], "title": "Hola"}).json()
    assert made["language"] == "es"
    own = owner.post("/scripts", json={"brand_id": brand["id"], "title": "Hi",
                                       "language": "en"}).json()  # fmt: skip
    assert own["language"] == "en"
    copy = owner.post(f"/scripts/{made['id']}/duplicate").json()
    assert copy["language"] == "es"

    dog = owner.post("/library/character", json={"name": "Biscuit"}).json()["id"]
    gone = owner.post("/library/character", json={"name": "Rex"}).json()["id"]
    owner.patch(f"/brands/{brand['id']}", json={"default_cast": [dog, gone]})
    owner.delete(f"/library/character/{gone}")
    video = owner.post("/projects", json={"brand_id": brand["id"], "name": "V"}).json()
    assert video["cast_ids"] == [dog]  # the brand's live default cast
    picked = owner.post("/projects", json={"brand_id": brand["id"], "name": "W",
                                           "cast_ids": []}).json()  # fmt: skip
    assert picked["cast_ids"] == [dog]  # an empty pick is the brand's too


def test_a_take_made_through_its_job_records_what_it_was_made_with(
    app,
    db,
    owner,
    editor,
    song,  # noqa: F811
):
    from tests.test_song_final_cut import _clips_made

    video = _video(app, db, owner, editor, song)
    _clips_made(app, db, editor, video)
    take = db.scalars(select(ClipTake).order_by(ClipTake.id)).first()
    assert take.made_with["model"] == "seedance-2.5" and take.made_with["aspect_ratio"] == "9:16"
    assert "sung_shots" in take.made_with and "products" in take.made_with
    assert not any(c["take_stale"] for c in editor.get(f"{video}/clips").json())


def test_picking_back_an_earlier_still_brings_back_what_it_was_made_with(owner, editor, db):
    video, pid = _made(owner, editor, db)
    frame = db.query(StoryboardFrame).filter_by(project_id=pid).one()
    old = _a_file(db)
    frame.earlier = [
        {
            "file_id": old,
            "prompt": "Old.",
            "made_with": {**AUTO, "model": "nano-banana-2.1", "aspect_ratio": "1:1"},
        }
    ]
    db.commit()  # fmt: skip
    picked = editor.post(f"{video}/storyboard/frames/{frame.id}/pick", json={"file_id": old})
    assert picked.status_code == 200 and picked.json()["still_stale"]  # made in 1:1, video 9:16
    db.expire_all()
    assert db.get(StoryboardFrame, frame.id).earlier[0]["made_with"]["aspect_ratio"] == "9:16"


def test_make_this_version_takes_the_settings_and_a_no_lip_sync_plan_has_no_sung_shots(
    app,
    db,
    owner,
    editor,
    song,  # noqa: F811
    monkeypatch,
):
    from app import song_breakdown
    from tests.test_song_takes import _approve_plan, _style

    split = song_breakdown.split

    def one_sung(bd, take_id):  # the stand-in plan has no Sung shot: make its first one Sung
        plan, part = split(bd, take_id)
        first = next(iter(part["shots"]))
        return plan, {
            **part,
            "shots": {**part["shots"], first: {**part["shots"][first], "sung": True}},
        }

    monkeypatch.setattr(song_breakdown, "split", one_sung)
    _style(owner, song, "pop")
    owner.post(f"{song}/songs", json={})
    _work(app, db)
    owner.post(f"{song}/approve")
    owner.post(f"{song.rsplit('/drafts', 1)[0]}/publish")
    assert editor.post(f"{song}/produce", json={"video_model": "nope"}).status_code == 422
    made = editor.post(
        f"{song}/produce", json={"video_model": "seedance-2.0", "aspect_ratio": "1:1"}
    )
    assert made.status_code == 201, made.text  # the refused try left the version free
    pid = made.json()["project_id"]
    _work(app, db)  # the plan
    _approve_plan(app, db, editor, f"/projects/{pid}")  # its shots
    db.expire_all()
    project = db.get(Project, pid)
    assert (project.video_model, project.aspect_ratio) == ("seedance-2.0", "1:1")
    rows = db.scalars(select(BreakdownVersion).where(BreakdownVersion.project_id == pid)).all()
    assert rows and not any(
        t["sung"] for r in rows for t in r.data.get("song", {}).get("shots", {}).values()
    )
    assert len(project.sung_flipped) == 1  # remembered: Auto (lip-sync) turns it back


def test_make_this_version_refuses_an_off_look_for_an_editor(owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    off = editor.post(f"{base}/drafts/0/produce", json={"look": "zack-d"})
    assert off.status_code == 409
    made = editor.post(f"{base}/drafts/0/produce", json={"image_model": "nano-banana-pro"})
    assert made.status_code == 201
    assert db.get(Project, made.json()["project_id"]).image_model == "nano-banana-pro"


def test_make_this_versions_price_line_follows_the_picks(owner, editor, db):
    base, _ = _published(owner, db, breakdown=BREAKDOWN)
    url = f"{base}/drafts/0/estimate"
    auto = editor.post(url).json()
    shown = editor.get(base).json()["versions"][0]["estimate_credits"]
    assert auto == {"credits": shown, "over_cap": False, "reason": ""}  # the card's figure
    cheaper = editor.post(url, json={"video_model": "seedance-2.0"}).json()
    assert 0 < cheaper["credits"] < auto["credits"]
    assert editor.post(url, json={"look": "zack-d"}).status_code == 409  # Off for editors
    assert editor.post(url, json={"video_model": "nope"}).status_code == 422
    db.add(CreditLimits(workspace_id=1, per_video_max_credits=1))
    db.commit()
    over = editor.post(url).json()
    assert over["over_cap"] and over["reason"] == vs.OVER_CAP.format(1)
    assert db.query(Project).count() == 0  # nothing is made
    models = {m["id"]: m["lip_sync"] for m in editor.get("/models?kind=video").json()}
    assert models["seedance-2.5"] and not models["seedance-2.0"]
