"""Replicate: start predictions, check on them, download outputs, and work out real cost.

Credentials: REPLICATE_API_TOKEN, required: with none, nothing is sent (NoKey), because a
sandbox's network proxy would sign a bare request. The token goes only to the API, never to
download hosts, and is never logged.
Prices come from the catalogue; amounts used come from the prediction's metrics when
Replicate reports them (otherwise from the request, marked as an estimate)."""

from decimal import Decimal

import httpx2 as httpx

from app.catalogue import CatalogueModel, get_model
from app.providers import NetworkError, NoKey, NotStarted, Result, UsageItem

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# Replicate metrics that report what was produced, by price unit.
METRIC_FOR_UNIT = {"second": "video_output_duration_seconds", "image": "image_count"}


class ReplicateProvider:
    name = "replicate"
    paid = True

    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        delivery_hosts: tuple[str, ...] = ("replicate.delivery",),
        max_download_mb: int = 500,
        token: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=TIMEOUT)  # never follows redirects itself
        self.delivery_hosts = delivery_hosts
        self.max_download = max_download_mb * 1024 * 1024
        # Only sent to the API (never to download hosts). Empty: nothing is sent (NoKey).
        self._auth = {"Authorization": f"Bearer {token}"} if token else {}

    def _call(self, method: str, path: str, **kwargs) -> dict:
        if not self._auth:
            raise NoKey("Replicate")
        try:
            r = self.client.request(method, f"{self.base_url}{path}", headers=self._auth, **kwargs)
        except httpx.TransportError as exc:
            raise NetworkError(repr(exc)) from exc
        if r.status_code == 429:
            raise NotStarted("Replicate is rate limiting; try later.")
        if r.status_code >= 500:
            raise NetworkError(f"Replicate {r.status_code}: {r.text[:500]}")
        if r.status_code >= 400:
            raise RuntimeError(f"Replicate {r.status_code}: {r.text[:2000]}")
        return r.json()

    def submit(self, kind: str, input: dict) -> str:
        """`input` is {"model": <catalogue id>, "input": {...Replicate input...}}."""
        model = _model(input)
        if not model.provider_version:  # an official model runs on its model's own endpoint
            path = f"/models/{model.provider_model}/predictions"
            return self._call("POST", path, json={"input": input["input"]})["id"]
        body = {"version": model.provider_version, "input": input["input"]}
        return self._call("POST", "/predictions", json=body)["id"]

    def cancel(self, ref: str) -> None:
        """Stop a prediction that ran past our time limit (Replicate: POST .../cancel)."""
        self._call("POST", f"/predictions/{ref}/cancel")

    def poll(self, ref: str) -> Result:
        p = self._call("GET", f"/predictions/{ref}")
        status = p.get("status")
        if status in ("starting", "processing"):
            return Result("running")
        if status != "succeeded":  # failed, canceled, aborted
            return Result("failed", error=str(p.get("error") or status))
        output = p.get("output")
        model = get_model(_model_id_from_version(p))
        if isinstance(output, dict):  # named fields (a voice clone: voice_id, preview, model)
            files = [v for v in output.values() if _is_url(v)]
            return Result("succeeded", output={"fields": output}, files=files,
                          usage=[_usage(model, p, len(files))] if model else [])  # fmt: skip
        parts = [output] if isinstance(output, str) else output if isinstance(output, list) else []
        is_files = bool(parts) and all(_is_url(o) for o in parts)
        files = parts if is_files else []
        text = None if is_files or not parts else "".join(str(o) for o in parts)
        return Result(
            "succeeded",
            output={"text": text} if text is not None else {},
            files=files,
            usage=[_usage(model, p, len(files))] if model else [],
        )

    def _allowed(self, url: str) -> bool:
        """Only https on Replicate's delivery hosts: never internal addresses or the API."""
        parsed = httpx.URL(url)
        host = parsed.host.lower()
        on_delivery = any(host == h or host.endswith(f".{h}") for h in self.delivery_hosts)
        return parsed.scheme == "https" and on_delivery

    def fetch(self, url: str) -> tuple[bytes, str]:
        """Download one output, following up to 3 redirects that stay on delivery hosts,
        and stopping past the size cap."""
        for _ in range(4):
            if not self._allowed(url):
                raise RuntimeError(f"Refusing to download from {url!r}.")
            try:
                with self.client.stream("GET", url) as r:
                    if r.is_redirect:
                        url = str(r.url.join(r.headers.get("location", "")))
                        continue
                    if r.status_code >= 500:
                        raise NetworkError(f"Download failed: {r.status_code}")
                    r.raise_for_status()
                    data = bytearray()
                    for chunk in r.iter_bytes():
                        data += chunk
                        if len(data) > self.max_download:
                            raise RuntimeError("Output file is larger than the download cap.")
                    content_type = r.headers.get("content-type", "").split(";")[0].strip()
                    return bytes(data), content_type
            except httpx.TransportError as exc:
                raise NetworkError(repr(exc)) from exc
        raise RuntimeError("Too many redirects downloading the output.")


def _model(input: dict) -> CatalogueModel:
    model = get_model(input.get("model", ""))
    if not model:
        raise RuntimeError(f"Unknown model {input.get('model')!r}.")
    return model


def _model_id_from_version(prediction: dict) -> str:
    from app.catalogue import catalogue

    version, name = prediction.get("version"), prediction.get("model")
    for m in catalogue().values():  # an official model's prediction names its model, no version
        if (m.provider_version or m.provider_model) == (version if m.provider_version else name):
            return m.id
    return ""


def _is_url(value) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


def _usage(model: CatalogueModel, prediction: dict, file_count: int) -> UsageItem:
    """Real amount from metrics when present; otherwise from the request (estimated)."""
    unit = model.price.unit
    metrics = prediction.get("metrics") or {}
    request = prediction.get("input") or {}
    rate, ran = model.price.gpu_usd_per_second, metrics.get("predict_time")
    if rate and ran is not None:  # billed by GPU time (MMAudio): what this run really cost
        return UsageItem(Decimal(1), unit, Decimal(str(ran)) * rate, False)
    reported = metrics.get(METRIC_FOR_UNIT.get(unit, ""))
    estimated = reported is None
    if reported is not None:
        units = Decimal(str(reported))
    elif unit == "image":
        units, estimated = Decimal(file_count), False
    elif unit == "thousand_characters":  # speech: billed on the text sent (MiniMax's `text`)
        said = request.get("prompt") or request.get("text") or ""
        units, estimated = Decimal(len(said)) / 1000, False
    elif unit == "second":
        seconds = int(request.get("duration", 0))
        # "-1" lets the model choose; without a reported length assume the longest
        longest = model.duration.max if model.duration else 0
        units = Decimal(seconds if seconds > 0 else longest)
    else:
        units = Decimal(1)
    try:  # an edit (a `video` given to a model that edits) at its own price
        price = model.usd_per_unit(request.get("resolution"), bool(request.get("video")))
    except ValueError:  # resolution left to the model's default: assume the dearest
        price, estimated = max(model.price.usd.values()), True
    return UsageItem(units, unit, units * price, estimated or unit == "call")
