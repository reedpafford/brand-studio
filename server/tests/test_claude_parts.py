"""A clip prompt run's parts are asked at the same time (Producer, approved by Reed): each part
only ever sees the shared prompt, so asking them together changes nothing but the wait. The
first goes alone until its answer begins, so the rest read the shared prompt's cache."""

import threading
import time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.claude import ClaudeError
from app.providers import NetworkError, NotStarted
from app.providers.claude import PARALLEL, ClaudeProvider

INPUT = {"step": "clip_prompts", "system": ["Rules."], "prompt": "<breakdown/>"}


def _answer(clip: str, cost: str = "0.01"):
    parsed = SimpleNamespace(model_dump=lambda: {"clips": [{"clip_id": clip}]})
    return SimpleNamespace(parsed=parsed, cost_usd=Decimal(cost))


def _provider(ask) -> ClaudeProvider:
    provider = ClaudeProvider("k", client=object())
    provider._ask = lambda input, prompt, shared="", started=None: ask(prompt)
    return provider


def test_parts_run_at_once_and_join_in_part_order():
    running, most, lock = [0], [0], threading.Lock()

    def ask(part):
        with lock:
            running[0] += 1
            most[0] = max(most[0], running[0])
        time.sleep(0.2 if part == "c1" else 0.05)  # the first part finishes last
        with lock:
            running[0] -= 1
        return _answer(part)

    parts = ["c1", "c2", "c3", "c4", "c5", "c6"]
    result = _provider(ask).run("write", INPUT | {"parts": parts})
    assert result.state == "succeeded"
    assert [c["clip_id"] for c in result.output["clips"]] == parts  # part order, not finish
    assert 1 < most[0] <= PARALLEL  # they overlap, never more than PARALLEL at once
    assert result.usage[0].cost_usd == Decimal("0.06")


def test_one_failed_part_is_listed_and_its_billed_cost_kept():
    def ask(part):
        if part == "c2":
            raise ClaudeError("cut off", cost_usd=Decimal("0.02"))
        return _answer(part)

    result = _provider(ask).run("write", INPUT | {"parts": ["c1", "c2", "c3"]})
    assert result.state == "succeeded"
    assert [c["clip_id"] for c in result.output["clips"]] == ["c1", "c3"]
    assert result.output["failed_parts"] == [{"part": 1, "error": "cut off"}]
    assert result.usage[0].cost_usd == Decimal("0.04")


def test_all_parts_failing_fails_the_job_with_their_costs():
    def ask(part):
        raise ClaudeError(f"refused {part}", cost_usd=Decimal("0.01"))

    result = _provider(ask).run("write", INPUT | {"parts": ["c1", "c2"]})
    assert result.state == "failed" and result.error == "refused c1; refused c2"
    assert result.usage[0].cost_usd == Decimal("0.02")


def test_busy_or_lost_raise_only_when_nothing_was_answered_or_billed():
    def busy(part):
        raise NotStarted("busy")

    with pytest.raises(NotStarted):  # retried by the worker, as before
        _provider(busy).run("write", INPUT | {"parts": ["c1", "c2"]})

    def lost(part):
        raise NetworkError("dropped") if part == "c2" else NotStarted("busy")

    with pytest.raises(NetworkError):  # one might have been billed: unsure, as before
        _provider(lost).run("write", INPUT | {"parts": ["c1", "c2"]})

    def some(part):
        if part == "c2":
            raise NotStarted("busy")
        return _answer(part)

    result = _provider(some).run("write", INPUT | {"parts": ["c1", "c2"]})
    assert result.output["failed_parts"] == [{"part": 1, "error": "busy"}]


def test_the_rest_start_once_the_first_answer_begins_so_they_read_its_cache():
    """QA and the Producer: asked together, every part would write the shared prompt's
    cache. A cache is readable once its answer starts streaming (Anthropic's caching docs),
    so the rest wait only for the first part's answer to begin, never for it to finish."""
    times, lock = {}, threading.Lock()

    def ask(input, part, shared="", started=None):
        start = time.monotonic()
        time.sleep(0.05)  # reading the prompt, writing its cache
        if started:
            started()
            with lock:
                times["begun"] = time.monotonic()
        time.sleep(0.2 if part == "c1" else 0.05)  # the answer
        with lock:
            times[part] = (start, time.monotonic())
        return _answer(part)

    provider = ClaudeProvider("k", client=object())
    provider._ask = ask
    provider.run("write", INPUT | {"parts": ["c1", "c2", "c3"]})
    assert all(times[p][0] >= times["begun"] for p in ("c2", "c3"))  # after it began
    assert all(times[p][0] < times["c1"][1] for p in ("c2", "c3"))  # not after it finished


def test_a_first_part_that_fails_before_its_answer_never_holds_the_rest():
    def ask(part):
        if part == "c1":
            raise NotStarted("busy")
        return _answer(part)

    result = _provider(ask).run("write", INPUT | {"parts": ["c1", "c2"]})
    assert [c["clip_id"] for c in result.output["clips"]] == ["c2"]
