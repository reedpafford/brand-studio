"""Movie (Reed, 7 Nov: "Movie, up to 30 s: make it work on the site"): a photoreal short drama
in the Dialogue format, every clip on the model its guide names (`video_model:`, the one place
it is set) in that model's own voices, with no voice track or music bed of our own. On the
stand-ins: no paid call."""

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


def _own() -> str:
    """Movie's video model: its guide's, whichever it names."""
    return guides.style("movie")["video_model"]


def test_movie_is_a_style_people_can_pick_made_on_its_guides_model_in_the_dialogue_format(editor):
    movie = guides.style("movie")
    assert (movie["name"], movie["on"]) == ("Movie", True)
    assert guides.video_format("story", "movie") == "dialogue"  # the story engine carries it
    for kind in ("story", "narrated", None):
        assert video_model(look="movie", kind=kind).id == _own(), kind
    shown = {x["id"]: x for x in editor.get("/looks").json()}
    assert shown["movie"]["on"] and shown["movie"]["video_model"] == _own()
    sound = movie["sections"]["Sound and delivery"]
    assert "No score under dialogue. Music is added in post" in sound  # never asks for a bed
    assert "add nothing to them" in movie["sections"]["The videos"]  # the script's own ending
    assert "added in the edit" in movie["sections"]["Stills"]  # rule 32: overlays only
    brief = prompts.system("clip_prompts", "movie")
    assert "## Style: Movie\n" in brief and "made from the quoted lines" in brief


def test_a_movie_goes_from_its_script_to_a_cut_with_every_clip_on_its_model(app, db, owner, editor):
    """Brief → Script → Breakdown → Storyboard → Clips → Cut, by the director on the stand-ins:
    each take on Movie's own model (spoken lines too: never moved to another that lip-syncs),
    9:16, within its lengths, the sheets as reference pictures, its lines in quotes for the
    model's own voices; no voice track, narration or music bed is made beside it."""
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
    kinds = {
        "write-claude",
        "check-claude",
        "image",
        "video",
        "cut_make",
        "cut_listen",
        "director_step",
    }  # the server's own steps (director_auto)
    assert {j.kind for j in jobs} <= kinds, {j.kind for j in jobs}  # no voice, narration, music
    takes = [j for j in jobs if j.kind == "video"]
    own = get_model(_own())
    for take in takes:
        sent = take.input["input"]
        assert take.input["model"] == own.id
        assert sent["aspect_ratio"] == "9:16"
        assert own.duration.min <= sent["duration"] <= own.duration.max
        assert len(take.input["files"]["reference_images"]) >= 2  # the sheets (and the still)
        assert '"' in sent["prompt"]
    for row in db.query(ProjectClip).filter_by(project_id=pid):
        assert model_map.lip_synced(project, row) is None  # spoken, and still on its model
    shown = owner.get(f"/projects/{pid}/clips").json()
    assert shown and {c["model"]["id"] for c in shown} == {own.id}
    assert shown[0]["model"]["why"] == "Movie's default for its clips."


def test_the_director_keeps_every_movie_clip_on_its_guides_model(app, db, owner, editor):
    pid = _movie(app, owner, editor)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    project = db.get(Project, pid)
    row = db.query(ProjectClip).filter_by(project_id=pid).first()
    own = get_model(_own())
    refused = model_map.ONE_MODEL.format(style="Movie", model=own.name)
    whole = model_map.WHOLE.format(style="Movie", model=own.name)
    for other in ("seedance-2.5", "seedance-2.0"):
        assert model_map.choose(db, project, row, other, "lip-sync") == refused
        assert model_map.off_map(project, other) == whole
    assert model_map.off_map(project, own.id) == ""
    assert model_map.choose(db, project, row, own.id, "an insert").startswith(
        f"Clip {row.clip_id.removeprefix('c')} is made on {own.name} now"
    )


def test_a_persons_note_can_put_one_movie_clip_on_seedance(app, db, owner, editor):
    """QA on #1440: "make the 3D insert on Seedance" in a person's note could never be done,
    as every clip was refused. A move that answers a note ("Note 1: …", as settings uses)
    puts that one clip on Seedance; without one, it stays on Movie's own model."""
    pid = _movie(app, owner, editor)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    project = db.get(Project, pid)
    row = db.query(ProjectClip).filter_by(project_id=pid).first()
    assert model_map.choose(db, project, row, "seedance-2.5", "b3: a 3D insert.") == (
        model_map.ONE_MODEL.format(style="Movie", model=get_model(_own()).name))  # fmt: skip
    said = model_map.choose(db, project, row, "seedance-2.5", "Note 1: the 3D insert on Seedance.")
    assert said.startswith(f"Clip {row.clip_id.removeprefix('c')} is made on Seedance 2.5 now")


def test_movie_is_made_only_as_dialogue_with_its_reason(app, db, owner, editor):
    """QA on #1440: Movie as Narrated made a MiniMax narration and as Presenter a HeyGen host,
    against its "no voice track of ours". It's offered and made only as Dialogue."""
    from app import looks

    movie = next(x for x in editor.get("/looks").json() if x["id"] == "movie")
    assert movie["formats"] == ["dialogue"] and "voice track of ours" in movie["formats_why"]
    said = looks.format_refusal("movie", "presenter")
    assert said.startswith("Movie is made only as Dialogue: its people say the script's lines")
    assert looks.format_refusal("movie", "dialogue") == "" == looks.format_refusal("house", "song")
    brand = owner.get("/brands").json()[0]["id"]
    for kind in ("presenter", "narrated"):
        made = owner.post("/freestyles", json={"type": kind, "look": "movie", "shape": "9:16",
                                               "brand_id": brand, "text": "NATE: Hi."})  # fmt: skip
        assert (made.status_code, made.json()["detail"]) == (409, said), kind
    pid = _movie(app, owner, editor)
    video = db.get(Project, pid)
    video.look = "house"
    db.commit()
    from app import narration

    script = narration.video_script(db, video)
    script.kind = "narrated"  # a narrated video: switching it to Movie is refused
    db.commit()
    moved = owner.post(f"/projects/{pid}/settings", json={"look": "movie"})
    assert moved.status_code == 409 and moved.json()["detail"].startswith("Movie is made only as")


def test_a_script_is_never_movie_in_a_format_movie_isnt_made_in(owner):
    """QA on #1440: a narrated Movie script was published (its narration paid for) and then
    never made. Writing or changing one is refused in Make's words; Dialogue stays free."""
    from app import looks

    said = looks.format_refusal("movie", "narrated")
    brand = owner.get("/brands").json()[0]["id"]
    for body in ({"format": "narrated"}, {"kind": "narrated"}, {"format": "presenter"}):
        made = owner.post("/scripts", json={"brand_id": brand, "title": "T", "look": "movie",
                                            **body})  # fmt: skip
        assert made.status_code == 409 and made.json()["detail"].startswith(said[:30]), body
    rows = owner.post("/scripts/bulk", json={"scripts": [
        {"brand_id": brand, "title": "T", "look": "movie", "format": "narrated"}]})  # fmt: skip
    assert (rows.status_code, rows.json()["detail"]) == (409, f"Row 1: {said}")
    movie = _make(owner, text=DRAMA, look="movie")["id"]
    moved = owner.patch(f"/scripts/{movie}", json={"format": "narrated"})
    assert (moved.status_code, moved.json()["detail"]) == (409, said)
    told = _make(owner, text=DRAMA, format="narrated")["id"]
    moved = owner.patch(f"/scripts/{told}", json={"look": "movie"})
    assert (moved.status_code, moved.json()["detail"]) == (409, said)
    assert owner.patch(f"/scripts/{told}", json={"look": "movie", "format": "dialogue"}).is_success
    assert owner.get(f"/scripts/{told}").json()["look"] == "movie"


def test_an_omni_take_in_a_shape_omni_doesnt_make_is_made_nearest_and_cropped_in_the_cut():
    """QA on #1440: Omni 1.2 makes only 9:16 and 16:9, so a 1:1 Movie or UGC video's takes
    failed at the provider. Its takes are made at the nearest shape Omni has (9:16 on a tie)
    and the cut crops each to the video's shape around its centre."""
    import subprocess

    from app import cut_render

    omni = get_model(model_map.OMNI)
    assert [model_map.nearest(s, omni.aspect_ratios) for s in ("9:16", "16:9", "1:1", "4:3")] == [
        "9:16", "16:9", "9:16", "16:9"]  # fmt: skip
    taken, _ = model_map.fit(omni, {"prompt": "Audio: only room tone.\nShot 1 | 0-4 s. A.",
                                    "duration": 4, "aspect_ratio": "1:1"}, {})  # fmt: skip
    assert taken["aspect_ratio"] == "9:16"  # with a line keeping faces in the crop, only then
    assert "keep the action and faces inside the centre square." in taken["prompt"]
    own, _ = model_map.fit(omni, {"prompt": "Shot 1 | 0-4 s. A.", "duration": 4,
                                  "aspect_ratio": "9:16"}, {})  # fmt: skip
    assert "Framing" not in own["prompt"]
    tall = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",  # noqa: S603, S607
                           "color=c=red:s=270x480:d=1", "-f", "lavfi", "-i",
                           "anullsrc=r=44100:cl=mono", "-t", "1", "-c:v", "libx264",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags",
                           "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"],
                          capture_output=True, check=True).stdout  # fmt: skip
    square = cut_render.joined([tall, tall], [(0.0, None), (0.0, None)], "1:1")
    probe = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height", "-of", "csv=p=0:s=x", "pipe:0"]  # fmt: skip
    size = subprocess.run(probe, input=square, capture_output=True, check=True)  # noqa: S603
    size = size.stdout.decode().strip()
    assert size == "270x270"
    assert not cut_render._shaped(tall, "1:1") and cut_render._shaped(tall, "9:16")
    assert cut_render._shaped(tall, None)  # a cut that asks no shape: as before


def test_the_cut_crops_only_when_a_take_was_made_in_another_shape(app, db, owner, editor):
    """The crop is for a take Omni made at its nearest shape: a cut whose takes were all asked
    in the video's own shape is joined exactly as before."""
    from app import cut, cut_render

    pid = _movie(app, owner, editor)
    editor.post(f"/projects/{pid}/director")
    _run(app, db)
    project = db.get(Project, pid)
    tl, _ = cut.timeline(db, project)
    assert cut_render.recipe(db, project, tl)["aspect"] is None  # every take asked 9:16
    project.aspect_ratio = "1:1"  # a square Movie: its 9:16 takes are cropped to it
    assert cut_render.recipe(db, project, tl)["aspect"] == "1:1"
    db.rollback()


# A clip as the one-pass plan writes it (the house lines), from Movie Ad 1's lot scene
HOUSE = """Audio: only the spoken lines and an idling engine, a police radio far off, slippers on wet asphalt. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is Paige. [Image2] is Dana. [Image3] is Dr. Reyes. [Image4] is the place, EXT. STORE LOT - NIGHT. [Image5] is the real Palace Guard alarm; show it exactly as it is.
Language: every spoken line is in American English, and any text on screen is in English.
Summary: Paige sits in her parked car with the window down while an officer questions her; her mother Dana runs in and holds her face.
Style: Photoreal TV-drama footage, long lens, shallow focus, the acting small and real.
Setting: Night, red and blue police light from the left on wet asphalt.
Paige's voice: a girl of 18, light and clear, a little dry.
Dana's voice: a woman in her 40s, warm and slightly husky.
Shot 1 | 0-5 s. Close-up through the open driver's window, camera still. Paige's eyes stay on the steering wheel, her fist tight around her keys and the alarm. Only in frame: Paige. Paige (in English, quiet, unsteady): "I tried. Nothing came out."
Shot 2 | 5-7.5 s. Low wide from the car's rear corner, past broken eggs near the lens, camera still. Dana runs in from the left to the driver's door. Only in frame: Dana, Paige. No one speaks.
Shot 3 | 7.5-11 s. Medium close two-shot at the open door, a slow push in. Dana takes Paige's face in both hands. Only in frame: Dana, Paige. Dana (in English, out of breath): "Let me see you."
Shot 4 | 11-14 s. Close-up of Paige, camera still. She looks past Dana at the lot and holds. Only in frame: Paige. Paige (in English, voice-over, lips closed, flat): "They knew my car."
Keep: Paige as in [Image1], the same look as on their sheet. Dana as in [Image2], the same look as on their sheet. Dr. Reyes as in [Image3], the same look as on their sheet.
Audio: only the spoken lines and an idling engine, a police radio far off, slippers on wet asphalt. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles."""  # noqa: E501
SCENE = """Scene context: Paige sits in her parked car with the window down while an officer questions her; her mother Dana runs in and holds her face.
[Image1] is Paige: their face, hair and outfit.
[Image2] is Dana: their face, hair and outfit.
[Image3] is Dr. Reyes: their face, hair and outfit.
[Image4] is the place, EXT. STORE LOT - NIGHT: use it for the place, its light and colour, not for framing.
[Image5] is the real Palace Guard alarm; show it exactly as it is.
Shot 1, 0-5 s: Close-up through the open driver's window, camera still. Paige's eyes stay on the steering wheel, her fist tight around her keys and the alarm. Only in frame: Paige. Paige says, quiet, unsteady: "I tried. Nothing came out."
Shot 2, 5-7.5 s: Low wide from the car's rear corner, past broken eggs near the lens, camera still. Dana runs in from the left to the driver's door. Only in frame: Dana, Paige.
Shot 3, 7.5-11 s: Medium close two-shot at the open door, a slow push in. Dana takes Paige's face in both hands. Only in frame: Dana, Paige. Dana says, out of breath: "Let me see you."
Shot 4, 11-14 s: Close-up of Paige, camera still. She looks past Dana at the lot and holds. Only in frame: Paige. Paige's thought is heard as a voice-over, lips closed, flat: "They knew my car."
Look: Photoreal TV-drama footage, long lens, shallow focus, the acting small and real. Night, red and blue police light from the left on wet asphalt.
Sound: An idling engine, a police radio far off, slippers on wet asphalt. Voices: Paige, a girl of 18, light and clear, a little dry; Dana, a woman in her 40s, warm and slightly husky. No music, no subtitles."""  # noqa: E501


def test_kies_seedance_gets_the_clip_laid_out_as_the_clips_that_held_their_people_were():
    """Reed, 12 Nov: the 25 clips of Movie Ad 1 came out right first time in this shape: the
    scene, a line for each picture saying what to take from it, the timed shots with their
    lines, one look line, one sound line ending on the voices. The repeated audio line, Keep
    and Language go; what is said, and by whom, is unchanged."""
    kie = get_model("seedance-2.5-kie")
    asked = {"prompt": HOUSE, "duration": 14, "aspect_ratio": "9:16", "generate_audio": True}
    sent, files = model_map.fit(kie, asked, {"reference_images": [1, 2, 3, 4, 5]})
    assert sent["prompt"] == SCENE
    assert ({**sent, "prompt": HOUSE}, files) == (asked, {"reference_images": [1, 2, 3, 4, 5]})
    silent = model_map._scene("\n".join(x for x in HOUSE.splitlines() if '"' not in x))
    assert silent.endswith("slippers on wet asphalt. No one speaks. No music, no subtitles.")
    sample = "Photoreal TV-drama footage. [Image1] is the first frame: Mia turns and smiles."
    assert model_map.fit(kie, {"prompt": sample}, {})[0]["prompt"] == sample  # not a house clip
