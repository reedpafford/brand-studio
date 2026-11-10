"""A deploy restarting the worker (SIGTERM) lets the job in hand finish, then stops it
(QA-Live 6: clip-prompts runs were cut off mid-answer by deploys)."""

import os
import signal
import time

from app import worker


def test_a_stop_signal_lets_each_lanes_job_in_hand_finish_then_stops(monkeypatch):
    monkeypatch.setattr(worker, "STOP", worker.threading.Event())
    monkeypatch.setattr(worker, "shares", lambda lanes: [None] * lanes)  # this process unpinned
    done, begun = [], worker.threading.Event()

    def long_job() -> None:  # a Claude call still being written when the deploy comes
        begun.wait(5)
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(0.2)
        done.append("finished")

    def listen() -> None:  # a second local lane's take listen, under way meanwhile
        begun.set()
        time.sleep(0.2)
        done.append("listened")

    try:
        worker.serve([long_job, listen], poll=0.01)
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
    assert sorted(done) == ["finished", "listened"]  # each finished once, then they stopped


def test_when_the_first_lane_dies_the_others_finish_their_job_and_stop(monkeypatch):
    """Ctrl-C, or the first lane dying: the second lane never runs on alone (QA on #1526)."""
    import pytest

    monkeypatch.setattr(worker, "STOP", worker.threading.Event())
    monkeypatch.setattr(worker, "shares", lambda lanes: [None] * lanes)
    done, begun = [], worker.threading.Event()

    def dies() -> None:
        begun.wait(5)
        raise KeyboardInterrupt

    def listen() -> None:
        begun.set()
        time.sleep(0.2)
        done.append("listened")

    try:
        with pytest.raises(KeyboardInterrupt):
            worker.serve([dies, listen], poll=0.01)
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
    assert done == ["listened"]  # its job finished once, and it stopped (serve returned)
