"""HeyGen Avatar 6 and Avatar 6 Turbo: one still and one voice recording make a talker, from
the Quick clip route the by-hand tools use (Reed, 20 Nov 2026: a cheaper talking head)."""

import base64
import io
import json
import wave

import httpx2 as httpx
import pytest

from app.models.jobs import Job
from app.providers.heygen import HeyGenProvider
from tests.conftest import upload
from tests.test_clips import fomo  # noqa: F401 - the brand fixture

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nstill").decode()
VOICE = base64.b64encode(b"ID3voice").decode()
JOB = {"model": "heygen-avatar-6-turbo", "input": {
    "image": f"data:image/png;base64,{PNG}", "audio": f"data:audio/mpeg;base64,{VOICE}",
    "resolution": "1080p", "motion_prompt": "She talks to the lens.", "duration": 12}}  # fmt: skip


def test_avatar_6_uploads_both_files_and_is_made_and_checked_on_the_model_api():
    seen = []

    def api(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v3/assets":
            return httpx.Response(200, json={"data": {"asset_id": f"a{len(seen)}"}})
        if request.url.path == "/v3/models/avatars":
            return httpx.Response(202, json={"data": {"video_id": "v6", "status": "pending"}})
        assert request.url.path == "/v3/models/videos/v6"
        return httpx.Response(200, json={"data": {
            "status": "completed", "duration": 12.4, "model": "heygen-avatar-6-turbo",
            "video_url": "https://files2.heygen.ai/v6.mp4?Signature=x"}})  # fmt: skip

    heygen = HeyGenProvider("https://api.heygen.com", "test-key",
                            httpx.Client(transport=httpx.MockTransport(api)))  # fmt: skip
    ref = heygen.submit("video", JOB)
    assert ref == "models:v6"
    voice, still, create = seen
    assert b"ID3voice" in voice.content and b"still.png" in still.content
    assert json.loads(create.content) == {
        "model": "heygen-avatar-6-turbo",
        "reference_images": [{"type": "asset_id", "asset_id": "a2"}],
        "audio": {"type": "asset_id", "asset_id": "a1"},
        "resolution": "1080p", "motion_prompt": "She talks to the lens."}  # fmt: skip
    done = heygen.poll(ref)
    assert done.files == ["https://files2.heygen.ai/v6.mp4?Signature=x"]
    assert float(done.usage[0].cost_usd) == pytest.approx(12.4 * 0.05)  # Turbo's published rate


def test_a_quick_clip_on_avatar_6_is_one_still_and_one_voice_priced_by_the_voice(
        owner, fomo, db):  # noqa: F811  # fmt: skip
    wav = io.BytesIO()
    with wave.open(wav, "wb") as w:  # 12.5 s of sound: the clip is priced as 13 s
        w.setparams((1, 2, 8000, 0, "NONE", ""))
        w.writeframes(bytes(2 * 8000 * 12 + 8000))
    still, voice = upload(owner), upload(owner, "voice.wav", wav.getvalue(), "audio/wav")
    ask = {"brand_id": fomo["brand"], "model_id": "heygen-avatar-6-turbo",
           "prompt": "She talks to the lens, easy nods.",
           "skip_screen_ids": [fomo["screen"]]}  # fmt: skip
    alone = owner.post("/clips", json={**ask, "file_ids": [still]})
    assert alone.status_code == 422 and "one still and one voice" in alone.json()["detail"]
    made = owner.post("/clips", json={**ask, "file_ids": [still, voice]})
    assert made.status_code == 201, made.text
    job = db.get(Job, made.json()["id"])
    assert job.provider == "heygen" and job.input["model"] == "heygen-avatar-6-turbo"
    assert job.input["files"] == {"image": [still], "audio": [voice]}
    assert job.input["input"]["motion_prompt"] == "She talks to the lens, easy nods."
    assert job.input["input"]["resolution"] == "1080p" and job.input["input"]["duration"] == 13


def test_a_still_is_one_upright_picture_from_words_drawn_by_seedream(
        owner, editor, fomo, db):  # noqa: F811  # fmt: skip
    words = "A man of fifty sits at a podcast microphone, a phone photo."
    ask = {"brand_id": fomo["brand"], "prompt": words}
    assert editor.post("/clips/still", json=ask).status_code == 403  # Seedream is the owner's
    made = owner.post("/clips/still", json=ask)
    assert made.status_code == 201, made.text
    job = db.get(Job, made.json()["id"])
    assert job.kind == "image" and job.provider == "kie" and job.input["step"] == "still"
    assert job.input["model"] == "seedream-5.5" and job.input["input"]["prompt"] == words
    assert job.input["input"]["aspect_ratio"] == "9:16"
