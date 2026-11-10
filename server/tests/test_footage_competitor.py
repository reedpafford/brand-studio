"""A competitor's clip (Reed, 10 Nov): footage of another company's alarm, uploaded "labelled as
competitor", is never the brand's own: never listed as its footage, a shot or a Seedance
reference; a script that compares is told, in one line, what never to show as ours. A clip
marked one after a video used it leaves that video's plan. And in UGC a clip named as animation
(its folder or file name) is context, never a real footage shot. Stand-ins only."""

import pytest
from fastapi import HTTPException

from app import clip_prompts, cut, director_tools, footage, footage_rank, footage_shot
from app.models.accounts import User
from app.models.files import MediaUpload
from app.models.folders import Folder
from app.models.jobs import Job
from tests.conftest import first_brand, run_writer
from tests.helpers import product
from tests.test_footage import _add, _described, _plan
from tests.test_footage_rank import _clip, _says
from tests.test_omni_talker import _clips, _made, _video, songs_on  # noqa: F401 - fixture

CHEAP = "A competitor's cheap keychain alarm; its pin falls out and it stays silent."
OURS = "The PalaceGuard alarm on a keychain; its pin pulls and it shrieks."


def _shot(key: str):
    return _plan(("1.1", {"footage": {"id": key, "start": 0.0, "end": 2.0, "sound": False}}))


def test_a_clip_is_labelled_a_competitors_on_upload_and_on_the_tab(app, db, owner):
    brand = first_brand(owner)
    guard = product(db, brand, "PalaceGuard")
    db.commit()
    theirs = _add(owner, brand, competitor="true", product_id=guard).json()  # the API's field
    assert theirs["competitor"] and theirs["product_id"] is None  # never one of ours
    job = db.get(Job, db.get(MediaUpload, theirs["id"]).describe_job_id)
    assert "<competitor>yes</competitor>" in job.input["prompt"]
    assert "<products>\n(none)\n</products>" in job.input["prompt"]  # the AI can't call it ours
    run_writer(app, db)
    assert owner.get(f"/brands/{brand}/footage").json()[0]["product_id"] is None
    ours = _add(owner, brand, description=OURS, product_id=guard).json()
    assert not ours["competitor"]
    url = f"/brands/{brand}/footage/{ours['id']}"
    marked = owner.patch(url, json={"competitor": True}).json()  # the tab's toggle
    assert marked["competitor"] and marked["product_id"] is None
    assert marked["description"] == "" and "competitor" in marked["note"]  # its words named ours
    back = owner.patch(url, json={"competitor": False, "product_id": guard}).json()
    assert (back["competitor"], back["product_id"]) == (False, guard)


def test_a_competitors_clip_is_never_listed_shot_or_referenced_as_the_brands(app, db, owner):
    video = _video(db, owner)
    video.video_model = "seedance-2.5"  # it takes reference videos
    ours = _described(app, db, owner, video.brand_id, OURS)
    theirs = _described(app, db, owner, video.brand_id, CHEAP, competitor="true")
    _says(db, video, "MAYA: My keychain alarm's pin falls out. It stays silent.")  # their words
    key = f"{footage.KEY}{theirs}"
    assert [r.id for r in footage.relevant(db, video)] == [ours]
    for step in ("director", "breakdown", "clip_prompts"):
        told = footage.block(db, video, step)
        assert key not in told and "silent" not in told and footage_rank.RIVALS not in told
    assert set(footage.assets(db, video)) == {f"{footage.KEY}{ours}"}  # never a reference
    me = db.get(User, video.created_by_id)
    found = director_tools.run(db, me, video, {"tool": "find_footage", "note": "pin silent"}, None)
    assert key not in found
    _, said = footage_shot.checked(db, video, _shot(key))
    assert said == ["Advice: Shot 1.1 is made, not real footage: that clip is a competitor's "
                    "product."]  # fmt: skip


def test_a_script_about_other_alarms_is_told_what_never_to_show_as_ours(app, db, owner):
    video = _video(db, owner)
    theirs = _described(app, db, owner, video.brand_id, CHEAP, competitor="true")
    _says(db, video, "MAYA: Other alarms just sit there when you need them.")
    told = footage.block(db, video, "director")  # no footage of ours: still told
    assert told == f"<footage>\n{footage_rank.RIVALS}{CHEAP}\n</footage>"
    assert f"{footage.KEY}{theirs}" not in told  # in words only: never a shot or reference
    _described(app, db, owner, video.brand_id, OURS)
    _says(db, video, "MAYA: I bought the cheapest alarm online. Never again.")
    assert footage.block(db, video, "breakdown").splitlines()[-2] == footage_rank.RIVALS + CHEAP
    for said in ("Unlike other brands, this one shrieks.", "Most alarms on Amazon are junk.",
                 "My old knock-off never worked.", "My old keychain alarm failed."):  # fmt: skip
        _says(db, video, f"MAYA: {said}")
        assert footage_rank.RIVALS in footage.block(db, video, "breakdown"), said
    for said in ("My brother and I looked at each other and laughed.", "The other night I was "
                 "walking home.", "Other people stare at their phones.", "My old friend's car.",
                 "The other day it's raining.", "I won the dance competition."):  # fmt: skip
        _says(db, video, f"MAYA: {said}")
        assert footage_rank.RIVALS not in footage.block(db, video, "breakdown"), said


def _mark(db, owner, clip_id: int, how: str) -> None:
    row = db.get(MediaUpload, clip_id)
    url = f"/brands/{row.brand_id}/footage/{clip_id}"
    if how == "competitor":
        assert owner.patch(url, json={"competitor": True}).status_code == 200
    elif how == "deleted":
        assert owner.delete(url).status_code == 204
    else:  # filed in an Animation folder
        folder = Folder(workspace_id=row.workspace_id, brand_id=row.brand_id, name="Animation",
                        footage=True, created_by_id=row.created_by_id)  # fmt: skip
        db.add(folder)
        db.flush()
        row.folder_id = folder.id
        db.commit()
    db.expire_all()


@pytest.mark.parametrize(("how", "why"), [
    ("competitor", "that clip is a competitor's product"),
    ("deleted", "that clip isn't in the brand's footage"),
    ("animated", "that clip is animated, not real")])  # fmt: skip
def test_a_clip_marked_after_a_video_used_it_leaves_that_videos_plan(app, db, owner, how, why):
    clip_id = _described(app, db, owner, first_brand(owner))
    video = _made(app, db, owner)  # the stand-in director plans it as a UGC footage shot
    ((clip, _),) = footage_shot.uses(clip_prompts.newest(db, video).data).items()
    _mark(db, owner, clip_id, how)  # after its take was cut (QA on #1518)
    with pytest.raises(HTTPException) as no:  # checked again at the cut
        cut.ready(db, video, app.state.storage)
    assert no.value.detail == footage_shot.DROPPED
    plan = clip_prompts.newest(db, video)
    assert footage_shot.uses(plan.data) == {}
    assert any(p.endswith(f"is made, not real footage: {why}.") for p in plan.problems)
    assert clip not in {r.clip_id for r in _clips(db, video)}  # its prompt is written now
    assert clip in clip_prompts.to_rewrite(db, video)


def test_an_animated_clip_is_context_in_ugc_but_never_a_real_footage_shot(app, db, owner):
    video = _video(db, owner)
    folder = Folder(workspace_id=video.workspace_id, brand_id=video.brand_id, name="Animation",
                    footage=True, created_by_id=video.created_by_id)  # fmt: skip
    db.add(folder)
    db.flush()
    drawn = [_clip(db, video, folder.id, "A girl walks home at night.", "walk.mp4"),
             _clip(db, video, None, "A boy runs to the bus at night.", "Pixar_bus.mp4"),
             _clip(db, video, None, "A dog sleeps at night.", "cartoon-b.mp4")]  # fmt: skip
    real = _clip(db, video, None, "An animated crowd cheers a girl walking home at night down a "
                 "quiet street.", "real.mp4")  # fmt: skip  # its words say animated: still real
    _says(db, video, "MAYA: I walk home at night alone, down a quiet street.")
    given = [r.id for r in footage.relevant(db, video)]
    assert given[0] == real and set(drawn) <= set(given)  # context, ranked below the real one
    for clip in drawn:
        _, said = footage_shot.checked(db, video, _shot(f"{footage.KEY}{clip}"))
        assert said == ["Advice: Shot 1.1 is made, not real footage: that clip is animated, "
                        "not real."]  # fmt: skip
    bd, said = footage_shot.checked(db, video, _shot(f"{footage.KEY}{real}"))
    assert not said and bd.scenes[0].shots[0].footage
