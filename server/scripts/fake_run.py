"""Make the two done-test videos end to end with the stand-in providers: free, no keys.
Script Library (script, cast slots, breakdown preview, publish, produce, Assets), then
storyboard, stills, clip prompts, takes, one cut-in and the final MP4, all through the API.
Also reel import: one uploaded reel read and produced, two reel links through bulk create.
Prints what came out; exits 1 if anything went wrong.

    cd server && uv run python -m scripts.fake_run
"""

import json
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.models  # noqa: F401
from app import end_logo
from app.db import Base
from app.main import create_app
from app.models.jobs import Job, JobStatus
from app.providers import get_providers
from app.providers.fake_local import two_scenes
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
    """Through the Script Library (workflow v2): script, cast slots locked to sheets, the
    breakdown preview, approve, variations, publish, produce, Assets; then the usual
    project steps."""
    print(f"\n{case['id']} ({planned} s planned)")
    brand_id = next(b["id"] for b in c.get("/brands").json() if b["name"].lower().startswith(brand))
    reel = Path(case["reference"]["path"]).parent.name if case.get("reference") else None
    body = {"brand_id": brand_id, "title": case["id"], "text": script, "reference_id": reel}
    lib = f"/scripts/{ok(c.post('/scripts', json=body), 'script')['id']}"
    ok(c.put(f"{lib}/drafts/0", json={"text": script, "target_seconds": planned}), "target")
    for x in case["cast"]:
        item = library(c, work, "character", x)
        slot = ok(c.post(f"{lib}/cast", json={"role": x.split(" ", 1)[1][:60]}), "slot")[-1]
        ok(c.post(f"{lib}/cast/{slot['id']}/lock", json={"library_item_id": item}), "lock")
    for x in case["places"]:
        library(c, work, "place", x)
    ok(c.post(f"{lib}/drafts/0/breakdown"), "breakdown preview")
    work()
    preview = c.get(f"{lib}/drafts/0/breakdown").json()
    problems.extend(f"breakdown: {p}" for p in preview["problems"] if not p.startswith("Advice: "))
    ok(c.post(f"{lib}/drafts/0/approve"), "approve")
    ok(c.post(f"{lib}/variations", json={}), "variations")
    work()
    if len(c.get(lib).json()["versions"]) != 3:
        problems.append("variations: two weren't written")
    for slot in (1, 2):  # this run produces the original only
        ok(c.delete(f"{lib}/drafts/{slot}"), f"remove variation {slot}")
    # The cast read after variations adds slots by speaker name; the stand-in can't match
    # them to the locked roles, so drop the unlocked ones it added (Assets would fill them).
    for slot in c.get(lib).json()["cast"]:
        if not slot["locked"]:
            ok(c.delete(f"{lib}/cast/{slot['id']}"), "remove a read slot")
    ok(c.post(f"{lib}/publish"), "publish")
    made = ok(c.post(f"{lib}/drafts/0/produce"), "produce")
    if made.get("breakdown_job_id") is not None:
        problems.append("produce ran a new breakdown instead of using the saved one")
    base = f"/projects/{made['project_id']}"
    ok(c.patch(base, json={"product_variants": variants or {}}), "brief")
    waiting = [a["role"] for a in c.get(f"{base}/assets").json() if not a["ready"]]
    problems.extend(f"assets: {role} isn't ready" for role in waiting)
    bd = c.get(f"{base}/breakdown").json()
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
        card = end_logo.CARD_SECONDS if video["end_logo"] == "end_card" else 0
        print(f"  ends on the logo: {video['end_logo']}")
        if abs(float(length) - sum(seconds) - card) > 1:
            problems.append(f"video is {length} s, clips add up to {sum(seconds)} s (+{card})")


def write_all(c, work) -> None:
    """Bulk create two scripts from titles, then Write all (stand-in Claude writes the words)."""
    print("\nwrite all")
    brand_id = c.get("/brands").json()[0]["id"]
    rows = [{"brand_id": brand_id, "title": f"Idea {n}", "description": "Mom finds the wallet"}
            for n in (1, 2)]  # fmt: skip
    ids = [s["id"] for s in ok(c.post("/scripts/bulk", json={"scripts": rows}), "bulk create")]
    price = ok(c.post("/scripts/write/estimate", json={"script_ids": ids}), "estimate")
    print(f"  {price['count']} scripts, {price['credits']:.0f} credits")
    ok(c.post("/scripts/write", json={"script_ids": ids}), "write all")
    work()
    for script_id in ids:
        if not c.get(f"/scripts/{script_id}").json()["versions"][0]["text"].strip():
            problems.append(f"write all: script {script_id} has no words")
        ok(c.delete(f"/scripts/{script_id}"), "remove")


def _upload(c, url: str, video: Path, **form) -> dict:
    with video.open("rb") as f:
        return ok(c.post(url, data=form, files={"file": ("reel.mp4", f, "video/mp4")}), url)


def import_reel(c, work, video: Path) -> None:
    """Reel import: upload a two-scene reel (free prep), read it at one price (stand-in
    Gemini and Claude), approve and publish version A, and produce it once with its reel."""
    print("\nreel import")
    brand_id = c.get("/brands").json()[0]["id"]
    sid = _upload(c, "/scripts/import/upload", video, brand_id=brand_id)["script_id"]
    work()
    ready = c.get(f"/scripts/{sid}/import").json()
    if ready["status"] != "ready" or ready["shots"] != 2:
        problems.append(f"reel import: prep gave {ready['status']}, {ready['shots']} shots")
        return
    credits = ready["estimate"]["credits"]
    print(f"  {ready['seconds']:.0f} s, {ready['shots']} shots, {credits:.0f} credits")
    ok(c.post(f"/scripts/{sid}/import/read"), "read the reel")
    work()
    if (done := c.get(f"/scripts/{sid}/import").json())["status"] != "done":
        problems.append(f"reel import: read ended {done['status']} at {done['failed_step']}")
        return
    script = c.get(f"/scripts/{sid}").json()
    version = script["versions"][0]
    problems.extend(f"reel import: {p}" for p in version["problems"])
    if not script["cast"]:
        problems.append("reel import: cast read filled no slots")
    ok(c.post(f"/scripts/{sid}/drafts/0/approve"), "approve")
    ok(c.post(f"/scripts/{sid}/publish"), "publish")
    made = ok(c.post(f"/scripts/{sid}/drafts/0/produce"), "produce")
    ref = c.get(f"/projects/{made['project_id']}").json()["reference_breakdown"] or {}
    if len(ref.get("shots", [])) != 2:
        problems.append("reel import: the project didn't get the reel's breakdown")


def bulk_reels(c, work, video: Path) -> None:
    """Two reel links in bulk create; local runs can't reach Instagram, so each says to upload
    the video, gets it, and Write all reads both at one total."""
    print("\nbulk reel links")
    brand_id = c.get("/brands").json()[0]["id"]
    rows = [{"brand_id": brand_id, "reel_url": f"https://www.instagram.com/reel/Local{n}x/"}
            for n in (1, 2)]  # fmt: skip
    ids = [s["id"] for s in ok(c.post("/scripts/bulk", json={"scripts": rows}), "bulk links")]
    work()
    for sid in ids:
        if c.get(f"/scripts/{sid}/import").json()["problem_code"] != "blocked":
            problems.append(f"bulk reel links: script {sid} wasn't refused locally")
        _upload(c, f"/scripts/{sid}/import/upload", video)
        work()
    price = ok(c.post("/scripts/write/estimate", json={"script_ids": ids}), "estimate")
    print(f"  read {price['reading']} reels, {price['credits']:.0f} credits")
    ok(c.post("/scripts/write", json={"script_ids": ids}), "write all reels")
    work()
    for sid in ids:
        if c.get(f"/scripts/{sid}/import").json()["status"] != "done":
            problems.append(f"bulk reel links: script {sid} wasn't read")


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
        providers = get_providers(settings, app.state.storage)
        with TestClient(app) as c:
            owner = {"setup_token": token, "workspace_name": "Studio", "name": "Reed",
                     "email": "reed@example.com", "password": "correct horse battery"}  # fmt: skip
            ok(c.post("/auth/setup", json=owner), "setup")
            write_all(c, lambda: drain(app, providers))
            video = two_scenes(Path(tmp) / "reel.mp4")
            import_reel(c, lambda: drain(app, providers), video)
            bulk_reels(c, lambda: drain(app, providers), video)
            pb = CASES["ironpaws-pitbull-1"]
            make(c, lambda: drain(app, providers), "iron", pb, "\n".join(pb["script"]), 160,
                 {"bag": "Peanut butter"})  # fmt: skip
            altar = CASES["fomo-adapt-altar"]
            make(c, lambda: drain(app, providers), "fomo", altar, altar_script(), 50)
    print("\n" + ("\n".join(f"PROBLEM {p}" for p in problems) or "All good."))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
