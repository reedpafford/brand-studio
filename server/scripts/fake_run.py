"""Make the two done-test videos end to end with the stand-in providers: free, no keys.
Sheets, brief, script, breakdown, storyboard, stills, clip prompts, takes, one cut-in, the
final MP4, all through the API. Prints what came out; exits 1 if anything went wrong.

    cd server && uv run python -m scripts.fake_run
"""

import json
import secrets
import subprocess
import sys
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.models  # noqa: F401
from app.db import Base
from app.main import create_app
from app.models.jobs import Job, JobStatus
from app.providers import get_providers
from app.settings import REPO_ROOT, Settings
from app.worker import run_once

CASES = {
    c["id"]: c for c in json.loads((REPO_ROOT / "server/evals/cases.json").read_text())["cases"]
}
REFERENCE = REPO_ROOT / "docs/references/fomo-DehudnaAmce/BREAKDOWN.json"
problems: list[str] = []


def ok(r, what: str):
    if r.status_code >= 300:
        problems.append(f"{what}: {r.status_code} {r.text[:200]}")
    return r.json() if r.content else None


def drain(app, providers) -> None:
    with app.state.sessionmaker() as db:
        for _ in range(50):
            run_once(db, providers, app.state.storage)
            busy = (JobStatus.queued, JobStatus.running)
            if not db.scalars(select(Job).where(Job.status.in_(busy))).first():
                break
        for job in db.scalars(select(Job).where(Job.status != JobStatus.succeeded)):
            problems.append(f"job {job.id} ({job.input.get('step')}): {job.status}")


def library(c, work, kind: str, text: str) -> int:
    label = text.split(" ", 1)[1]  # "char:1 Bruno, the pitbull" -> "Bruno, the pitbull"
    item = ok(c.post(f"/library/{kind}", json={"name": label[:60], "notes": label}), kind)
    ok(c.post(f"/library/{kind}/{item['id']}/sheet", json={}), "sheet")
    work()
    ok(c.post(f"/library/{kind}/{item['id']}/sheet/approve"), "approve sheet")
    return item["id"]


def make(c, work, brand: str, case: dict, script: str, planned: int, variants=None) -> None:
    print(f"\n{case['id']} ({planned} s planned)")
    brand_id = next(b["id"] for b in c.get("/brands").json() if b["name"].lower().startswith(brand))
    cast = [library(c, work, "character", x) for x in case["cast"]]
    for x in case["places"]:
        library(c, work, "place", x)
    body = {"brand_id": brand_id, "name": case["id"], "planned_seconds": planned}
    base = f"/projects/{ok(c.post('/projects', json=body), 'project')['id']}"
    ok(c.patch(base, json={"cast_ids": cast, "product_variants": variants or {}}), "brief")
    ok(c.put(f"{base}/script", json={"text": script}), "script")
    ok(c.post(f"{base}/breakdown"), "breakdown")
    work()
    bd = c.get(f"{base}/breakdown").json()
    problems.extend(f"breakdown: {p}" for p in bd["problems"])
    seconds = [x["seconds"] for x in bd["breakdown"]["clips"]]
    print(f"  {len(seconds)} clips {seconds} = {sum(seconds)} s")
    ok(c.post(f"{base}/storyboard", json={"per_shot": False}), "storyboard")
    work()
    for f in c.get(f"{base}/storyboard").json():
        ok(c.post(f"{base}/storyboard/frames/{f['id']}/render"), f"still {f['clip_id']}")
    work()
    for f in c.get(f"{base}/storyboard").json():
        ok(c.post(f"{base}/storyboard/frames/{f['id']}/approve"), f"approve {f['clip_id']}")
    ok(c.post(f"{base}/clips/prompts"), "clip prompts")
    work()
    for clip in c.get(f"{base}/clips").json():
        problems.extend(f"clip {clip['clip_id']}: {p}" for p in clip["problems"])
        ok(c.post(f"{base}/clips/{clip['id']}/generate"), f"take {clip['clip_id']}")
        work()
        ok(c.post(f"{base}/clips/{clip['id']}/approve"), f"approve {clip['clip_id']}")
    inserts = [(x, i) for x in c.get(f"{base}/clips").json() for i in x.get("inserts", [])]
    if inserts:
        (clip, insert) = inserts[0]
        url = f"{base}/clips/{clip['id']}/inserts/{insert['shot_id']}"
        ok(c.put(url, json={"use_real_image": True}), "cut-in")
    video = ok(c.post(f"{base}/video"), "video")
    project = c.get(base).json()
    used, budget = project["credits_used"], project["budget_credits"]
    print(f"  {len(inserts)} insert(s); credits {used} of {budget}")
    if video and "file_id" in video:
        data = c.get(f"/files/{video['file_id']}").content
        probe = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            "-",
        ]
        done = subprocess.run(probe, input=data, capture_output=True)  # noqa: S603
        length = done.stdout.decode().strip()
        print(f"  final video: {float(length):.1f} s, {len(data) / 1e6:.1f} MB")
        if abs(float(length) - sum(seconds)) > 1:
            problems.append(f"video is {length} s, clips add up to {sum(seconds)} s")


def altar_script() -> str:
    """The reference reel's lines word for word, one ★ screen line, then fomo's end line."""
    lines = json.loads(REFERENCE.read_text())["lines"]
    said = [f"{x['speaker'].split()[0].upper()}: {x['text']}" for x in lines]
    return "\n".join([
        "SCENE 1 — EXT. FLORAL ALTAR BY THE OCEAN — DAY", *said[:6],
        "SCENE 2 — INT. NATE'S BEDROOM — NIGHT", "★ fomo screen: Token chart up — fills the frame",
        *said[6:], "NATE: Want to trade like me? Download fomo through the link in my bio.",
    ])  # fmt: skip


def main() -> int:
    token = secrets.token_hex(16)  # first-owner setup for this throwaway database only
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            database_url=f"sqlite:///{tmp}/run.db",
            storage_dir=f"{tmp}/files",
            cookie_secure=False,
            setup_token=token,
            fake_providers=True,
            generation_enabled=False,
        )
        app = create_app(settings)
        Base.metadata.create_all(app.state.sessionmaker.kw["bind"])
        providers = get_providers(settings)
        with TestClient(app) as c:
            owner = {"setup_token": token, "workspace_name": "Studio", "name": "Reed",
                     "email": "reed@example.com", "password": "correct horse battery"}  # fmt: skip
            ok(c.post("/auth/setup", json=owner), "setup")
            pb = CASES["ironpaws-pitbull-1"]
            make(c, lambda: drain(app, providers), "iron", pb, "\n".join(pb["script"]), 160,
                 {"bag": "Peanut butter"})  # fmt: skip
            altar = CASES["fomo-adapt-altar"]
            make(c, lambda: drain(app, providers), "fomo", altar, altar_script(), 50)
    print("\n" + ("\n".join(f"PROBLEM {p}" for p in problems) or "All good."))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
