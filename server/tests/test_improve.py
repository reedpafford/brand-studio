"""Quick clip Improve prompt with a mocked Claude (no paid calls)."""

import json

import httpx2 as httpx

from app.models.jobs import Job
from app.providers.replicate import ReplicateProvider
from app.worker import run_once
from tests.helpers import assert_hidden, assert_no_dollars
from tests.test_clips import _clip, fomo  # noqa: F401 - fixture
from tests.test_enhance import FakeClaude, _run
from tests.test_replicate import BASE, FakeReplicate

IDEA = 'Max starts trading at sunrise. Max: "Let\'s go!"'
AUDIO = (
    "Audio: only the spoken lines and a quiet morning room. No music, background music, BGM, "
    "score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. "
    "No subtitles."
)
REFS = '[Image1] is Max. [Image2] is the fomo "Buy" screen, shown exactly.'


def _improved(line: str = "Let's go!") -> dict:
    prompt = "\n".join(
        [
            AUDIO,
            f"References: {REFS}",
            "Summary: Max starts trading at sunrise.",
            "Style: stylized 3D animated feature film, expressive faces, cinematic.",
            "Setting: warm sunrise through a window.",
            "Shots (hard cuts):",
            f'Shot 1 | 0–2 s. Close-up, push in. Max grins at his phone. Max (excited): "{line}"',
            "Shot 2 | 2–5 s. Close-up on the phone, static. It shows [Image2] exactly.",
            "Keep: Max as in [Image1], one of him; the screen exactly as [Image2].",
            AUDIO,
        ]
    )
    return {"prompt": prompt}


def _ask(editor, fomo, **extra):  # noqa: F811
    body = _clip(fomo, prompt=IDEA, character_ids=[fomo["character"]], **{"shots": 2, **extra})
    return editor.post("/clips/improve", json=body)


def test_improve_then_generate_as_is(app, db, editor, fomo):  # noqa: F811
    job = _ask(editor, fomo, direction="Cinematic")
    assert job.status_code == 201, job.text
    assert job.json()["credits"] == 3 and job.json()["step"] == "improve"
    again = _ask(editor, fomo, direction="Cinematic")  # a double press makes no second call
    assert again.status_code == 409 and "already being improved" in again.json()["detail"]
    fake = FakeClaude(_improved())
    _run(app, db, fake)
    sent = fake.requests[0]["messages"][0]["content"]
    assert "<brief>direction: Cinematic; shots: 2; seconds: 5</brief>" in sent
    assert f"<references>{REFS}</references>" in sent
    assert f"<idea>{IDEA}</idea>" in sent

    result = editor.get(f"/clips/improve/{job.json()['id']}").json()
    assert result["status"] == "succeeded" and result["problems"] == []
    body = _clip(fomo, prompt=result["prompt"], character_ids=[fomo["character"]], improved=True)
    clip = editor.post("/clips", json=body)
    assert clip.status_code == 201, clip.text
    replicate = FakeReplicate()
    client = httpx.Client(transport=httpx.MockTransport(replicate))
    run_once(db, {"replicate": ReplicateProvider(BASE, client)}, app.state.storage)
    posted = next(q for q in replicate.requests if q.method == "POST")
    assert json.loads(posted.content)["input"]["prompt"] == result["prompt"]  # not doubled
    assert db.get(Job, clip.json()["id"]).input["request"]["improved"] is True

    changed = _clip(fomo, prompt=result["prompt"], improved=True)  # Max removed since
    r = editor.post("/clips", json=changed)
    assert r.status_code == 422 and "changed since Improve" in r.json()["detail"]


def test_problems_are_shown(app, db, editor, fomo):  # noqa: F811
    job = _ask(editor, fomo, shots=3)
    _run(app, db, FakeClaude(_improved(line="Let us go!")))
    problems = editor.get(f"/clips/improve/{job.json()['id']}").json()["problems"]
    assert "the line “Let's go!” isn't there once, word for word" in problems
    assert "2 shots, the brief asks for 3" in problems


def test_improve_switch_workspace_and_dollars(app, editor, outsider, fomo):  # noqa: F811
    job = _ask(editor, fomo).json()["id"]
    assert_hidden(outsider, [("GET", f"/clips/improve/{job}")])
    assert_no_dollars(editor, [f"/clips/improve/{job}"])
    assert editor.get("/clips/improve/999").status_code == 404
    app.state.settings.generation_enabled = False
    try:
        assert _ask(editor, fomo).status_code == 503
    finally:
        app.state.settings.generation_enabled = True
