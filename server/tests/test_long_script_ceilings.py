"""A 1,000-word, 5-minute script (Reed's Palace Guard UGC ads, 10 Nov) goes through every step
on the stand-ins: each Claude call has room for its answer, within the model's own limit, and
the director's turns and watches grow with the video's clips."""

import json
import re

import pytest

from app import claude, director, still_review, watch_cut
from app.models.accounts import User
from app.models.asks import Ask
from app.models.clips import ClipTake, ProjectClip
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import _run

SENTENCES = [
    "I almost lost ten thousand dollars because I trusted the wrong guard.",
    "Every night I locked the door and thought my family was safe.",
    "Then the camera showed me what happened at three in the morning.",
    "A stranger walked right up to the porch and tried the handle.",
    "The old guard never made a sound and the light never came on.",
    "So I tested the new one the same way, with my own hand on the door.",
    "It lit the porch, called my phone, and spoke before I touched the lock.",
]
CHARS_A_TOKEN = 3  # JSON answers run about 3-4 characters a token: the low end, to be safe
ROOM_TO_SPARE = 3  # every call's room is at least 3x its stand-in answer (real ones run longer)
PROMPT_CHARS = 300_000  # about 100k tokens at most: well under the 1M context window


def _script(words: int) -> str:
    out, n = [], 0
    while sum(len(x.split()) for x in out) < words:
        out.append(f"MARCUS: {SENTENCES[n % len(SENTENCES)]} Part {n + 1}.")
        n += 1
    return "\n".join(out)


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def test_turns_and_watches_grow_with_the_clips_up_to_a_ceiling():
    assert director.most_turns(0) == director.most_turns(20) == director.MAX_TURNS == 40
    assert director.most_turns(47) == 94  # 2 a clip on a long video
    assert director.most_turns(500) == director.MOST_TURNS == 200
    assert director.most_watches(0) == director.most_watches(19) == director.MAX_WATCHES == 3
    assert director.most_watches(47) == 5  # one more for every 20 clips
    assert director.most_watches(500) == director.MOST_WATCHES == 6


def test_a_thousand_word_script_goes_through_every_step(app, db, owner):
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": _script(1000),
            "brand_id": first_brand(owner)}  # fmt: skip
    r = owner.post("/freestyles", json=body)
    assert r.status_code == 201, r.text
    fs = db.get(Freestyle, r.json()["id"])
    video = db.get(Project, fs.project_id, execution_options={"see_hidden": True})
    assert director.planned_clips(db, video) == 0  # no breakdown yet: the base caps
    _run(app, db, ticks=300)
    jobs = db.query(Job).filter(Job.project_id == video.id).order_by(Job.id).all()

    assert not [(j.id, j.input.get("step"), j.error) for j in jobs if j.status == "failed"]
    assert ("start", "answered") in {(a.kind, a.state) for a in db.query(Ask).filter_by(
        project_id=video.id)}  # its start card, pressed  # fmt: skip
    clips = director.planned_clips(db, video)
    takes = db.query(ClipTake).join(ProjectClip, ClipTake.clip_id == ProjectClip.id).filter(
        ProjectClip.project_id == video.id).count()  # fmt: skip
    assert clips >= 40 and takes >= 40, (clips, takes)
    cut = next(j.id for j in jobs if j.kind == "cut_make" and j.status == "succeeded")

    for j in jobs:  # every Claude call: room for its answer, never past the model's limit
        if j.provider != "claude" or j.status != "succeeded":
            continue
        room = j.input.get("max_tokens", claude.ROOM)
        answer = len(json.dumps(j.output)) / len(j.input.get("parts") or [""])  # one call's
        assert ROOM_TO_SPARE * answer / CHARS_A_TOKEN <= room <= claude.MOST_TOKENS, (
            j.input.get("step"), room, answer)  # fmt: skip

    turns = [j for j in jobs if j.input.get("step") == director.STEP and j.kind == "write-claude"]
    first = [t.input["prompt"] for t in turns if t.id < cut]
    left = [int(re.search(r'"turns_left": (-?\d+)', p)[1]) for p in first]
    # 30-odd turns to its first cut (the old cap was 40): plenty left to watch it and fix it
    assert min(left) >= director.MAX_TURNS // 2, left
    watches = int(re.search(r'"watches_left": (\d+)', first[-1])[1])
    assert watches == director.most_watches(clips) > director.MAX_WATCHES
    longest = max(len(t.input["prompt"]) + sum(map(len, t.input["system"])) for t in turns)
    assert longest < PROMPT_CHARS, longest
    assert not any("It stopped after" in str(j.input.get("result")) for j in turns)
    listen = next(j for j in jobs if j.kind == "cut_listen")  # its watch: about 3 frames a clip
    overview = [x for x in listen.output["strips"] if "over the whole" in x["what"]]
    assert len(overview) * 8 >= watch_cut.PER_CLIP * clips - 8  # 8 upright frames a strip


SUNG = ["Wake up hungry", "Bowl is bright", "Iron Paws tonight", "Tail so high",
        "Gut so happy", "My best ally", "Crunch and run", "Here comes the sun"]  # fmt: skip
MOST_PICTURES = 600  # a request's pictures on a 1M-token model (Anthropic's vision docs)


def test_a_full_length_song_has_room_for_its_shots_and_stills(app, db, owner, monkeypatch):
    """Reed's full-length Pixar songs (about 1,000 words, 5.5 minutes) at song density, a shot
    a sung line, 160 of them, reach the stills and the clip prompts on the stand-ins; the
    shots and storyboard calls have the model's whole room (Reed, 10 Nov: the stopgap), and
    a stills review of 150-odd stills stays well under Anthropic's 600 pictures a request."""
    monkeypatch.setattr(app.state.settings, "kie_suno", True)
    long = f"{director.STAND_IN_STYLE} fake:long=400"  # a word a beat: 800 words, 6.5 minutes
    monkeypatch.setattr(director, "STAND_IN_STYLE", long)
    lyrics = "\n".join(f"{SUNG[n % len(SUNG)]}, bar {n + 1}" for n in range(160))
    body = {"type": "song", "look": "house", "shape": "9:16", "text": lyrics,
            "brand_id": first_brand(owner)}  # fmt: skip
    r = owner.post("/freestyles", json=body)
    assert r.status_code == 201, r.text
    video = db.get(Project, db.get(Freestyle, r.json()["id"]).project_id,
                   execution_options={"see_hidden": True})  # fmt: skip
    _run(app, db, ticks=300)
    jobs = db.query(Job).filter(Job.project_id == video.id).order_by(Job.id).all()

    assert not [(j.id, j.input.get("step"), j.error) for j in jobs if j.status == "failed"]
    done = {j.input.get("step") for j in jobs if j.status == "succeeded"}
    assert {"song_breakdown", "storyboard", "clip_prompts"} <= done, done
    (shots_job,) = [j for j in jobs if j.input.get("step") == "song_breakdown"]
    shots = sum(len(sc["shots"]) for sc in shots_job.output["scenes"])
    assert shots >= 150, shots
    for step in ("song_breakdown", "storyboard"):  # the model's most, never past it
        rooms = {j.input["max_tokens"] for j in jobs if j.input.get("step") == step}
        assert rooms == {claude.MOST_TOKENS}, (step, rooms)
    assert [j for j in jobs if j.input.get("step") == still_review.STEP]

    drawn = still_review.frames(db, video)  # one still a shot: the stills review's pictures
    monkeypatch.setattr(still_review, "frames", lambda db, project: drawn * (shots // len(drawn)))
    still_review.start(db, db.get(User, video.created_by_id), video, None)
    review = db.query(Job).filter(Job.project_id == video.id).order_by(Job.id.desc()).first()
    seen = len(review.input["files"]["reference_images"])
    assert review.input["step"] == still_review.STEP and 150 <= seen <= MOST_PICTURES
