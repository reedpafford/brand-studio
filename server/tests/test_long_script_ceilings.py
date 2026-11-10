"""probe"""

import json

import pytest

from app.models.asks import Ask
from app.models.clips import ProjectClip
from app.models.freestyles import Freestyle
from app.models.jobs import Job
from app.models.projects import Project
from tests.conftest import first_brand
from tests.test_freestyle_dialogue import _run

SENTENCES = [
    "I almost lost ten thousand dollars because I trusted the wrong guard.",
    "Every night I locked the door and thought my family was safe.",
    "Then the camera showed me what happened at three in the morning.",
    "A stranger walked right up to the porch and tried the handle.",
    "The old guard never made a sound and the light never came on.",
    "So I tested the new one the same way, with my own hand on the door.",
    "It lit the porch, called my phone, and spoke before I touched the lock.",
]


def _script(words: int) -> str:
    out, n = [], 0
    while sum(len(x.split()) for x in out) < words:
        out.append(f"MARCUS: {SENTENCES[n % len(SENTENCES)]} Part {n + 1}.")
        n += 1
    return "\n".join(out)


@pytest.fixture(autouse=True)
def songs_on(monkeypatch):
    monkeypatch.setattr("app.director_song._on", lambda db, draft: True)


def test_probe(app, db, owner):
    text = _script(1000)
    body = {"type": "presenter", "look": "ugc", "shape": "9:16", "text": text,
            "brand_id": first_brand(owner)}
    r = owner.post("/freestyles", json=body)
    assert r.status_code == 201, r.text
    fs = db.get(Freestyle, r.json()["id"])
    video = db.get(Project, fs.project_id, execution_options={"see_hidden": True})
    _run(app, db, ticks=300)
    jobs = db.query(Job).filter(Job.project_id == video.id).order_by(Job.id).all()
    for j in jobs:
        print(j.id, j.kind, j.provider, j.input.get("step"), j.status, j.input.get("max_tokens"),
              len(j.input.get("prompt", "")), len(json.dumps(j.output or {})), (j.error or "")[:80], (j.output or {}).get("tool"), str(j.input.get("result"))[:200])
    print("clips", db.query(ProjectClip).filter_by(project_id=video.id).count())
    print([(a.kind, a.state) for a in db.query(Ask).filter_by(project_id=video.id)])
    last = jobs[-1]
    print("LAST", last.status, last.input.get("director_run"),
          {k: v for k, v in last.input.items() if k not in ("prompt", "system")})
