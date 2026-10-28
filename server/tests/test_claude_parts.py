"""A clip prompt run's parts are asked at the same time (Producer, approved by Reed): each part
only ever sees the shared prompt, so asking them together changes nothing but the wait."""

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
    provider._ask = lambda input, prompt: ask(prompt.rsplit("\n", 1)[-1])
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
