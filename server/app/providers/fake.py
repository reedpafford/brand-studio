"""A provider that does no real work, for tests and local development. Costs nothing real."""

import itertools
from decimal import Decimal

from app.providers import NetworkError, Result, UsageItem


class FakeProvider:
    name = "fake"

    def __init__(self, paid: bool = True, polls_until_done: int = 0, fail: bool = False):
        self.paid = paid  # behaves like a paid model so the no-retry rule is exercised
        self.polls_until_done = polls_until_done
        self.fail = fail
        self.network_errors_on_submit = 0
        self.network_errors_on_poll = 0
        self.submit_error: Exception | None = None  # raised by the next submit
        self.submitted: dict[str, dict] = {}
        self._polls: dict[str, int] = {}
        self._ids = itertools.count(1)

    def submit(self, kind: str, input: dict) -> str:
        if self.submit_error:
            raise self.submit_error
        if self.network_errors_on_submit:
            self.network_errors_on_submit -= 1
            raise NetworkError("fake network error")
        ref = f"fake-{next(self._ids)}"
        self.submitted[ref] = {"kind": kind, "input": input}
        self._polls[ref] = 0
        return ref

    def fetch(self, url: str) -> tuple[bytes, str]:
        return b"\0\0\0\x18ftypmp42" + b"0" * 32, "video/mp4"

    def poll(self, ref: str) -> Result:
        if self.network_errors_on_poll:
            self.network_errors_on_poll -= 1
            raise NetworkError("fake network error")
        self._polls[ref] += 1
        if self._polls[ref] <= self.polls_until_done:
            return Result("running")
        if self.fail:
            return Result("failed", error="fake failure")
        seconds = Decimal(str(self.submitted[ref]["input"].get("seconds", 1)))
        return Result(
            "succeeded",
            output={"url": f"fake://{ref}"},
            usage=[UsageItem(seconds, "second", seconds * Decimal("0.1028"))],
        )
