"""Replicate: start predictions, check on them, download outputs, and work out real cost.

Credentials come from the environment's network proxy, never from code or env vars.
Prices come from the catalogue; amounts used come from the prediction's metrics when
Replicate reports them (otherwise from the request, marked as an estimate)."""

from decimal import Decimal

import httpx2 as httpx

from app.catalogue import CatalogueModel, get_model
from app.providers import NetworkError, NotStarted, Result, UsageItem

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# Replicate metrics that report what was produced, by price unit.
METRIC_FOR_UNIT = {"second": "video_output_duration_seconds", "image": "image_count"}


class ReplicateProvider:
    name = "replicate"
    paid = True

    def __init__(self, base_url: str, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=TIMEOUT, follow_redirects=True)

    def _call(self, method: str, path: str, **kwargs) -> dict:
        try:
            r = self.client.request(method, f"{self.base_url}{path}", **kwargs)
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
        body = {"version": model.provider_version, "input": input["input"]}
        return self._call("POST", "/predictions", json=body)["id"]

    def poll(self, ref: str) -> Result:
        p = self._call("GET", f"/predictions/{ref}")
        status = p.get("status")
        if status in ("starting", "processing"):
            return Result("running")
        if status != "succeeded":  # failed, canceled, aborted
            return Result("failed", error=str(p.get("error") or status))
        output = p.get("output")
        model = get_model(_model_id_from_version(p))
        files = [output] if isinstance(output, str) else []
        if isinstance(output, list) and all(_is_url(o) for o in output):
            files = output
        text = "".join(output) if isinstance(output, list) and not files else None
        return Result(
            "succeeded",
            output={"text": text} if text is not None else {},
            files=files,
            usage=[_usage(model, p, len(files))] if model else [],
        )

    def fetch(self, url: str) -> tuple[bytes, str]:
        try:
            r = self.client.get(url)
        except httpx.TransportError as exc:
            raise NetworkError(repr(exc)) from exc
        if r.status_code >= 500:
            raise NetworkError(f"Download failed: {r.status_code}")
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "").split(";")[0].strip()


def _model(input: dict) -> CatalogueModel:
    model = get_model(input.get("model", ""))
    if not model:
        raise RuntimeError(f"Unknown model {input.get('model')!r}.")
    return model


def _model_id_from_version(prediction: dict) -> str:
    from app.catalogue import catalogue

    version = prediction.get("version")
    return next((m.id for m in catalogue().values() if m.provider_version == version), "")


def _is_url(value) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


def _usage(model: CatalogueModel, prediction: dict, file_count: int) -> UsageItem:
    """Real amount from metrics when present; otherwise from the request (estimated)."""
    unit = model.price.unit
    metrics = prediction.get("metrics") or {}
    request = prediction.get("input") or {}
    reported = metrics.get(METRIC_FOR_UNIT.get(unit, ""))
    estimated = reported is None
    if reported is not None:
        units = Decimal(str(reported))
    elif unit == "image":
        units, estimated = Decimal(file_count), False
    elif unit == "second":
        seconds = int(request.get("duration", 0))
        # "-1" lets the model choose; without a reported length assume the longest.
        units = Decimal(seconds if seconds > 0 else model.duration.max)
    else:
        units = Decimal(1)
    try:
        price = model.usd_per_unit(request.get("resolution"))
    except ValueError:  # resolution left to the model's default: assume the dearest
        price, estimated = max(model.price.usd.values()), True
    return UsageItem(units, unit, units * price, estimated or unit == "call")
