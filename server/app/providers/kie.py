"""KIE (kie.ai): Suno songs, the way Reed's workflow reaches Suno (docs/next/song-ad-workflow.md),
and the pictures and takes of real-looking people (Reed, 12 Nov): Seedream 5.5 character sheets
and Seedance 2.5 takes.

Songs (`KieSuno`) are off unless BS_KIE_SUNO is true and KIE_API_KEY is set: Reed decides
before it's switched on (flows open question 4), and the test site stays on the free stand-in
either way. One request is Suno V6 Custom mode with our lyrics and style line (app/music.py
A1), and gives 2 songs (A2) as audio links (A3). Docs: docs.kie.ai, "Generate Music" (POST
/jobs/createTask) and "Get Task Details" (GET /jobs/recordInfo).

Pictures and takes (`KieMedia`: the catalogue's models whose `provider` is "kie") need only
the key. Why they go this way: ByteDance's Seedance refuses an uploaded picture of a
real-looking face ("input image may contain real person"), on Replicate too, but trusts a
face its own Seedream drew from words on the same account. Reed's tests by hand on kie.ai, 12
Nov: KIE's Seedance 2.5 took a sheet KIE's Seedream 5.5 made, also when its saved PNG was
uploaded again untouched; Replicate's refused the same sheet. A scaled or re-encoded copy is
untested, so every reference goes as the file we hold, byte for byte (the worker skips its
scaling for this provider), and Seedream is only ever asked from words.

Written from KIE's docs alone (read 12 Nov 2026): NO REAL PICTURE OR TAKE HAS BEEN MADE WITH
THIS CODE YET. What it relies on, and the page that says so (under https://docs.kie.ai):
- / (getting started): `Authorization: Bearer`; an error is HTTP 200 with its own `code` (401
  the key, 402 credits, 422 the request, 429 the rate limit: "rejected requests will not
  enter the queue"); made files are kept 14 days.
- /market/seedream/5-5-text-to-image: POST /jobs/createTask {"model":
  "seedream/5-5-text-to-image", "input": {prompt (5 to 5,000 characters), aspect_ratio, size
  "1K" | "1.5K" | "2K", output_format, background, nsfw_checker}} answers {"taskId"}; its
  example result is on tempfile.aiquickdraw.com.
- /market/bytedance/seedance-2-5: the model is `bytedance/seedance-2-5`; `input` is prompt
  (20,480 characters at most), reference_image_urls (30: jpeg, png or webp, each side 300 to
  6,000 px, under 30 MB), reference_video_urls and reference_audio_urls (10 each, 30 s of each
  in all), or first_frame_url and last_frame_url, never with references;
  omni_reference_task_type (auto, reference, edit, extend: it "only takes effect when
  reference materials are supplied", and is refused without them), generate_audio, resolution,
  aspect_ratio, duration (4 to 30), output_format, web_search, draft, nsfw_checker.
- /market/common/get-task-detail: GET /jobs/recordInfo?taskId= gives `state` (waiting,
  queuing, generating, success, fail), `resultJson` (a JSON string, {"resultUrls": [...]};
  `response` is the same, parsed), `failCode`, `failMsg`, `creditsConsumed`, `model`, and
  `param` (the request as a JSON string whose `input` is one too).
- /file-upload-api/quickstart and /file-upload-api/upload-file-stream: POST
  https://kieai.redpandaai.co/api/file-stream-upload, multipart `file`, `uploadPath` and
  `fileName`, with the same Bearer key, answers {"code": 200, "data": {"downloadUrl"}}; it is
  free, and "uploaded files are deleted 24 hours after upload".
- The prices are on kie.ai/seedream-5-5 and kie.ai/seedance-2-5 (the catalogue's
  price_source), in KIE credits at $0.005 each.

Not in the docs (the likeliest to be wrong on first contact):
- that a prompt names its pictures `@Image1` (KIE's playground, 12 Nov; no page says how):
  the site's [Image1], [Video1] and [Audio1] are sent as @Image1, @Video1 and @Audio1;
- that Seedance takes a file from the upload API's host (tempfile.redpandaai.co in the docs;
  the playground's own uploads landed on tempfileb.aiquickdraw.com), and trusts a Seedream
  sheet that arrives that way as it did in the playground;
- `omni_reference_task_type`: "auto" as the playground sent it in Reed's tests (the docs: the
  model works out the task), but "reference" (the docs' own example) once a reference video
  goes too, so a brand's clip is never taken as one to edit or extend;
- where a take is delivered from (Reed's came from tempfile.aiquickdraw.com:
  BS_KIE_MEDIA_DELIVERY_HOSTS), what type that host says a file is, and whether it redirects
  (a redirect isn't followed);
- how a refusal is worded, and whether a refused or failed task is billed (`creditsConsumed`
  is recorded whenever it says so);
- the upload API's size limit (it only says to stream a file over 10 MB).

KIE answers HTTP 200 even for errors, so its own `code` is read. The key goes only to the API
and its file upload, never to download hosts, and is never logged."""

import base64
import hashlib
import json
import mimetypes
import re
from decimal import Decimal

import httpx2 as httpx

from app.catalogue import get_model
from app.prompts.check import sung_lines
from app.providers import NetworkError, NoKey, NotStarted, Result, UsageItem

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
RUNNING = ("waiting", "queuing", "generating")
MODEL, SUNO = "ai-music-api/generate", "V6"
STAND_IN = "stand-in:"  # a request the free stand-in sings (a ref of its own)
AGAIN = "fetch_again"  # in a job: the KIE task whose songs were made but not saved by us
FETCHED = "again:"  # its ref: the same task read again (free: no new request, no new cost)
TAG = re.compile(r"\[(Image|Video|Audio)(\d+)\]")  # the site's [Image1]; KIE's is @Image1
# A take's files as the site names them (Replicate's inputs), and as KIE does
URLS = {"reference_images": "reference_image_urls", "reference_videos": "reference_video_urls",
        "reference_audios": "reference_audio_urls", "image": "first_frame_url",
        "last_frame_image": "last_frame_url"}  # fmt: skip
FOLDER = "references"  # where our uploads sit in KIE's file store (its `uploadPath`)


class Kie:
    """What KIE's two roads share: the key, a call, its dollar a credit, the download rules."""

    paid = True

    def __init__(self, base_url: str, key: str, delivery_hosts: tuple[str, ...],
                 max_download_mb: int = 500, client: httpx.Client | None = None,
                 usd_per_credit: float = 0.005):  # fmt: skip
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=TIMEOUT)  # never follows redirects itself
        self.delivery_hosts = delivery_hosts
        self.max_download = max_download_mb * 1024 * 1024
        self._auth = {"Authorization": f"Bearer {key}"} if key else {}
        self.usd_per_credit = Decimal(str(usd_per_credit))

    def _call(self, method: str, path: str, **kwargs) -> dict:
        """`path`: under the API's address, or the file upload's whole address."""
        if not self._auth:
            raise NoKey("KIE")
        url = path if path.startswith("https://") else f"{self.base_url}{path}"
        try:
            r = self.client.request(method, url, headers=self._auth, **kwargs)
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

    def _usd(self, credits) -> Decimal:
        return (Decimal(str(credits)) * self.usd_per_credit).quantize(Decimal("0.0001"))

    def _allowed(self, url: str) -> bool:
        """Only https on the hosts KIE delivers from: never internal addresses."""
        parsed = httpx.URL(url)
        host = parsed.host.lower()
        on_delivery = any(host == h or host.endswith(f".{h}") for h in self.delivery_hosts)
        return parsed.scheme == "https" and on_delivery

    def fetch(self, url: str) -> tuple[bytes, str]:
        """Download one made file, stopping past the size cap (redirects aren't followed)."""
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
                        raise RuntimeError("The file is larger than the download cap.")
                return bytes(data), r.headers.get("content-type", "").split(";")[0].strip()
        except httpx.TransportError as exc:
            raise NetworkError(repr(exc)) from exc


class KieSuno(Kie):
    name = "suno"

    def __init__(self, *args, stand_in=None, usd_per_request: float = 0.06, **kwargs):
        super().__init__(*args, **kwargs)
        # The test site's free stand-in, for requests that aren't real songs (made before
        # real songs were on, or once the test budget is used): never sent to KIE.
        self.stand_in = stand_in
        self.usd_per_request = Decimal(str(usd_per_request))

    def submit(self, kind: str, input: dict) -> str:
        """`input` is music.job's: {"input": {lyrics, style, exclude_styles, instrumental}}."""
        if not input.get("kie"):  # not a real-song request: never sung for real
            if self.stand_in is None:
                raise RuntimeError("Not a real-song request; make it again.")
            return STAND_IN + self.stand_in.submit(kind, input)
        if input.get(AGAIN):  # its songs were made and paid for: read the same task again
            return FETCHED + input[AGAIN]
        song = input["input"]
        title = (sung_lines(song["lyrics"]) or ["Song"])[0][:80]  # Custom mode needs one
        body = {"model": MODEL, "input": {
            "custom_mode": True, "instrumental": False, "model": SUNO, "title": title,
            "lyrics": song["lyrics"], "style": song["style"],
            "negative_tags": song.get("exclude_styles", ""),
        }}  # fmt: skip
        if song.get("vocal_gender") in ("f", "m"):  # from the style line; else Suno picks
            body["input"]["vocal_gender"] = song["vocal_gender"]  # KIE's docs and pilots: snake
        return self._call("POST", "/jobs/createTask", json=body)["taskId"]

    def poll(self, ref: str) -> Result:
        if ref.startswith(STAND_IN):
            return self.stand_in.poll(ref.removeprefix(STAND_IN))
        again = ref.startswith(FETCHED)
        task = self._call("GET", "/jobs/recordInfo", params={"taskId": ref.removeprefix(FETCHED)})
        state = task.get("state")
        if state in RUNNING:
            return Result("running")
        usage = [] if again else self._cost(task, state == "success")
        if state != "success":
            return Result("failed", error=f"{task.get('failCode')}: {task.get('failMsg')}",
                          usage=usage)  # fmt: skip
        tracks = (task.get("response") or {}).get("data") or []
        files = [t["audio_url"] for t in tracks if t.get("audio_url")]
        return Result("succeeded", files=files, usage=usage)

    def _cost(self, task: dict, made: bool) -> list[UsageItem]:
        """What KIE took for the request (`creditsConsumed`, at its dollar a credit); a made
        song KIE didn't report is its usual price, marked estimated. A failure it didn't
        charge costs nothing."""
        used = task.get("creditsConsumed")
        if used:
            return [UsageItem(Decimal(1), "request", self._usd(used))]
        if made:
            return [UsageItem(Decimal(1), "request", self.usd_per_request, estimated=True)]
        return []

    def fetch(self, url: str) -> tuple[bytes, str]:
        if url.startswith("fake://") and self.stand_in is not None:
            return self.stand_in.fetch(url)
        return super().fetch(url)


class KieMedia(Kie):
    """Seedream 5.5 pictures and Seedance 2.5 takes: one task each, started, then checked on."""

    name = "kie"

    def __init__(self, *args, upload_url: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.upload_url = upload_url.rstrip("/")

    def submit(self, kind: str, input: dict) -> str:
        """`input` is the job as Replicate would get it: {"model": <catalogue id>, "input":
        {prompt, …}} with its files as the worker's data URLs. A take's files are uploaded
        first (free), so one that fails there has started nothing paid."""
        model = get_model(input.get("model", ""))
        if not model or model.provider != self.name:
            raise RuntimeError(f"{input.get('model')!r} isn't made through KIE.")
        given = input["input"]
        sent = picture(given) if model.kind == "image" else take(given, self._upload)
        body = {"model": model.provider_model, "input": sent}
        return self._call("POST", "/jobs/createTask", json=body)["taskId"]

    def _upload(self, url: str) -> str:
        """One reference (the worker's data URL) put on KIE's file store exactly as we hold
        it, named by its own bytes; its address there."""
        head, found, data = (url or "").partition(";base64,")
        if not found or not head.startswith("data:"):
            raise RuntimeError("KIE needs each picture or clip as a file.")
        kind, raw = head.removeprefix("data:"), base64.b64decode(data)
        ending = mimetypes.guess_extension(kind) or f".{kind.rpartition('/')[2]}"
        name = hashlib.sha256(raw).hexdigest()[:32] + ending
        try:
            got = self._call("POST", f"{self.upload_url}/api/file-stream-upload",
                             files={"file": (name, raw, kind)},
                             data={"uploadPath": FOLDER, "fileName": name})  # fmt: skip
        except NetworkError as exc:  # no task was asked for yet: safe to try again
            raise NotStarted(f"KIE's file upload didn't answer: {exc}") from exc
        return got["downloadUrl"]

    def poll(self, ref: str) -> Result:
        task = self._call("GET", "/jobs/recordInfo", params={"taskId": ref})
        state = task.get("state")
        if state in RUNNING:
            return Result("running")
        usage = self._cost(task, state == "success")
        if state != "success":
            return Result("failed", error=f"{task.get('failCode')}: {task.get('failMsg')}",
                          usage=usage)  # fmt: skip
        made = _read(task.get("resultJson")) or _read(task.get("response"))
        if not made.get("resultUrls"):
            return Result("failed", error="KIE finished with nothing made.", usage=usage)
        return Result("succeeded", output={}, files=made["resultUrls"], usage=usage)

    def _cost(self, task: dict, made: bool) -> list[UsageItem]:
        """What KIE took (`creditsConsumed`, at its dollar a credit), for a take's asked
        seconds or one picture; a failure it says took 0 is recorded as $0, so it's never
        counted as spent. When it doesn't say: nothing here, and the worker records a made
        job's own price as an estimate."""
        used = task.get("creditsConsumed")
        if used is None or (made and not used):
            return []
        seconds = _read(_read(task.get("param")).get("input")).get("duration")
        if isinstance(seconds, int) and seconds > 0:
            return [UsageItem(Decimal(seconds), "second", self._usd(used))]
        unit = "image" if str(task.get("model")).startswith("seedream") else "request"
        return [UsageItem(Decimal(1), unit, self._usd(used))]

    def fetch(self, url: str) -> tuple[bytes, str]:
        """A made file; one its host doesn't call a picture or a video is named by its
        address's ending, so a take that was paid for is never lost to a label."""
        data, kind = super().fetch(url)
        named = mimetypes.guess_type(httpx.URL(url).path)[0]
        return data, kind if kind.startswith(("image/", "video/")) or not named else named


def picture(given: dict) -> dict:
    """An image job's input (app/images.py) as Seedream takes it: from words only (Seedance
    trusts only what Seedream drew from text), an opaque PNG at the size asked."""
    if given.get("image_input"):
        raise RuntimeError("Seedream draws from words only: it takes no reference pictures.")
    return {"prompt": given["prompt"], "aspect_ratio": given["aspect_ratio"],
            "size": given.get("resolution") or "2K", "output_format": "png",
            "background": "opaque", "nsfw_checker": True}  # fmt: skip


def take(given: dict, upload) -> dict:
    """A take's input as KIE's Seedance takes it; what it says is unchanged but for its
    picture tags ([Image1] to @Image1). Each file goes as its address on KIE's file store
    (`upload`): references, or a start and end frame."""
    sent = {"prompt": TAG.sub(r"@\1\2", given["prompt"]),
            **{k: given[k] for k in ("generate_audio", "resolution", "aspect_ratio", "duration")
               if k in given},
            "output_format": "mp4", "web_search": False, "draft": False,
            "nsfw_checker": True}  # fmt: skip
    for ours, theirs in URLS.items():
        if files := given.get(ours):
            sent[theirs] = upload(files) if isinstance(files, str) else [upload(f) for f in files]
    if any(k.startswith("reference_") for k in sent):  # refused on a take with none
        clip = "reference_video_urls" in sent  # a brand's clip: never one to edit or extend
        sent["omni_reference_task_type"] = "reference" if clip else "auto"
    return sent


def _read(text) -> dict:
    """A JSON string KIE puts inside its answer (`resultJson`, `param` and its `input`)."""
    try:
        found = json.loads(text) if isinstance(text, str) else text
    except ValueError:
        return {}
    return found if isinstance(found, dict) else {}
