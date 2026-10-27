"""Clip prompts always finish (stabilization, 2026-10-27, "Mom gave him three days"): every
clip of a long video in one answer ran out of room and failed the whole run. Now Claude is
asked a few clips at a time in one job (one price), a clip whose answer still runs out gets a
free "Fix this clip's prompt", and a run that fails says why. Mocked: no paid calls."""

import copy
import json
import re

import httpx2 as httpx

from app.credits import usd_to_credits
from app.models.jobs import Job, Usage
from tests.helpers import claude_stream
from tests.test_breakdown import BREAKDOWN, _shot
from tests.test_enhance import FakeClaude, _run, setup  # noqa: F401 - fixture

AUDIO = "Audio: no one speaks, only room sound. No music. No subtitles."


def _long_breakdown() -> dict:
    """c1 the opening exchange, c2 a 12-shot trading montage, c3 and c4 one shot each."""
    bd = copy.deepcopy(BREAKDOWN)
    montage = [_shot(f"2.{i}", [], None, None, 1) for i in range(1, 13)]
    end = [_shot("3.1", [], None, None, 4), _shot("3.2", [], None, None, 4)]
    bd["scenes"] += [
        {"id": 2, "heading": "MONTAGE — NIGHTS", "look": "Phone glow.", "shots": montage},
        {"id": 3, "heading": "EXT. STREET — DAY", "look": "Sun.", "shots": end},
    ]
    bd["clips"] += [
        {"id": "c2", "shot_ids": [s["id"] for s in montage], "seconds": 12, "seam": "Cut."},
        {"id": "c3", "shot_ids": ["3.1"], "seconds": 4, "seam": "Cut."},
        {"id": "c4", "shot_ids": ["3.2"], "seconds": 4, "seam": "end"},
    ]
    return bd


def _clip(clip_id: str) -> dict:
    prompt = f"{AUDIO}\nSummary: clip {clip_id}.\nShots (hard cuts):\nShot 1 | 0-4 s.\n{AUDIO}"
    return {"clip_id": clip_id, "seconds": 4, "references": [], "prompt": prompt}


class Writer:
    """Answers each part with the clips it asks for; `cut` clips run out of room."""

    def __init__(self, cut: set[str]):
        self.cut, self.asked = cut, []

    def __call__(self, request):
        prompt = json.loads(request.content)["messages"][0]["content"]
        asked = re.findall(r'<write clips="([^"]+)">', prompt)  # none: every clip at once
        ids = asked[-1].split(", ") if asked else re.findall(r'"id": "(c\d+)"', prompt)
        self.asked.append(ids)
        if self.cut & set(ids):  # the answer stops mid-way: max_tokens
            body = claude_stream('{"clips": [{"clip_id": "c2", "prom', "max_tokens")
        else:
            body = claude_stream(json.dumps({"clips": [_clip(i) for i in ids]}))
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})


def test_a_long_video_finishes_and_the_clip_that_ran_out_gets_a_free_fix(app, db, editor, setup):  # noqa: E501, F811
    base = f"/projects/{setup['project']}"
    editor.post(f"{base}/breakdown")
    _run(app, db, FakeClaude(_long_breakdown()))
    price = editor.get(f"{base}/clips/prompts/price").json()["credits"]
    job = editor.post(f"{base}/clips/prompts").json()
    shown = job["credits"]
    assert price == shown == 9  # 3 credits a Claude call, 3 calls (QA-Live 6: undercharged)

    writer = Writer(cut={"c2"})
    _run(app, db, writer)
    assert writer.asked == [["c1"], ["c2"], ["c3", "c4"]]  # the montage gets a call of its own
    done = db.get(Job, job["id"])
    spent = sum(u.cost_usd for u in db.query(Usage).filter_by(job_id=job["id"]))
    assert done.status == "succeeded" and done.credits == usd_to_credits(spent)  # what it cost
    clips = {c["clip_id"]: c for c in editor.get(f"{base}/clips").json()}
    assert [k for k, c in clips.items() if c["prompt"]] == ["c1", "c3", "c4"]
    assert clips["c2"]["problems"] == [
        "This clip's prompt wasn't written: the answer ran out of room before it was finished."
    ]
    assert editor.post(f"{base}/clips/{clips['c2']['id']}/generate").status_code == 409

    fix = editor.post(f"{base}/clips/{clips['c2']['id']}/fix").json()
    assert fix["job"]["credits"] == 0  # free
    writer.cut = set()
    _run(app, db, writer)
    assert writer.asked[-1] == ["c2"]
    db.expire_all()
    c2 = next(c for c in editor.get(f"{base}/clips").json() if c["clip_id"] == "c2")
    assert "Summary: clip c2." in c2["prompt"] and not any(
        p.startswith("This clip's prompt wasn't written") for p in c2["problems"]
    )


def test_a_failed_run_names_its_cause(app, db, editor, setup, caplog):  # noqa: F811
    base = f"/projects/{setup['project']}"
    editor.post(f"{base}/breakdown")
    _run(app, db, FakeClaude(BREAKDOWN))
    job = editor.post(f"{base}/clips/prompts").json()
    _run(app, db, Writer(cut={"c1"}))
    seen = next(j for j in editor.get("/jobs").json() if j["id"] == job["id"])
    assert seen["status"] == "failed"
    assert seen["error"] == (
        "The answer ran out of room before it was finished. Nothing was charged; try again."
    )
    assert "clip prompts didn't finish: the answer ran out of room" in caplog.text
