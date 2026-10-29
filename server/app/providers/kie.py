"""Suno through KIE (kie.ai), the way Reed's workflow reaches Suno (docs/next/song-ad-workflow.md).
Off unless BS_KIE_SUNO is true and KIE_API_KEY is set: Reed decides before it's switched on
(flows open question 4), and the test site stays on the free stand-in either way.

One request is Suno V6 Custom mode with our lyrics and style line (app/music.py A1), and
gives 2 songs (A2) as audio links (A3). Docs: docs.kie.ai, "Generate Music" (POST
/jobs/createTask) and "Get Task Details" (GET /jobs/recordInfo). KIE answers HTTP 200 even
for errors, so its own `code` is read. The key goes only to the API, never to download hosts,
and is never logged."""

import httpx2 as httpx

from app.prompts.check import sung_lines
from app.providers import NetworkError, NoKey, NotStarted, Result

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
RUNNING = ("waiting", "queuing", "generating")
MODEL, SUNO = "ai-music-api/generate", "V6"
STAND_IN = "stand-in:"  # a request the free stand-in sings (a ref of its own)


class KieSuno:
    name = "suno"
    paid = True

    def __init__(self, base_url: str, key: str, delivery_hosts: tuple[str, ...],
                 max_download_mb: int = 500, client: httpx.Client | None = None,
                 stand_in=None):  # fmt: skip
        # The test site's free stand-in, for requests that aren't real songs (made before
        # real songs were on, or once the test budget is used): never sent to KIE.
        self.stand_in = stand_in
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=TIMEOUT)  # never follows redirects itself
        self.delivery_hosts = delivery_hosts
        self.max_download = max_download_mb * 1024 * 1024
        self._auth = {"Authorization": f"Bearer {key}"} if key else {}

    def _call(self, method: str, path: str, **kwargs) -> dict:
        if not self._auth:
            raise NoKey("KIE")
        try:
            r = self.client.request(method, f"{self.base_url}{path}", headers=self._auth, **kwargs)
        except httpx.TransportError as exc:
            raise NetworkError(repr(exc)) from exc
        body = r.json() if r.status_code < 500 else {}
        code = body.get("code", r.status_code)
        if code == 429 or r.status_code == 429:
            raise NotStarted("KIE is rate limiting; try later.")
        if r.status_code >= 500 or code >= 500:
            raise NetworkError(f"KIE {code}: {str(body.get('msg') or r.text)[:500]}")
        if code != 200:  # 401 key, 402 credits, 422 the request: the job fails, plainly
            raise RuntimeError(f"KIE {code}: {str(body.get('msg'))[:2000]}")
        return body.get("data") or {}

    def submit(self, kind: str, input: dict) -> str:
        """`input` is music.job's: {"input": {lyrics, style, exclude_styles, instrumental}}."""
        if not input.get("kie"):  # not a real-song request: never sung for real
            if self.stand_in is None:
                raise RuntimeError("Not a real-song request; make it again.")
            return STAND_IN + self.stand_in.submit(kind, input)
        song = input["input"]
        title = (sung_lines(song["lyrics"]) or ["Song"])[0][:80]  # Custom mode needs one
        body = {"model": MODEL, "input": {
            "custom_mode": True, "instrumental": False, "model": SUNO, "title": title,
            "lyrics": song["lyrics"], "style": song["style"],
            "negative_tags": song.get("exclude_styles", ""),
        }}  # fmt: skip
        return self._call("POST", "/jobs/createTask", json=body)["taskId"]

    def poll(self, ref: str) -> Result:
        if ref.startswith(STAND_IN):
            return self.stand_in.poll(ref.removeprefix(STAND_IN))
        task = self._call("GET", "/jobs/recordInfo", params={"taskId": ref})
        state = task.get("state")
        if state in RUNNING:
            return Result("running")
        if state != "success":
            return Result("failed", error=f"{task.get('failCode')}: {task.get('failMsg')}")
        tracks = (task.get("response") or {}).get("data") or []
        return Result("succeeded", files=[t["audio_url"] for t in tracks if t.get("audio_url")])

    def _allowed(self, url: str) -> bool:
        """Only https on the hosts KIE delivers songs from: never internal addresses."""
        parsed = httpx.URL(url)
        host = parsed.host.lower()
        on_delivery = any(host == h or host.endswith(f".{h}") for h in self.delivery_hosts)
        return parsed.scheme == "https" and on_delivery

    def fetch(self, url: str) -> tuple[bytes, str]:
        """Download one song, stopping past the size cap (redirects aren't followed)."""
        if url.startswith("fake://") and self.stand_in is not None:
            return self.stand_in.fetch(url)
        if not self._allowed(url):
            raise RuntimeError(f"Refusing to download from {url!r}.")
        try:
            with self.client.stream("GET", url) as r:
                if r.status_code >= 500:
                    raise NetworkError(f"Download failed: {r.status_code}")
                r.raise_for_status()
                data = bytearray()
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > self.max_download:
                        raise RuntimeError("The song file is larger than the download cap.")
                return bytes(data), r.headers.get("content-type", "").split(";")[0].strip()
        except httpx.TransportError as exc:
            raise NetworkError(repr(exc)) from exc
