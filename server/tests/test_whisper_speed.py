"""Local Whisper on the shared server (the test site, video 240: 6 minutes for 24 s of
narration, the box at 114 MB free): the same model, read from its cache with no hub check, at
a thread count its container may use, and every run saying where its time went. No model is
loaded: faster_whisper is a stand-in."""

import json
import subprocess
import sys
import types

import pytest

from app import song_timing, whisper


@pytest.fixture
def model(monkeypatch):
    """A stand-in faster_whisper that records how it was asked to load."""
    made = []

    class Model:
        def __init__(self, size, **kwargs):
            if kwargs.get("local_files_only") and made and made[-1] == "missing":
                raise RuntimeError("not in the cache")
            made.append({"size": size, **kwargs})

        def transcribe(self, path, **kwargs):
            word = types.SimpleNamespace(word=" hi", start=0.1, end=0.4)
            seg = types.SimpleNamespace(text=" hi", start=0.1, end=0.4, words=[word],
                                        no_speech_prob=0.1, avg_logprob=-0.2)  # fmt: skip
            return iter([seg]), types.SimpleNamespace(duration=24.0)

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    return made


def test_the_same_model_is_read_from_its_cache_at_the_threads_it_may_use(model, monkeypatch):
    monkeypatch.setenv(whisper.THREADS, "2")
    loaded, cached = whisper.load()
    (asked,) = model
    same = {"size": "small", "device": "cpu", "compute_type": "int8"}  # the model, unchanged
    loads = {"cpu_threads": 2, "num_workers": 1, "local_files_only": True}
    assert cached and asked == {**same, **loads}
    model[:] = ["missing"]  # not downloaded yet: fetched once, as before
    _, cached = whisper.load()
    assert not cached and "local_files_only" not in model[-1] and model[-1]["size"] == "small"
    monkeypatch.delenv(whisper.THREADS)
    six = {0, 1, 2, 3, 4, 5}
    monkeypatch.setattr(whisper.os, "sched_getaffinity", lambda pid: six, raising=False)
    assert whisper.threads() == 4  # the CPUs it may use, at most 4
    monkeypatch.setattr(whisper.os, "sched_getaffinity", lambda pid: {0}, raising=False)
    assert whisper.threads() == 1


def test_each_read_says_how_long_the_load_and_the_read_took(model, capsys):
    whisper.main("take.mp4", words_prompt="Hi.")
    out = capsys.readouterr()
    assert json.loads(out.out) == [{"word": "hi", "start": 0.1, "end": 0.4}]
    facts = whisper.timings(out.err)
    assert set(facts) == {"load_s", "cached", "threads", "transcribe_s", "audio_s"}
    assert facts["audio_s"] == 24.0 and facts["cached"] is True
    assert whisper.timings(b'noise\n{"whisper": {"load_s": 3.1}}\n') == {"load_s": 3.1}


def test_a_timing_read_logs_where_its_time_went_even_when_it_runs_out(monkeypatch, caplog):
    caplog.set_level("INFO", logger="app.song_timing")
    monkeypatch.setattr(song_timing, "read_timeout", lambda path: 180)

    def late(args, timeout):
        raise subprocess.TimeoutExpired(args, timeout, stderr=b'{"whisper": {"load_s": 171.2}}\n')

    monkeypatch.setattr(song_timing, "_run", late)
    with pytest.raises(RuntimeError, match="took too long"):
        song_timing.words("v.mp3", "Hi.")
    assert "ran out of 180 s" in caplog.text and "'load_s': 171.2" in caplog.text  # the load

    def done(args, timeout):
        err = b'{"whisper": {"load_s": 4.0}}\n{"whisper": {"transcribe_s": 9.5, "audio_s": 24}}\n'
        return subprocess.CompletedProcess(args, 0, stdout=b"[]", stderr=err)

    monkeypatch.setattr(song_timing, "_run", done)
    assert song_timing.words("v.mp3", "Hi.") == []
    assert "'transcribe_s': 9.5" in caplog.text
