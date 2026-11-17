"""ElevenLabs' own API (elevenlabs.io/docs/api-reference/text-to-voice/design): a voice designed
from a few words about a person, for the speakers of a video whose model hears a voice sample
(app/voice_carry.py; Reed, 17 Nov 2026, after his by-hand test: "the voice and elevenlabs touch
was amazing"). One job is one request: POST /v1/text-to-voice/design {voice_description,
auto_generate_text}, answered at once with three previews (base64 MP3, about 10 s each, of
words it wrote itself); the first is the voice.

Credentials: ELEVENLABS_API_KEY, sent only to the API in the xi-api-key header, never logged;
with none, nothing is sent (NoKey). ElevenLabs reports no price for a design, so the cost is the
catalogue's estimate. The sample is held from `submit` to `poll` in this process; a worker
restarted between them has lost it, and the speaker's sample is then cut from a take as before."""

import base64
import uuid
from decimal import Decimal

import httpx2 as httpx

from app.providers import NetworkError, NoKey, NotStarted, Result, UsageItem

TIMEOUT = httpx.Timeout(120.0, connect=10.0)
COST = Decimal("0.10")  # the catalogue's `elevenlabs-voice-design`: an estimate


class ElevenLabsProvider:
    name = "elevenlabs"
    paid = True

    def __init__(self, base_url: str, key: str = "", client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=TIMEOUT)
        self._auth = {"xi-api-key": key} if key else {}  # only to the API
        self._made: dict[str, bytes] = {}

    def submit(self, kind: str, input: dict) -> str:
        """`input` is the job's: {"model", "input": {"voice_description"}}."""
        if not self._auth:
            raise NoKey("ElevenLabs")
        body = {"voice_description": input["input"]["voice_description"],
                "auto_generate_text": True}  # fmt: skip
        try:
            r = self.client.post(f"{self.base_url}/v1/text-to-voice/design", headers=self._auth,
                                 json=body)  # fmt: skip
        except httpx.TransportError as exc:
            raise NetworkError(repr(exc)) from exc
        if r.status_code == 429:
            raise NotStarted("ElevenLabs' service is temporarily unavailable; try later.")
        if r.status_code >= 500:
            raise NetworkError(f"ElevenLabs {r.status_code}: {r.text[:500]}")
        if r.status_code >= 400:
            raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:500]}")
        previews = r.json().get("previews") or []
        if not previews:
            raise RuntimeError("ElevenLabs answered with no voice.")
        ref = uuid.uuid4().hex
        self._made[ref] = base64.b64decode(previews[0]["audio_base_64"])
        return ref

    def poll(self, ref: str) -> Result:
        if ref not in self._made:
            return Result("failed", error="The designed voice was lost before it was saved.")
        return Result("succeeded", output={}, files=[ref],
                      usage=[UsageItem(Decimal(1), "call", COST, estimated=True)])  # fmt: skip

    def fetch(self, url: str) -> tuple[bytes, str]:
        return self._made.pop(url), "audio/mpeg"
