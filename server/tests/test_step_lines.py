"""S3-04's step lines, as drawn: the cast with its voice and whether it's the brand's saved
cast, the stills redrawn and why, and the clip prompts' models with why each. All on the
stand-ins (no paid call)."""

from app import director, host
from app.cast_roles import pick, video_slots
from app.models.brands import Brand
from app.models.clips import ProjectClip
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.songs import SongTake
from app.models.voices import Voice
from tests.conftest import upload
from tests.test_run_progress import _done, _progress


def _step(client, pid: int, key: str) -> dict:
    return next(s for s in _progress(client, pid)["steps"] if s["key"] == key)


def _looks(db, project) -> list[LibraryItem]:
    return [db.get(LibraryItem, pick(db, project, s)) for s in video_slots(db, project)]


def test_the_cast_line_says_whether_the_cast_is_saved_or_made_for_this_video(app, db, owner,
                                                                           editor):  # fmt: skip
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    brand = db.get(Brand, project.brand_id)
    assert _step(owner, pid, "cast")["text"] == "Cast: Mom and Nate"  # neither: nothing said
    for item in _looks(db, project):
        item.owner_project_id = pid  # made for this video only
    db.commit()
    assert _step(owner, pid, "cast")["text"] == "Cast: Mom and Nate, made for this video"
    mom, nate = _looks(db, project)
    mom.owner_project_id, mom.brands = None, [brand]  # one saved, one not: nothing said
    db.commit()
    assert _step(owner, pid, "cast")["text"] == "Cast: Mom and Nate"
    nate.owner_project_id, nate.brands = None, [brand]
    db.commit()
    assert _step(owner, pid, "cast")["text"] == f"Cast: Mom and Nate, both saved in {brand.name}"
    nate.owner_script_id = db.get(Project, pid).reel_script_id or 1  # kept by a script: not saved
    db.commit()
    assert _step(owner, pid, "cast")["text"] == "Cast: Mom and Nate"
    nate.owner_script_id, nate.archived = None, True  # an archived look: that role isn't cast
    db.commit()
    assert _step(owner, pid, "cast")["text"] == f"Cast: Mom, saved in {brand.name}"


def test_a_presenters_cast_line_names_the_presenter_and_the_voice(app, db, owner, editor,
                                                                 monkeypatch):  # fmt: skip
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    brand = db.get(Brand, project.brand_id)
    for item in _looks(db, project):
        item.owner_project_id, item.brands = None, [brand]
    face = LibraryItem(workspace_id=project.workspace_id, kind=Kind.character, name="Dr. Pickle",
                       brands=[brand])  # fmt: skip
    clone = Voice(workspace_id=project.workspace_id, brand_id=brand.id, name="Dr. Pickle",
                  kind="cloned", provider="minimax", provider_voice_id="v1")  # fmt: skip
    style = Voice(workspace_id=project.workspace_id, brand_id=None, look="dr-pickle",
                  name="Dr. Pickle", kind="cloned", provider="minimax",
                  provider_voice_id="v2")  # fmt: skip
    db.add_all([face, clone, style])
    db.commit()
    monkeypatch.setattr(host, "presents", lambda db, p: True)
    monkeypatch.setattr(host, "host_look", lambda db, p: db.get(LibraryItem, face.id))
    project.voice = f"voice:{clone.id}"  # the brand's own clone
    db.commit()
    said = _step(owner, pid, "cast")["text"]
    assert said == f"Cast: Dr. Pickle, Mom, Nate and the cloned voice, all saved in {brand.name}"
    project.voice = f"voice:{style.id}"  # the style's own clone, listed with the brand's voices
    db.commit()
    assert _step(owner, pid, "cast")["text"] == said
    project.voice = "stock:Roger"  # an app voice: never the brand's to save, said apart
    db.commit()
    said = _step(owner, pid, "cast")["text"]
    assert (
        said
        == f"Cast: Dr. Pickle, Mom and Nate, all saved in {brand.name}; read in the Roger voice"
    )
    project.voice = None  # no voice of its own and no style voice: none until its audition
    db.commit()
    assert _step(owner, pid, "cast")["text"] == f"Cast: Dr. Pickle, Mom and Nate, all saved in {
        brand.name}"  # fmt: skip
    job = db.query(Job).filter_by(project_id=pid).first()
    take = SongTake(draft_id=project.script_draft_id, project_id=pid, number=1, kind="narration",
                    voice="Roger", job_id=job.id, lyrics="", style_line="")  # fmt: skip
    db.add(take)
    db.flush()
    project.song_take_id, project.voice = take.id, "stock:Austin"  # read in Roger, set since
    db.commit()
    assert _step(owner, pid, "cast")["text"].endswith("; read in the Roger voice")  # as it was read


def test_stills_say_how_many_were_redrawn_and_why_in_plain_words(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    turns = director.turns(db, project)
    run = turns[-1].input[director.RUN]
    turns[-1].input = {**turns[-1].input, director.RUN: {**run, "redraws": {"1.1": 2}}}
    findings = [{"shot_id": "1.1", "problem": "The capsule label faced away.", "note": "n"},
                {"shot_id": "9.9", "problem": "Not redrawn.", "note": "n"}]  # fmt: skip
    review = Job(
        workspace_id=project.workspace_id,
        kind="check-claude",
        provider="fake",
        project_id=pid,
        credits=0,
        status=JobStatus.succeeded,
        input={"step": "review_stills"},
        output={"ready": False, "findings": findings},
    )
    db.add(review)
    db.commit()
    said = _step(owner, pid, "stills")["text"]
    assert said == "Stills: 1 drawn, 2 redrawn (the capsule label faced away)"
    review.output = {"ready": False, "findings": [
        {"shot_id": "1.1", "problem": "c1: Dr. Pickle's coat is green.", "note": "n"}]}  # fmt: skip
    db.commit()
    said = _step(owner, pid, "stills")["text"]  # a name keeps its capital; no raw clip id
    assert said == "Stills: 1 drawn, 2 redrawn (Dr. Pickle's coat is green)"
    from app import clip_prompts

    bd = clip_prompts.newest(db, project)  # a scene 2 shot in clip 1: named by its clip
    bd.data = {
        **bd.data,
        "clips": [{**bd.data["clips"][0], "shot_ids": [*bd.data["clips"][0]["shot_ids"], "2.1"]}],
    }
    turns[-1].input = {**turns[-1].input, director.RUN: {**run, "redraws": {"2.1": 1}}}
    review.output = {"ready": False, "findings": [  # the review prompt's own shape, worst first
        {"shot_id": "2.1", "problem": "2.1 shows him sitting; the beat is the jar exploding"},
        {"shot_id": "2.1", "problem": "The jar is empty; it should be full"}]}  # fmt: skip
    db.commit()
    said = _step(owner, pid, "stills")["text"]  # one reason, the shot's clip, no shot number
    assert said == "Stills: 1 drawn, 1 redrawn (clip 1's still shows him sitting)"


def test_clip_prompts_say_each_model_with_how_many_and_why(app, db, owner, editor, monkeypatch):
    pid = _done(app, db, owner, editor)
    step = _step(owner, pid, "prompts")
    assert step["text"] == "Clip prompts written · on Seedance 2.5"
    assert step["sub"] == "Seedance 2.5: House's default for its clips"  # shown once done too
    first = db.query(ProjectClip).filter_by(project_id=pid).one()
    for n in (2, 3):  # two clips of their own on Seedance 1 Lite, chosen by the director
        db.add(ProjectClip(project_id=pid, breakdown_id=first.breakdown_id, clip_id=f"c{n}",
                           seconds=4, prompt="More.", model={"id": "seedance-1-lite",
                                                             "why": "A hand: Lite is enough.",
                                                             "by": "director"}))  # fmt: skip
    db.commit()
    step = _step(owner, pid, "prompts")
    assert step["text"] == "Clip prompts written · on Seedance 2.5 (1), Seedance 1 Lite (2)"
    assert step["sub"] == ("Seedance 2.5: House's default for its clips; "
                           "Seedance 1 Lite: A hand: Lite is enough")  # fmt: skip


def test_a_presenters_video_lays_the_presenter_over_the_b_roll(app, db, owner, editor,
                                                              monkeypatch):  # fmt: skip
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    monkeypatch.setattr(host, "on", lambda db, p: True)
    step = _step(owner, pid, "prompts")
    assert step["text"] == "Clip prompts written · B-roll on Seedance 2.5, presenter on HeyGen"
    assert step["sub"].endswith("; HeyGen lip-syncs the presenter to the voice")
    assert _step(owner, pid, "host")["text"] == "Lay Mom and Nate over the B-roll"
    face = LibraryItem(workspace_id=project.workspace_id, kind=Kind.character, name="Dr. Pickle")
    db.add(face)
    db.commit()
    monkeypatch.setattr(host, "presents", lambda db, p: True)
    monkeypatch.setattr(host, "host_look", lambda db, p: db.get(LibraryItem, face.id))
    assert _step(owner, pid, "host")["text"] == "Lay Dr. Pickle over the B-roll"  # just them
    job = db.query(Job).filter_by(project_id=pid).first()
    take = SongTake(
        draft_id=project.script_draft_id,
        project_id=pid,
        number=1,
        kind="narration",
        job_id=job.id,
        lyrics="",
        style_line="",
        file_id=upload(owner),
        music_file_id=upload(owner),
    )  # its narration came with its music bed
    db.add(take)
    db.flush()
    project.song_take_id = take.id
    db.commit()
    said = _step(owner, pid, "host")["text"]
    assert said == "Lay Dr. Pickle over the B-roll, music under the voice"
    assert _step(owner, pid, "cut")["text"] == "Watch and listen to the whole cut, then deliver"
