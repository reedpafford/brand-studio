"""A deploy restarting the worker (SIGTERM) lets the job in hand finish, then stops it
(QA-Live 6: clip-prompts runs were cut off mid-answer by deploys)."""

import os
import signal
import time

from app import worker


def test_a_stop_signal_lets_the_job_in_hand_finish_then_stops(monkeypatch):
    monkeypatch.setattr(worker, "STOP", worker.threading.Event())
    done = []

    def long_job() -> None:  # a Claude call still being written when the deploy comes
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(0.2)
        done.append("finished")

    try:
        worker.serve(long_job, poll=0.01)
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
    assert done == ["finished"]  # finished once, then the worker stopped
