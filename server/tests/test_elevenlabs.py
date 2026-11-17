"""A speaker's designed voice through ElevenLabs' own API (app/providers/elevenlabs.py), against
a mock of the request as its SDK sends it: no paid call."""

import base64
import json
from decimal import Decimal

import httpx2 as httpx
import pytest

from app.providers import NoKey, NotStarted, get_providers
from app.providers.elevenlabs import ElevenLabsProvider
from app.settings import Settings

BASE = "https://api.elevenlabs.io"
JOB = {"model": "elevenlabs-voice-design", "input": {"voice_description": "a woman of 46, warm"}}


def _eleven(status=200, key="test-key"):
    seen = []

    def api(request):
        seen.append(request)
        sound = base64.b64encode(b"ID3first").decode()
        said = {"previews": [{"audio_base_64": sound}, {"audio_base_64": "AAAA"}], "text": "Hi."}
        return httpx.Response(status, json=said if status == 200 else {"detail": "no"})

    return ElevenLabsProvider(BASE, key, httpx.Client(transport=httpx.MockTransport(api))), seen


def test_a_voice_is_designed_from_its_words_and_its_first_sample_is_the_voice():
    eleven, seen = _eleven()
    ref = eleven.submit("voice", JOB)
    (sent,) = seen
    assert str(sent.url) == f"{BASE}/v1/text-to-voice/design"
    assert sent.headers["xi-api-key"] == "test-key"
    assert json.loads(sent.content) == {"voice_description": "a woman of 46, warm",
                                        "auto_generate_text": True}  # fmt: skip
    made = eleven.poll(ref)
    assert (made.state, made.files) == ("succeeded", [ref])
    (cost,) = made.usage  # ElevenLabs names no price: the catalogue's estimate
    assert (cost.cost_usd, cost.estimated) == (Decimal("0.10"), True)
    assert eleven.fetch(ref) == (b"ID3first", "audio/mpeg")
    assert eleven.poll(ref).state == "failed"  # saved once; a lost one says so


def test_no_key_or_a_busy_service_starts_nothing_paid():
    eleven, seen = _eleven(key="")
    with pytest.raises(NoKey):
        eleven.submit("voice", JOB)
    assert not seen
    with pytest.raises(NotStarted):
        _eleven(status=429)[0].submit("voice", JOB)
    with pytest.raises(RuntimeError, match="ElevenLabs 401"):
        _eleven(status=401)[0].submit("voice", JOB)


def test_the_provider_is_there_only_with_its_key():
    real = {"fake_providers": False, "env": "development"}
    assert "elevenlabs" not in get_providers(Settings(**real))
    assert "elevenlabs" in get_providers(Settings(**real, ELEVENLABS_API_KEY="k"))
