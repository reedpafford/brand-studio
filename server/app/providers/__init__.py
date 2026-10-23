"""Model providers behind one interface. Real Replicate adapters come later; tests use the fake."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Protocol


class NetworkError(Exception):
    """The provider couldn't be reached. The only kind of error that is retried."""


@dataclass
class UsageItem:
    units: Decimal
    unit: str
    cost_usd: Decimal


@dataclass
class Result:
    state: Literal["running", "succeeded", "failed"]
    output: dict | None = None
    error: str = ""
    usage: list[UsageItem] = field(default_factory=list)


class Provider(Protocol):
    name: str
    paid: bool  # True if submitting costs money: such work is never auto-retried

    def submit(self, kind: str, input: dict) -> str:
        """Start the work and return the provider's reference for it."""

    def poll(self, ref: str) -> Result:
        """Check on work started earlier."""


def get_providers() -> dict[str, Provider]:
    from app.providers.fake import FakeProvider

    return {"fake": FakeProvider()}
