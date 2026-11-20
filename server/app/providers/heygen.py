"""HeyGen (developers.heygen.com, API v3): a UGC talker from one still, lip-synced to our own
voice track by Avatar IV (app/talker.py). One job is: upload the voice (POST /v3/assets,
multipart MP3), create the video (POST /v3/videos, type "image", the still inline as base64,
audio_asset_id), then check it (GET /v3/videos/{id}: pending, processing, completed or failed)
and download `video_url` (a presigned link on HeyGen's file hosts).

Credentials: HEYGEN_API_KEY, sent only to the API in the x-api-key header, never to download
hosts, never logged; with none, nothing is sent (NoKey). HeyGen doesn't report a price: the
cost is the video's `duration` at the measured rate (batch-b and th-20s: $0.037-0.039 a second
at 720p), marked as an estimate; credits and quotes use the catalogue's rounded-up $0.05. A 429
(rate limit or concurrency) never started: tried again later.

Avatar 6 and Avatar 6 Turbo (developers.heygen.com/docs/models/avatar-6, read 20 Nov 2026) take a
raw still only on the Model API: both files uploaded as assets, POST /v3/models/avatars {model,
reference_images, audio, resolution, motion_prompt}, checked at GET /v3/models/videos/{id}. The
clip runs the length of the audio and takes the still's shape; its cost is its `duration` at
the published rate (RATES). NO REAL TAKE HAS BEEN MADE WITH THIS PATH YET."""

import base64
import re
from decimal import Decimal

import httpx2 as httpx

from app.providers import NetworkError, NoKey, NotStarted, Result, UsageItem

TIMEOUT = httpx.Timeout(60.0, connect=10.0)
DATA = re.compile(r"data:([\w/+.-]+);base64,(.*)", re.S)
SENT = ("aspect_ratio", "resolution", "expressiveness", "motion_prompt", "title")
WAITING = ("pending", "processing", "waiting")
MEASURED = Decimal("0.039")  # dollars a second at 720p, from the wallet (batch-b, th-20s)
RATES = {"heygen-avatar-6-turbo": Decimal("0.05"), "heygen-avatar-6": Decimal("0.10")}  # 1080p
MODELS = "models:"  # a Model API video's reference: checked on its own path


class HeyGenProvider:
    name = "heygen"
    paid = True

    def __init__(self, base_url: str, key: str = "", client: httpx.Client | None = None,
                 delivery_hosts: tuple[str, ...] = ("heygen.ai",),
                 max_download_mb: int = 500):  # fmt: skip
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=TIMEOUT)  # never follows redirects itself
        self.delivery_hosts = delivery_hosts
        self.max_download = max_download_mb * 1024 * 1024
        self._auth = {"x-api-key": key} if key else {}  # only to the API

    def _call(self, method: str, path: str, **kwargs) -> dict:
        if not self._auth:
            raise NoKey("HeyGen")
        try:
            r = self.client.request(method, f"{self.base_url}{path}", headers=self._auth, **kwargs)
        except httpx.TransportError as exc:
            raise NetworkError(repr(exc)) from exc
        if r.status_code == 429:
            raise NotStarted(
                "HeyGen's service is temporarily unavailable (its rate or "
                "concurrency limit); try later."
            )  # BUSY_SAID: the retry waits
        if r.status_code >= 500:
            raise NetworkError(f"HeyGen {r.status_code}: {r.text[:500]}")
        if r.status_code >= 400:  # its error code and message (e.g. insufficient_credit)
            said = (r.json() if r.headers.get("content-type", "").startswith("application/json")
                    else {}).get("error") or {}  # fmt: skip
            raise RuntimeError(f"HeyGen {r.status_code}: {said.get('code', '')} "
                               f"{said.get('message', r.text[:500])}".strip())  # fmt: skip
        return r.json().get("data") or {}

    def submit(self, kind: str, input: dict) -> str:
        """`input` is the job's: {"model", "input": {image, audio (data URLs), SENT...}}."""
        given = input["input"]
        sound_type, sound = _data(given["audio"])
        name = "voice.wav" if "wav" in sound_type else "voice.mp3"
        asset = self._call("POST", "/v3/assets", files={"file": (name, sound, sound_type)})
        picture_type, picture = _data(given["image"])
        if input.get("model") in RATES:  # Avatar 6: a raw still goes to the Model API alone
            still = self._call(
                "POST",
                "/v3/assets",
                files={"file": (f"still.{picture_type.split('/')[-1]}", picture, picture_type)},
            )
            ref = lambda a: {"type": "asset_id", "asset_id": a.get("asset_id") or a["id"]}  # noqa: E731
            body = {
                "model": input["model"],
                "reference_images": [ref(still)],
                "audio": ref(asset),
                **{k: given[k] for k in ("resolution", "motion_prompt") if given.get(k)},
            }
            return MODELS + self._call("POST", "/v3/models/avatars", json=body)["video_id"]
        body = {"type": "image", "audio_asset_id": asset.get("asset_id") or asset["id"],
                "image": {"type": "base64", "media_type": picture_type,
                          "data": base64.b64encode(picture).decode()},
                **{k: given[k] for k in SENT if given.get(k)}}  # fmt: skip
        return self._call("POST", "/v3/videos", json=body)["video_id"]

    def poll(self, ref: str) -> Result:
        new = ref.startswith(MODELS)
        video = self._call("GET", f"/v3/models/videos/{ref.removeprefix(MODELS)}" if new
                           else f"/v3/videos/{ref}")  # fmt: skip
        status = video.get("status")
        if status in WAITING:
            return Result("running")
        if status != "completed":
            said = f"{video.get('failure_code') or status}: {video.get('failure_message') or ''}"
            return Result("failed", error=said.strip(": "))
        seconds = Decimal(str(video.get("duration") or 0))
        rate = RATES.get(video.get("model"), RATES["heygen-avatar-6"]) if new else MEASURED
        usage = [UsageItem(seconds, "second", seconds * rate)]
        return Result("succeeded", output={}, files=[video["video_url"]], usage=usage)

    def _allowed(self, url: str) -> bool:
        parsed = httpx.URL(url)
        host = parsed.host.lower()
        mine = any(host == h or host.endswith(f".{h}") for h in self.delivery_hosts)
        return parsed.scheme == "https" and mine and not host.startswith("api.")

    def fetch(self, url: str) -> tuple[bytes, str]:
        """Download the video from HeyGen's file hosts (no key: the link is presigned)."""
        if not self._allowed(url):
            raise RuntimeError(f"Refusing to download from {httpx.URL(url).host!r}.")
        try:
            with self.client.stream("GET", url) as r:
                if r.status_code >= 500:
                    raise NetworkError(f"Download failed: {r.status_code}")
                r.raise_for_status()
                data = bytearray()
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > self.max_download:
                        raise RuntimeError("Output file is larger than the download cap.")
                said = r.headers.get("content-type", "").split(";")[0]  # its CDN may not say
                return bytes(data), "video/mp4" if data[4:8] == b"ftyp" else said
        except httpx.TransportError as exc:
            raise NetworkError(repr(exc)) from exc


def _data(url: str) -> tuple[str, bytes]:
    """A data URL's type and bytes (the worker hands files over as data URLs)."""
    found = DATA.fullmatch(url or "")
    if not found:
        raise RuntimeError("HeyGen needs the still and the voice as files.")
    return found[1], base64.b64decode(found[2])
