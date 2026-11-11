"""Google's Gemini API, direct: Gemini Omni 1.2 Flash video takes (Reed, 10 Nov: "we go omni
through google directly") and Nano Banana pictures (Reed, 11 Nov: "any nano banana... through
googles api directly. It is cheaper and better"). A take is one interaction: started in the
background, checked on, and its video read from the answer; a picture is made in the one call
and read the same way. Written from Google's docs alone (takes: read 10 Nov 2026, first real
takes 11 Nov; pictures: read 11 Nov, NO REAL PICTURE HAS BEEN MADE WITH THIS CODE YET).

What it relies on, and the page that says so (all under https://aistudio.google.com):
- /docs/omni: the model is `gemini-omni-1.2-flash`; POST {base}/interactions with `input`
  (the prompt, or content items: pictures and clips as {"type", "data": base64, "mime_type"},
  then {"type": "text"}; an uploaded clip to edit, 15 s at most, inside a `user_input` step)
  and `response_format` {"type": "video", "aspect_ratio": "9:16" | "16:9", "resolution":
  "360p" | "720p" | "1080p" | "4k", "duration": "3s" to "15s", "delivery": "uri" for a video
  over 4 MB}. No sound switch: sound is always made and the prompt steers it. Up to 6
  reference images. `generation_config.video_config.task` names the mode. The video is in
  `steps` (type model_output) → `content` (type video): `data` (base64, what GET gives today
  even when a uri was asked for) or `uri` (a file: GET /files/{id} until `state` is ACTIVE,
  then GET /files/{id}:download?alt=media). The key goes in the x-goog-api-key header.
- /docs/background-execution: `background: true` answers at once with the id; GET
  /interactions/{id} while `status` is in_progress; POST /interactions/{id}/cancel.
- /api-reference/interactions-api: every status, `usage` (total_input_tokens,
  total_output_tokens, output_tokens_by_modality, total_thought_tokens), `errors` [{code,
  message}], `video_config.task` (reference_to_video, image_to_video, edit).
- /docs/api-errors: an error is {"error": {"code", "message"}}; 429 (rate_limit_exceeded,
  quota_exceeded, too_many_requests) and 503 (service_unavailable) mean wait and try again.
- /docs/safety-settings: a blocked request is a 400 with code `safety` ("Request blocked due
  to safety violations…") or jailbreak, prohibited_content, blocklist ("Input blocked: …");
  in the background the interaction is `failed` with the same code and message in `errors`.
- /docs/pricing: $1.50 per 1M input tokens; output $12.00 per 1M video tokens (5,792 a second
  at 720p, about $0.07; 1,931 at 360p; 8,688 at 1080p; 17,376 at 4K) and $9.00 per 1M text.
- /docs/file-input-methods: inline data up to 100 MB a request.
- /docs/image-generation: `gemini-nano-banana-2.1` and `gemini-3-pro-image` (Nano Banana Pro);
  the same POST with `input` [text, then each reference as {"type": "image", "mime_type",
  "data"}] (14 at most) and `response_format` {"type": "image", "aspect_ratio", "image_size":
  "1K" | "2K" | "4K"}; the picture is in `steps` like a video, as base64 `data`. Its page shows
  no background form, so a picture is made in the one call. /docs/pricing: per 1M tokens,
  2.1 $1.50 in, $30 out as pictures (a 2K picture 1,680 tokens, $0.0504), $7.50 as text; Pro
  $2.00, $120 (1K or 2K 1,120 tokens, $0.134) and $12.00.

Not in the docs (the likeliest to be wrong on first contact): that `background` works for
Omni (its page only shows the one-call form: BS_GOOGLE_BACKGROUND=false makes takes that way);
that a `task` takes six pictures (its page says to try without first; ours is set so a
reference picture is never read as a literal first frame, as on Replicate); that GET repeats
`usage` and `response_format` for a video; whether a blocked take is billed; where a file
download redirects, if at all.

Credentials: BS_GOOGLE_API_KEY, required: with none, nothing is sent (NoKey). It goes in a
header (never a URL), only to the API's own address, and is taken out of any error text."""

import base64
import json
import re
from decimal import Decimal

import httpx2 as httpx

from app.catalogue import get_model
from app.providers import NetworkError, NoKey, NotStarted, Result, UsageItem

TIMEOUT = httpx.Timeout(60.0, connect=10.0)
WHOLE = httpx.Timeout(900.0, connect=10.0)  # a take made in one call (`background` off)
# What each of a take's files is to Omni (Replicate's inputs of the same names: its
# `reference_images` "keep the subject consistent, not literal frames")
TASKS = {"video": "edit", "image": "image_to_video", "last_frame": "image_to_video",
         "reference_images": "reference_to_video"}  # fmt: skip
BUSY = ("rate_limit_exceeded", "too_many_requests", "quota_exceeded", "service_unavailable")
BUSY_SAID = "Google's service is temporarily unavailable"  # clip_takes.BUSY_SAID: tried again
# $ per 1M tokens for each model: read in, what it makes (video or pictures), text
RATES = {"gemini-omni-1.2-flash": ("1.50", "12.00", "9.00"),
         "gemini-nano-banana-2.1": ("1.50", "30.00", "7.50"),
         "gemini-3-pro-image": ("2.00", "120.00", "12.00")}  # fmt: skip
TOKENS_A_SECOND = {"360p": 1931, "720p": 5792, "1080p": 8688, "4k": 17376}
FILE = re.compile(r"files/([\w-]+)")


class GoogleProvider:
    name = "google"
    paid = True

    def __init__(self, base_url: str, key: str = "", client: httpx.Client | None = None,
                 delivery_hosts: tuple[str, ...] = ("googleapis.com",),
                 max_download_mb: int = 500, background: bool = True):  # fmt: skip
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=TIMEOUT)  # never follows redirects itself
        self.delivery_hosts = delivery_hosts
        self.max_download = max_download_mb * 1024 * 1024
        self.background = background
        self._key = key
        self._auth = {"x-goog-api-key": key} if key else {}  # only to the API's own address

    def _clean(self, text: str) -> str:
        return text.replace(self._key, "[key]") if self._key else text

    def _call(self, method: str, path: str, **kwargs) -> dict:
        if not self._auth:
            raise NoKey("Google")
        try:
            r = self.client.request(method, f"{self.base_url}{path}", headers=self._auth, **kwargs)
        except httpx.TransportError as exc:
            raise NetworkError(self._clean(repr(exc))) from exc
        if r.status_code in (429, 503):  # its rate limit, quota or load: nothing started
            raise NotStarted(f"{BUSY_SAID} ({r.status_code}); try later.")
        if r.status_code >= 500:
            raise NetworkError(f"Google {r.status_code}: {self._clean(r.text[:500])}")
        if r.status_code >= 400:  # a block ("code": "safety") or a bad request: never billed
            raise RuntimeError(f"Google {r.status_code}: {self._clean(_said(r))}")
        return r.json()

    def submit(self, kind: str, input: dict) -> str:
        """`input` is a take's job as Replicate gets it: {"model": <catalogue id>, "input":
        {prompt, duration, resolution, aspect_ratio, reference_images | image | video}}."""
        model = get_model(input.get("model", ""), listed=True)
        if not model or not model.via or model.via.provider != self.name:
            raise RuntimeError(f"{input.get('model')!r} isn't made through Google.")
        if model.kind == "image":
            sent, slow = picture(model.via.provider_model, input["input"]), {"timeout": WHOLE}
        else:
            sent = body(model.via.provider_model, input["input"], self.background)
            slow = {} if self.background else {"timeout": WHOLE}
        return self._call("POST", "/interactions", json=sent, **slow)["id"]

    def cancel(self, ref: str) -> None:
        """Stop a take that ran past our time limit."""
        self._call("POST", f"/interactions/{ref}/cancel")

    def poll(self, ref: str) -> Result:
        found = self._call("GET", f"/interactions/{ref}")
        status = found.get("status")
        if status == "in_progress":
            return Result("running")
        usage = _usage(found)
        if status != "completed":  # failed, cancelled, incomplete: with what it cost, if said
            return Result("failed", error=self._clean(_why(found)), usage=usage)
        video = _made(found) or {}
        if video.get("data"):  # in the answer itself: read from it again when it's saved
            return Result("succeeded", output={}, usage=usage,
                          files=[f"{self.base_url}/interactions/{ref}"])  # fmt: skip
        file = FILE.search(video.get("uri") or "")
        if not file:
            return Result("failed", error="Google finished with nothing made.", usage=usage)
        try:
            state = self._call("GET", f"/files/{file[1]}").get("state")
        except (RuntimeError, NotStarted):  # no word on it: the download itself will say
            state = None
        if state == "PROCESSING":
            return Result("running")
        if state == "FAILED":
            return Result("failed", error="Google made the take but its file failed.", usage=usage)
        return Result("succeeded", output={}, usage=usage,
                      files=[f"{self.base_url}/files/{file[1]}:download?alt=media"])  # fmt: skip

    def fetch(self, url: str) -> tuple[bytes, str]:
        """The take's video: out of its interaction's answer, or its file's download. Only
        ever an address of the API's own, built here (never one an answer names)."""
        if not url.startswith(f"{self.base_url}/"):
            raise RuntimeError(f"Refusing to download from {httpx.URL(url).host!r}.")
        path = url.removeprefix(self.base_url)
        if not path.startswith("/interactions/"):
            return self._download(url)
        try:
            found = self._call("GET", path)
        except NotStarted as busy:  # the take is made: saving it is tried again, never failed
            raise NetworkError(str(busy)) from busy
        made = _made(found) or {}
        data = base64.b64decode(made.get("data") or "")
        if len(data) > self.max_download:
            raise RuntimeError("Output file is larger than the download cap.")
        return data, made.get("mime_type") or (
            "image/png" if made.get("type") == "image" else "video/mp4"
        )

    def _download(self, url: str) -> tuple[bytes, str]:
        """A file's bytes, following up to 3 redirects: the key only to the API's own address,
        anywhere else only https on Google's file hosts, and never past the size cap."""
        own = httpx.URL(self.base_url).host
        for _ in range(4):
            at = httpx.URL(url)
            mine = at.host == own
            sent_on = any(at.host == h or at.host.endswith(f".{h}") for h in self.delivery_hosts)
            if at.scheme != "https" or not (mine or sent_on):
                raise RuntimeError(f"Refusing to download from {at.host!r}.")
            try:
                with self.client.stream("GET", url, headers=self._auth if mine else {}) as r:
                    if r.is_redirect:
                        url = str(r.url.join(r.headers.get("location", "")))
                        continue
                    if r.status_code >= 500 or r.status_code == 429:
                        raise NetworkError(f"Download failed: {r.status_code}")
                    if r.status_code >= 400:
                        raise RuntimeError(f"Download failed: {r.status_code}")
                    data = bytearray()
                    for chunk in r.iter_bytes():
                        data += chunk
                        if len(data) > self.max_download:
                            raise RuntimeError("Output file is larger than the download cap.")
                    return bytes(data), "video/mp4"
            except httpx.TransportError as exc:
                raise NetworkError(self._clean(repr(exc))) from exc
        raise RuntimeError("Too many redirects downloading the output.")


def body(model: str, given: dict, background: bool = True) -> dict:
    """A take's input as Google's API takes it; what it says is unchanged. Its pictures (or
    the clip to edit) go inline, before the prompt; the length is "8s"; an edit sends neither
    length nor shape (it keeps its take's). There is no sound switch to send."""
    media = [(k, given[k]) for k in ("video", "image", "last_frame") if given.get(k)]
    media += [("reference_images", picture) for picture in given.get("reference_images") or []]
    tasks = {TASKS[k] for k, _ in media}
    if len(tasks) > 1:  # as Replicate refuses it: a start frame or references, never both
        raise RuntimeError("Input validation failed: Omni takes a start frame, reference "
                           "pictures or a clip to edit, never two of them.")  # fmt: skip
    content = [_media(k, v) for k, v in media] + [{"type": "text", "text": given["prompt"]}]
    fmt = {"type": "video", "delivery": "uri",
           **{k: given[k] for k in ("aspect_ratio", "resolution") if given.get(k)}}  # fmt: skip
    if given.get("duration"):
        fmt["duration"] = f"{int(given['duration'])}s"
    sent = {"model": model, "input": given["prompt"], "response_format": fmt,
            "background": background}  # fmt: skip
    if media:
        edit = "edit" in tasks
        sent["input"] = [{"type": "user_input", "content": content}] if edit else content
        sent["generation_config"] = {"video_config": {"task": tasks.pop()}}
    return sent


def picture(model: str, given: dict) -> dict:
    """An image job's input (app/images.py) as Google takes it: the prompt, then each
    reference inline, and the shape and size it's drawn at."""
    content = [{"type": "text", "text": given["prompt"]}]
    content += [_media("image", url) for url in given.get("image_input") or []]
    return {"model": model, "input": content,
            "response_format": {"type": "image", "aspect_ratio": given["aspect_ratio"],
                                "image_size": given.get("resolution") or "1K"}}  # fmt: skip


def _media(key: str, url: str) -> dict:
    """A picture or clip (the worker's data URL) as an inline content item."""
    head, found, data = (url or "").partition(";base64,")
    if not found or not head.startswith("data:"):
        raise RuntimeError("Google needs each picture or clip as a file.")
    kind = "video" if key == "video" else "image"
    return {"type": kind, "data": data, "mime_type": head.removeprefix("data:")}


def _said(r: httpx.Response) -> str:
    """An error answer's own code and message, as one line of JSON (clip_takes reads it)."""
    try:
        error = r.json().get("error")
    except (ValueError, AttributeError):
        error = None
    return json.dumps(error)[:2000] if isinstance(error, dict) else r.text[:2000]


def _why(found: dict) -> str:
    """Why an interaction didn't finish, in its own codes and words; one its rate limit or
    load stopped reads as busy, so it's tried again like any busy take."""
    errors = [e for e in found.get("errors") or [] if isinstance(e, dict)]
    busy = any(str(e.get("code", "")).rsplit("/", 1)[-1] in BUSY for e in errors)
    head = BUSY_SAID if busy else f"Google {found.get('status')}"
    return f"{head}: {json.dumps(errors)[:1800]}" if errors else head


def _made(found: dict) -> dict | None:
    """The video or picture it made: in the model's own step (the last one: a picture can come
    with drafts), never the clip an edit was given."""
    steps = [s for s in found.get("steps") or [] if s.get("type") == "model_output"]
    items = [c for s in steps for c in s.get("content") or []]
    return next((c for c in reversed(items) if c.get("type") in ("video", "image")), None)


def _usage(found: dict) -> list[UsageItem]:
    """What it cost: the tokens Google counted at its list prices; when it counted none, a made
    take's asked seconds (or a picture) at the catalogue's price, as an estimate. Neither said:
    nothing here, and the worker records the job's own price as an estimate."""
    used = found.get("usage") or {}
    asked = found.get("response_format")
    asked = asked if isinstance(asked, dict) else {}
    model = get_model(_catalogue_id(found.get("model")), listed=True)
    image = bool(model and model.kind == "image")
    resolution = asked.get("image_size" if image else "resolution") or ("2K" if image else "720p")
    said = re.fullmatch(r"(\d+)s", str(asked.get("duration") or ""))
    seconds = Decimal(said[1]) if said else Decimal(0)
    out = int(used.get("total_output_tokens") or 0)
    by_kind = {m.get("modality"): int(m.get("tokens") or 0)
               for m in used.get("output_tokens_by_modality") or []}  # fmt: skip
    made = by_kind.get("image" if image else "video", out)  # "billing is based on total output"
    if made:
        usd_in, usd_made, usd_text = (Decimal(r) for r in RATES.get(
            found.get("model"), RATES["gemini-omni-1.2-flash"]))  # fmt: skip
        text = max(0, out - made) + int(used.get("total_thought_tokens") or 0)
        cost = ((int(used.get("total_input_tokens") or 0) * usd_in + made * usd_made
                 + text * usd_text) / 1_000_000).quantize(Decimal("0.0001"))  # fmt: skip
        if image:
            return [UsageItem(Decimal(1), "image", cost)]
        length = Decimal(made) / TOKENS_A_SECOND.get(resolution, TOKENS_A_SECOND["720p"])
        return [UsageItem(seconds or length.quantize(Decimal("0.1")), "second", cost)]
    if found.get("status") != "completed" or not model or not (image or seconds):
        return []
    price = model.via.usd.get(resolution) or max(model.via.usd.values())
    if image:
        return [UsageItem(Decimal(1), "image", price, estimated=True)]
    return [UsageItem(seconds, "second", seconds * price, estimated=True)]


def _catalogue_id(name) -> str:
    from app.catalogue import catalogue

    return next((m.id for m in catalogue().values() if m.via and m.via.provider_model == name), "")
