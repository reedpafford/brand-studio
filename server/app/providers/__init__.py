"""Model providers behind one interface: Replicate for real work, a fake for tests."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Protocol


class NetworkError(Exception):
    """The provider couldn't be reached. The only kind of error that is retried."""


class NotStarted(Exception):
    """The provider certainly did not start the work (e.g. it said "too busy").
    Safe to try again later, even for paid work."""


@dataclass
class UsageItem:
    units: Decimal
    unit: str
    cost_usd: Decimal
    estimated: bool = False  # True when the provider didn't report the amount used


@dataclass
class Result:
    """`output` is shown to every editor, so it must never contain prices or costs:
    money goes in `usage` only. `error` is raw text and is kept owner-only."""

    state: Literal["running", "succeeded", "failed"]
    output: dict | None = None
    error: str = ""
    usage: list[UsageItem] = field(default_factory=list)
    files: list[str] = field(default_factory=list)  # provider URLs to copy into our storage


class Provider(Protocol):
    name: str
    paid: bool  # True if submitting costs money: such work is never auto-retried

    def submit(self, kind: str, input: dict) -> str:
        """Start the work and return the provider's reference for it."""

    def poll(self, ref: str) -> Result:
        """Check on work started earlier."""

    def fetch(self, url: str) -> tuple[bytes, str]:
        """Download one output file: (bytes, content type)."""


def get_providers(settings) -> dict[str, Provider]:
    from app.providers.fake import FakeProvider
    from app.providers.replicate import ReplicateProvider

    replicate = ReplicateProvider(
        settings.replicate_base_url,
        delivery_hosts=tuple(settings.replicate_delivery_hosts),
        max_download_mb=settings.max_download_mb,
    )
    return {"fake": FakeProvider(), "replicate": replicate}
