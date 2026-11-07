"""Movie (Reed, 7 Nov: "Movie, up to 30 s: make it work on the site"): a photoreal short drama
in the Dialogue format, every clip on Omni 1.2 (#1394) in Omni's own voices, with no voice
track or music bed of our own. On the stand-ins: no paid call."""

from app import guides, model_map, prompts
from app.breakdown import video_model
from app.catalogue import get_model
from app.models.clips import ProjectClip
from app.models.jobs import Job
from app.models.projects import Project
from tests.test_director import _run
from tests.test_script_library import _make

# About 30 s: two scenes, eight lines, two people talking to each other.
DRAMA = """SCENE 1 — INT. DINER — NIGHT
NATE: They laughed at me. The whole table.
MOM: Then give them something else to look at.
NATE: Like what? I've tried everything.
MOM: You haven't tried this.
SCENE 2 — EXT. DINER PARKING LOT — DAWN
NATE: Thirty days. Same booth, same table.
MOM: And nobody's laughing now.
NATE: No. Now they're asking what I did."""


def _movie(app, owner, editor) -> int:
    app.state.settings.fake_providers = True
    made = _make(owner, text=DRAMA, look="movie")
    base = f"/scripts/{made['id']}"
    owner.post(f"{base}/drafts/0/approve")
    owner.post(f"{base}/publish")
    return editor.post(f"{base}/drafts/0/produce").json()["project_id"]


def test_movie_is_a_style_people_can_pick_made_on_omni_in_the_dialogue_format(editor):
    movie = guides.style("movie")
    assert (movie["name"], movie["on"], movie["video_model"]) == ("Movie", True, model_map.OMNI)
    assert guides.video_format("story", "movie") == "dialogue"  # the story engine carries it
    for kind in ("story", "narrated", None):
        assert video_model(look="movie", kind=kind).id == model_map.OMNI, kind
    shown = {x["id"]: x for x in editor.get("/looks").json()}
    assert shown["movie"]["on"] and shown["movie"]["video_model"] == model_map.OMNI
    sound = movie["sections"]["Sound and delivery"]
    assert "No score under dialogue. Music is added in post" in sound  # never asks for a bed
    assert "add nothing to them" in movie["sections"]["The videos"]  # the script's own ending
    assert "added in the edit" in movie["sections"]["Stills"]  # rule 32: overlays only
    brief = prompts.system("clip_prompts", "movie")
    assert "## Style: Movie\n" in brief and "Omni's own, made from the quoted lines" in brief


def test_a_movie_goes_from_its_script_to_a_cut_with_every_clip_on_omni(app, db, owner, editor):
    """Brief → Script → Breakdown → Storyboard → Clips → Cut, by the director on the stand-ins:
    each take on Omni 1.2 (spoken lines too: never moved to a Seedance that lip-syncs), 9:16,
    3–15 s, the sheets and the still as reference pictures, its sound Omni's own with no music;
    no voice track, narration or music bed is made beside it."""
    pid = _movie(app, owner, editor)
    project = db.get(Project, pid)
    assert (project.look, project.aspect_ratio) == ("movie", "9:16")
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    out = editor.get(f"/projects/{pid}/director").json()
    assert out["status"] == "delivered", out["ended"]
    assert editor.get(f"/projects/{pid}/video").json()["file_id"]  # the cut
    jobs = db.query(Job).filter_by(project_id=pid).all()
    steps = {j.input.get("step") for j in jobs}
    assert {"breakdown", "storyboard", "frame", "clip_prompts", "clip_take", "cut_make"} <= steps
    kinds = {"write-claude", "check-claude", "image", "video", "cut_make", "cut_listen"}
    assert {j.kind for j in jobs} <= kinds, {j.kind for j in jobs}  # no voice, narration, music
    takes = [j for j in jobs if j.kind == "video"]
    omni = get_model(model_map.OMNI)
    for take in takes:
        sent = take.input["input"]
        assert take.input["model"] == model_map.OMNI
        assert sent["aspect_ratio"] == "9:16"
        assert omni.duration.min <= sent["duration"] <= omni.duration.max
        assert len(take.input["files"]["reference_images"]) >= 2  # the still and the sheets
        assert sent["prompt"].rstrip().endswith("No music.") and '"' in sent["prompt"]
    for row in db.query(ProjectClip).filter_by(project_id=pid):
        assert model_map.lip_synced(project, row) is None  # spoken, and still on Omni
    shown = owner.get(f"/projects/{pid}/clips").json()
    assert shown and {c["model"]["id"] for c in shown} == {model_map.OMNI}
    assert shown[0]["model"]["why"] == "Movie's default for its clips."


def test_the_director_keeps_every_movie_clip_on_omni(app, db, owner, editor):
    pid = _movie(app, owner, editor)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    project = db.get(Project, pid)
    row = db.query(ProjectClip).filter_by(project_id=pid).first()
    refused = model_map.ALL_OMNI.format(style="Movie")
    for other in ("seedance-2.5", "seedance-2.0"):
        assert model_map.choose(db, project, row, other, "lip-sync") == refused
        assert model_map.off_map(project, other).startswith("Refused: Movie's videos are made on")
    assert model_map.off_map(project, model_map.OMNI) == ""
    assert model_map.choose(db, project, row, model_map.OMNI, "an insert").startswith(
        f"Clip {row.clip_id.removeprefix('c')} is made on Gemini Omni 1.2 now"
    )
