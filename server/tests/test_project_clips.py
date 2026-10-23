"""Project clip prompts with a mocked Claude (no paid calls)."""

import copy

from app.models.jobs import Job
from tests.conftest import upload
from tests.helpers import assert_hidden, assert_no_dollars
from tests.test_breakdown import BREAKDOWN
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture

AUDIO = (
    "Audio: only the spoken lines and a quiet kitchen hum. No music, background music, BGM, "
    "score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. "
    "No subtitles."
)


def _prompt(screen_n: int = 2) -> str:
    return "\n".join(
        [
            AUDIO,
            'References: [Image1] is Mom. [Image2] is the fomo "Buy" screen.',
            "Summary: Mom finds the empty wallet in the kitchen; Nate is proud he bought the dip.",
            "Style: stylized 3D animated feature film, expressive faces.",
            "Setting: cold morning light.",
            "Shots (hard cuts):",
            'Shot 1 | 0–2 s. Close-up, push in. Mom (sharp): "Nate, where is all your money?"',
            f'Shot 2 | 2–5 s. Close-up. Nate (proud): "I bought the dip." Shows [Image{screen_n}].',
            f"Keep: Mom as in [Image1], one of her; the screen exactly as [Image{screen_n}].",
            AUDIO,
        ]
    )


def _answer(mom: int, screen: int, prompt: str) -> dict:
    refs = [
        {"kind": "image", "id": f"char:{mom}", "role": "Mom"},
        {"kind": "image", "id": f"screen:{screen}", "role": "fomo Buy screen"},
    ]
    return {"clips": [{"clip_id": "c1", "seconds": 5, "references": refs, "prompt": prompt}]}


def test_clip_prompts_written_checked_and_edited(app, db, editor, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/clips"
    assert editor.post(f"{url}/prompts").status_code == 409  # needs a breakdown
    voice = upload(editor, "v.mp3", b"ID3" + b"0" * 32, "audio/mpeg")
    mom = editor.post(
        "/library/character",
        json={"name": "Mom", "image_file_ids": [upload(editor)], "voice_file_id": voice},
    ).json()["id"]
    editor.patch(f"/projects/{setup['project']}", json={"cast_ids": [mom]})
    bd = copy.deepcopy(BREAKDOWN)
    bd["scenes"][0]["shots"][0]["character_ids"] = [f"char:{mom}"]
    editor.post(f"/projects/{setup['project']}/breakdown")
    _run(app, db, FakeClaude(bd))

    job = editor.post(f"{url}/prompts")
    assert job.status_code == 201
    assert editor.post(f"{url}/prompts").status_code == 409  # one at a time
    fake = FakeClaude(_answer(mom, setup["screen"], _prompt()))
    _run(app, db, fake)
    assert db.get(Job, job.json()["id"]).status == "succeeded"
    message = fake.requests[0]["messages"][0]["content"]
    assert "<video_model>Seedance 2.5" in message and f"voice:{mom} | voice sample | Mom" in message

    clips = editor.get(url).json()
    assert [(c["clip_id"], c["seconds"], c["problems"], c["stale"]) for c in clips] == [
        ("c1", 5, [], False)
    ]
    edit = _answer(mom, setup["screen"], _prompt(screen_n=7))["clips"][0]
    edit["references"].append({"kind": "image", "id": f"voice:{mom}", "role": "wrong kind"})
    edited = editor.put(f"{url}/{clips[0]['id']}", json=edit).json()
    assert "c1: prompt names an image that isn't attached" in edited["problems"]
    assert f"c1: voice:{mom} is not a image" in edited["problems"]


def test_clip_prompts_switch_workspace_and_dollars(app, db, editor, outsider, setup):  # noqa: F811
    url = f"/projects/{setup['project']}/clips"
    assert_hidden(outsider, [("POST", f"{url}/prompts"), ("GET", url)])
    editor.post(f"/projects/{setup['project']}/breakdown")
    _run(app, db, FakeClaude(BREAKDOWN))
    app.state.settings.generation_enabled = False
    try:
        assert editor.post(f"{url}/prompts").status_code == 503
    finally:
        app.state.settings.generation_enabled = True
    body = {"prompt": "x", "references": []}
    assert editor.put(f"{url}/999", json=body).status_code == 404
    assert_no_dollars(editor, [url])
