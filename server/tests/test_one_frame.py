"""One starting frame for a talker in one spot (Reed, 9 Nov: "the best fix for that request would
be using the same starting frame - as long as the hands are in like a neutral position"). Video
315's 5 Omni pieces of a man in his parked car each had their own still, so each showed another
car. Stand-ins only: no paid calls."""

import copy
from types import SimpleNamespace

from app import clip_prompts, one_frame, storyboard
from app.clip_takes import take_input
from app.models.breakdowns import BreakdownVersion
from app.models.clips import ProjectClip
from app.models.files import StoredFile
from app.models.freestyles import Freestyle
from app.models.jobs import Job, JobStatus
from app.models.projects import Project
from app.models.script_library import ScriptDraft
from app.models.storyboards import StoryboardFrame
from app.routes.estimate import _shots, version_cost
from tests.conftest import first_brand
from tests.test_breakdown import _shot
from tests.test_cast_roles import _video
from tests.test_freestyle_dialogue import _run

WORDS = ("so here is the thing about my brother in law that nobody at the table wanted to hear "
         "out loud this year and honestly I was the worst of them all")  # fmt: skip  # ~6 s
SCRIPT = "\n".join(f"MARCUS: {WORDS} part {n}." for n in range(1, 4))  # each line its own piece


def _talks(id: str, who: str, **more) -> dict:
    return {**_shot(id, [1], "Mom", "Fine.", 3), "character_ids": [who], **more}


def _ugc(owner, editor, db, look: str = "ugc", own: str = "", **c3) -> tuple[Project, dict]:
    """Mom (Mia) talks to camera in her kitchen in c1, c2 and c3, and c4 is a wordless B-roll
    shot of the bowl; `c3`: more for c3's first shot (a screen); `own`: c3's own_frame."""
    pid, mia, _ = _video(owner, editor, db)
    project = db.get(Project, pid)
    project.look = look
    me = f"char:{mia}"
    shots = [_talks("1.1", me), _talks("1.2", me), _talks("1.3", me, **c3),
             {**_shot("1.4", [2], None, None, 2), "character_ids": []}]  # fmt: skip
    data = {"hook": "x", "scenes": [{"id": 1, "heading": "INT. KITCHEN — DAY", "look": "Grey.",
                                     "shots": shots}],
            "clips": [{"id": f"c{n}", "shot_ids": [f"1.{n}"], "seconds": 3, "seam": "-"}
                      for n in range(1, 5)]}  # fmt: skip
    data["clips"][2]["own_frame"] = own or None
    db.add(BreakdownVersion(project_id=pid, script_version=1, source="edit", data=data))
    db.commit()
    return project, data


def _newest(db, project: Project) -> BreakdownVersion:
    return (
        db.query(BreakdownVersion)
        .filter_by(project_id=project.id)
        .order_by(BreakdownVersion.id.desc())
        .first()
    )


def _storyboard(db, project: Project, data: dict) -> list[StoryboardFrame]:
    """The storyboard Claude wrote, a frame a clip, saved as the step saves it."""
    bd = _newest(db, project)
    frames = [{"clip_id": c["id"], "shot_id": c["shot_ids"][0], "prompt": "Mom mid-laugh.",
               "reference_ids": data["scenes"][0]["shots"][n]["character_ids"]}
              for n, c in enumerate(data["clips"])]  # fmt: skip
    job = Job(
        workspace_id=project.workspace_id,
        kind="write-claude",
        provider="claude",
        project_id=project.id,
        status=JobStatus.succeeded,
        output={"frames": frames},
        input={"step": "storyboard", "project_id": project.id, "breakdown_id": bd.id},
    )
    db.add(job)
    db.flush()
    storyboard.save_frames(db, job)
    db.commit()
    return db.query(StoryboardFrame).filter_by(project_id=project.id).all()


def test_a_ugc_talkers_pieces_open_on_one_still(app, db, owner):
    body = {"type": "dialogue", "look": "ugc", "shape": "9:16", "text": SCRIPT,
            "brand_id": first_brand(owner)}  # fmt: skip
    fs = owner.post("/freestyles", json=body).json()
    _run(app, db, ticks=120)
    assert owner.get(f"/freestyles/{fs['id']}").json()["status"] == "delivered"
    video = db.get(Project, db.get(Freestyle, fs["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    jobs = db.query(Job).filter(Job.project_id == video.id).all()
    (still,) = [j for j in jobs if j.input.get("step") == "frame"]  # drawn once
    shared = still.output["file_ids"][0]
    takes = [j for j in jobs if j.input.get("step") == "clip_take"]
    firsts = [j.input["files"]["reference_images"][0] for j in takes]
    assert len(takes) >= 2 and set(firsts) == {shared}  # each piece's [Image1]


def test_the_shared_still_is_drawn_at_rest(owner, editor, db):
    project, data = _ugc(owner, editor, db)
    frames = {f.clip_id: f for f in _storyboard(db, project, data)}
    assert sorted(frames) == ["c1", "c4"]  # c2 and c3 open on c1's still: none of their own
    assert frames["c1"].prompt.endswith(one_frame.NEUTRAL)
    for words in ("mouth closed", "hands relaxed and low", "phone held steady at arm's length"):
        assert words in frames["c1"].prompt
    assert one_frame.NEUTRAL not in frames["c4"].prompt  # the B-roll is its own moment


def test_an_insert_keeps_its_own_frame(owner, editor, db):
    project, data = _ugc(owner, editor, db, own="an insert of the phone screen")
    assert one_frame.shared(db, project) == {"c2": "c1"}  # c3: the plan says why
    project, data = _ugc(owner, editor, db, screen_ids=["screen:1"])
    assert one_frame.shared(db, project) == {"c2": "c1"}  # c3 opens on a screen
    project.look = "house"
    assert one_frame.shared(db, project) == {}  # another style: each piece its own still


def test_the_owners_one_spot_note_puts_every_talker_piece_on_it(owner, editor, db):
    project, _ = _ugc(owner, editor, db, look="house", own="an insert of the phone")
    for loose in ("The camera stays on her face.", "The camera still pans to the door.",
                  "Use the same angle as clip 2.", "Set in one location."):  # fmt: skip
        project.director_chat = [{"by": 1, "text": loose}]
        assert one_frame.shared(db, project) == {}  # not an ask for one spot
    for ask in ("Keep the camera in one spot please.", "A static camera.", "Don't move the "
                "camera.", "Use the same starting frame for every clip."):  # fmt: skip
        project.director_chat = [{"by": 1, "text": ask}]
        assert one_frame.shared(db, project) == {"c2": "c1", "c3": "c1"}  # the B-roll c4 stays
    data = copy.deepcopy(_newest(db, project).data)  # c3 at night in the park: its own place
    data["scenes"].append({**data["scenes"][0], "id": 2, "heading": "EXT. PARK — NIGHT",
                           "shots": [data["scenes"][0]["shots"].pop(2)]})  # fmt: skip
    assert one_frame.shared(db, project, data) == {"c2": "c1"}  # the place always counts


def test_a_video_made_before_keeps_each_pieces_own_still(owner, editor, db):
    """QA on #1494: a finished UGC video whose pieces each have a still never goes out of date."""
    project, data = _ugc(owner, editor, db)
    files = [StoredFile(workspace_id=project.workspace_id, key=f"still-{c['id']}", size=1,
                        filename="still.png", content_type="image/png", sha256="0" * 64)
             for c in data["clips"]]  # fmt: skip
    db.add_all(files)
    db.flush()
    for clip, still in zip(data["clips"], files, strict=True):
        db.add(StoryboardFrame(project_id=project.id, breakdown_id=_newest(db, project).id,
                               clip_id=clip["id"], shot_id=clip["shot_ids"][0], prompt="x",
                               reference_ids=[], file_id=still.id))  # fmt: skip
    db.commit()
    known = clip_prompts.assets(db, project)
    assert [known[f"frame:c{n}"][2] for n in (1, 2, 3)] == [[f.id] for f in files[:3]]
    assert one_frame.sharing(db, project) == {}


def test_the_estimate_counts_one_still(owner, editor, db):
    project, data = _ugc(owner, editor, db)
    stage = next(s for s in owner.get(f"/projects/{project.id}/estimate").json()["stages"]
                 if s["stage"] == "storyboard")  # fmt: skip
    assert stage["note"].endswith(" 2 stills")  # c1's, shared by c2 and c3, and c4's
    pieces = [SimpleNamespace(clip_id=c) for c in ("c2", "c3")]  # a revision remaking them
    assert (_shots(db, project, pieces), _shots(db, project, pieces, looks=1)) == (0, 1)
    draft = db.get(ScriptDraft, project.script_draft_id)
    shared = version_cost(db, draft, project)  # the start card's, from the video's own plan
    apart = copy.deepcopy(data)
    for clip in apart["clips"]:  # every piece with its own still
        clip["own_frame"] = "another shot"
    _newest(db, project).data = apart
    db.commit()
    one = storyboard.still_credits(db, project.workspace_id, storyboard.image_model(project))
    assert version_cost(db, draft, project) - shared == 2 * one


def test_a_remake_of_one_piece_reuses_the_shared_still(owner, editor, db):
    project, data = _ugc(owner, editor, db, look="house")  # where Mia's sheet is drawn
    project.goal = "Her talking to us, the camera in one spot."
    frames = {f.clip_id: f for f in _storyboard(db, project, data)}
    frames["c1"].file_id = still = db.query(StoredFile).order_by(StoredFile.id).first().id
    bd = _newest(db, project)
    row = ProjectClip(
        project_id=project.id,
        breakdown_id=bd.id,
        clip_id="c3",
        seconds=3,
        prompt="References: [Image1] is the first frame.\nShots: Mom talks.",
        references=[{"kind": "image", "id": "frame:c3", "role": "first frame"}],
    )
    db.add(row)
    db.commit()
    sent = take_input(db, project, row, "Smile at the end.", check=False)["files"]
    assert still in [f for ids in sent.values() for f in ids]
