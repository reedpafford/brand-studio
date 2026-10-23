"""The Seedance A/B script's spending guard, with a fake provider (no real or paid calls)."""

from decimal import Decimal

from app.providers import Result, UsageItem
from evals import seedance_ab


class Fake:
    def __init__(self, cost: str):
        self.cost, self.submitted = Decimal(cost), []

    def submit(self, kind, input):
        self.submitted.append(input["input"]["prompt"])
        return f"p{len(self.submitted)}"

    def poll(self, ref):
        return Result(
            "succeeded",
            files=["https://replicate.delivery/x.mp4"],
            usage=[UsageItem(Decimal(10), "second", self.cost)],
        )

    def fetch(self, url):
        return b"mp4", "video/mp4"


def test_runs_both_variants_within_the_cap(tmp_path):
    fake = Fake("1.028")
    assert seedance_ab.run(tmp_path, fake, Decimal("2.20"), poll_every=0) == Decimal("2.056")
    assert fake.submitted == [seedance_ab.A, seedance_ab.B]
    assert (tmp_path / "A.mp4").read_bytes() == b"mp4" and (tmp_path / "B.json").exists()


def test_stops_before_a_clip_that_could_pass_the_cap(tmp_path):
    fake = Fake("1.50")  # billed more than estimated: B would pass the cap
    seedance_ab.run(tmp_path, fake, Decimal("2.20"), poll_every=0)
    assert fake.submitted == [seedance_ab.A]
    nothing = Fake("1")
    seedance_ab.run(tmp_path, nothing, Decimal("1.00"), poll_every=0)
    assert nothing.submitted == []
