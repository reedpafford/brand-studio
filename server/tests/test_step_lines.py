"""S3-04's step lines, as drawn: the cast with its voice and whether it's the brand's saved
cast, the stills redrawn and why, and the clip prompts' models with why each. All on the
stand-ins (no paid call)."""

from app import director, host
from app.cast_roles import pick, video_slots
from app.models.brands import Brand
from app.models.jobs import Job, JobStatus
from app.models.library import Kind, LibraryItem
from app.models.projects import Project
from app.models.voices import Voice
from tests.test_run_progress import _done, _progress


def _step(client, pid: int, key: str) -> dict:
    return next(s for s in _progress(client, pid)["steps"] if s["key"] == key)


def test_the_cast_line_says_its_voice_and_whether_it_is_the_brands_saved_cast(
    app, db, owner, editor, monkeypatch
):
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    assert _step(owner, pid, "cast")["text"] == "Cast: Mom and Nate, made for this video"
    brand = db.get(Brand, project.brand_id)
    for slot in video_slots(db, project):
        item = db.get(LibraryItem, pick(db, project, slot))
        item.owner_project_id, item.brands = None, [brand]  # saved in the brand on purpose
    db.commit()
    assert _step(owner, pid, "cast")["text"] == f"Cast: Mom and Nate, both saved in {brand.name}"
    face = LibraryItem(workspace_id=project.workspace_id, kind=Kind.character, name="Dr. Pickle",
                       brands=[brand])  # fmt: skip
    clone = Voice(workspace_id=project.workspace_id, brand_id=brand.id, name="Dr. Pickle",
                  kind="cloned", provider="minimax")  # fmt: skip
    db.add_all([face, clone])
    db.commit()
    project.voice = f"voice:{clone.id}"
    db.commit()
    monkeypatch.setattr(host, "presents", lambda db, p: True)
    monkeypatch.setattr(host, "host_look", lambda db, p: db.get(LibraryItem, face.id))
    said = _step(owner, pid, "cast")["text"]
    assert said == f"Cast: Dr. Pickle, Mom, Nate and the cloned voice, all saved in {brand.name}"
    project.voice = "stock:Roger"  # an app voice: never the brand's to save
    db.commit()
    said = _step(owner, pid, "cast")["text"]
    assert (
        said
        == f"Cast: Dr. Pickle, Mom and Nate, all saved in {brand.name}; read in the Roger voice"
    )


def test_stills_say_how_many_were_redrawn_and_why(app, db, owner, editor):
    pid = _done(app, db, owner, editor)
    project = db.get(Project, pid)
    turns = director.turns(db, project)
    run = turns[-1].input[director.RUN]
    turns[-1].input = {**turns[-1].input, director.RUN: {**run, "redraws": {"1.1": 2}}}
    db.add(Job(workspace_id=project.workspace_id, kind="check-claude", provider="fake",
               project_id=pid, credits=0, status=JobStatus.succeeded,
               input={"step": "review_stills"},
               output={"ready": False, "findings": [
                   {"shot_id": "1.1", "problem": "The capsule label faced away.", "note": "n"},
                   {"shot_id": "9.9", "problem": "Not redrawn.", "note": "n"}]}))  # fmt: skip
    db.commit()
    said = _step(owner, pid, "stills")["text"]
    assert said == "Stills: 1 drawn, 2 redrawn (the capsule label faced away)"


def test_clip_prompts_say_each_model_and_why_and_the_presenters(app, db, owner, editor,
                                                               monkeypatch):  # fmt: skip
    pid = _done(app, db, owner, editor)
    step = _step(owner, pid, "prompts")
    assert step["text"] == "Clip prompts written · on Seedance 2.5"
    assert step["sub"] == "Seedance 2.5: House's default for its clips"  # shown once done too
    monkeypatch.setattr(host, "on", lambda db, p: True)
    step = _step(owner, pid, "prompts")
    assert step["text"] == "Clip prompts written · B-roll on Seedance 2.5, presenter on HeyGen"
    assert step["sub"].endswith("; HeyGen lip-syncs the presenter to the voice")
    assert _step(owner, pid, "host")["text"].startswith("Lay Mom and Nate over the B-roll")
    assert _step(owner, pid, "cut")["text"] == "Watch and listen to the whole cut, then deliver"
