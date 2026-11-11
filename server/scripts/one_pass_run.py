"""One video per engine from pasted words to its delivery, on the stand-in providers, through
the real HTTP API: a real server and a real worker on a throwaway SQLite database (made by
the migrations) and a port nobody uses. Free: no keys, no paid call. Prints, for each engine,
whether it delivered, how long it took, its jobs by kind, its Claude calls and its credits,
so the one-pass director (app/one_pass.py) can be read beside the step-by-step one.

    cd server && uv run python -m scripts.one_pass_run                  # every engine
    cd server && uv run python -m scripts.one_pass_run --only song      # one of them
    cd server && uv run python -m scripts.one_pass_run --steps          # the step-by-step director
"""

import argparse
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx2 as httpx

SCRIPT = """INT. KITCHEN - NIGHT
MIA: You sold the car without asking me.
LEO: I sold it to pay our rent.
MIA: Then where did the money go, Leo?
INT. GARAGE - NIGHT
LEO: Into this. Look at the balance.
MIA: That can't be right.
EXT. STREET - DAY
MIA: Fine. Show me how you did it."""
NARRATION = """Every morning starts the same. You pour the coffee and open the app.
The numbers are up again, and you did nothing.
So you tell a friend. Then you tell another.
Get it today."""
LYRICS = """[Verse]
Woke up late and the bowl was bare
Shook the bag, there was nothing there
[Chorus] [Lip-sync]
Fill it up, fill it up again
Fill it up for my four-legged friend
[Verse]
Now he waits by the kitchen door
Tail goes thump on the wooden floor"""
STYLE = "bright pop, warm female vocal, 110 bpm"
# Each engine: its name here, then what New video sends (the type is a format, the look a
# style) and, for a presenter, how they appear (set on the video before its plan is made).
# The corner host is House's, not Dr. Pickle's: his cloned voice reads as unused for 7 days on
# a database made today, so his run would stop to have it cloned again (app/voices.py).
ENGINES = {
    "dialogue": {"type": "dialogue", "look": "house", "text": SCRIPT},
    "narrated": {"type": "narrated", "look": "house", "text": NARRATION},
    "presenter corner": {"type": "presenter", "look": "house", "text": NARRATION},
    "presenter talker": {"type": "presenter", "look": "house", "text": NARRATION,
                         "presenter": "talks"},
    "ugc on omni": {"type": "presenter", "look": "ugc", "text": NARRATION},
    "zack-d": {"type": "zack-d", "look": "zack-d", "text": NARRATION},
    "song": {"type": "song", "look": "house", "text": LYRICS},
}  # fmt: skip
PAID_KEYS = ("STUDIO_ANTHROPIC_KEY", "REPLICATE_API_TOKEN", "KIE_API_KEY", "HEYGEN_API_KEY")


def _wait(what, seconds: float, every: float = 0.5):
    """Poll `what` until it returns something, or give up (None)."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if (found := what()) is not None:
            return found
        time.sleep(every)
    return None


def _up(base: str) -> bool | None:
    try:
        return True if httpx.get(f"{base}/health", timeout=2).status_code == 200 else None
    except httpx.HTTPError:
        return None


def _answer(c: httpx.Client, video: int) -> None:
    """What only a person can answer, answered as one would: the presenter's voice once every
    candidate has read (the first of them), and a song's style."""
    for ask in c.get(f"/projects/{video}/asks").json():
        if ask["state"] not in ("open", "ready"):
            continue
        heard = ask.get("audition") or []
        if heard and not ask.get("voice") and all(v["sample_file_id"] for v in heard):
            c.post(f"/asks/{ask['id']}/answer", json={"how": "voice", "option": heard[0]["id"]})
        elif ask["kind"] == "question" and "reply" in ask["can"]:
            c.post(f"/asks/{ask['id']}/answer", json={"how": "reply", "text": STYLE})


def _make(c: httpx.Client, brand: int, send: dict, limit: float) -> tuple[dict | None, int | None]:
    """Send one video and wait for it to end: (its freestyle as it ended, its video)."""
    send = dict(send)
    how = send.pop("presenter", None)
    sent = c.post("/freestyles", json={**send, "shape": "9:16", "brand_id": brand,
                                       "mode": "auto"})  # fmt: skip
    if sent.status_code != 201:
        return {"status": f"refused: {sent.json().get('detail')}"}, None
    fs = sent.json()["id"]
    video = _wait(lambda: c.get(f"/freestyles/{fs}").json().get("project_id"), 30)
    if how and video:
        c.post(f"/projects/{video}/settings", json={"presenter": how}).raise_for_status()

    def ended():
        if video:
            _answer(c, video)
        now = c.get(f"/freestyles/{fs}").json()
        return now if now["status"] not in ("working", "waiting") else None

    return _wait(ended, limit), video


def run(port: int, one_pass: bool, limit: float, only: list[str]) -> int:
    token, here = secrets.token_hex(16), Path(__file__).resolve().parents[1]
    names = [n for n in ENGINES if not only or n in only]
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, **dict.fromkeys(PAID_KEYS, ""),  # no key: no paid call can be made
               "BS_DATABASE_URL": f"sqlite:///{tmp}/run.db", "BS_STORAGE_DIR": f"{tmp}/files",
               "BS_FAKE_PROVIDERS": "true", "BS_COOKIE_SECURE": "false", "BS_ENV": "dev",
               "BS_SETUP_TOKEN": token, "BS_WORKER_POLL_SECONDS": "0.2",
               "BS_KIE_SUNO": "true",  # the Song format on: with no key, its stand-in sings
               "BS_ONE_PASS": "true" if one_pass else "false"}  # fmt: skip
        py = [sys.executable, "-m"]
        migrate = [*py, "alembic", "upgrade", "head"]
        subprocess.run(migrate, cwd=here, env=env, check=True, capture_output=True)  # noqa: S603
        logs = open(f"{tmp}/server.log", "w")  # noqa: SIM115 - closed with the folder
        base = f"http://127.0.0.1:{port}"
        serve = [*py, "uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1",
                 "--port", str(port)]  # fmt: skip
        started = [subprocess.Popen(cmd, cwd=here, env=env, stdout=logs, stderr=logs)  # noqa: S603
                   for cmd in (serve, [*py, "app.worker"])]  # fmt: skip
        made: dict[str, tuple] = {}
        try:
            if not _wait(lambda: _up(base), 30):
                print(f"The server didn't start on port {port}.")
                return 1
            with httpx.Client(base_url=base, timeout=60) as c:
                owner = {
                    "setup_token": token,
                    "workspace_name": "Studio",
                    "name": "Reed",
                    "email": "reed@example.com",
                    "password": secrets.token_hex(12),
                }
                c.post("/auth/setup", json=owner).raise_for_status()
                brand = c.get("/brands").json()[0]["id"]
                for name in names:
                    began = time.monotonic()
                    out, video = _make(c, brand, ENGINES[name], limit)
                    made[name] = (out, video, time.monotonic() - began)
            db = sqlite3.connect(f"{tmp}/run.db")
            rows = db.execute(
                "select project_id, coalesce(json_extract(input, '$.step'), kind), provider, "
                "count(*), sum(credits) from jobs where status = 'succeeded' group by 1, 2, 3 "
                "order by 1, 2, 3"
            ).fetchall()
        finally:
            for child in started:  # only the two this run started
                child.terminate()
            for child in started:
                child.wait(timeout=20)
            logs.close()
    director = "one-pass" if one_pass else "step-by-step"
    print(f"{director} director, one video an engine, on the stand-ins:")
    for name, (out, video, took) in made.items():
        mine = [r for r in rows if video and r[0] == video]
        calls = sum(r[3] for r in mine if r[2] == "claude")
        status = out["status"] if out else f"still going after {limit:.0f} s"
        if out and out["status"] not in ("delivered",) and out.get("thread"):
            status += f" ({out['thread'][-1]['text'][:300]})"  # why, in its own words
        print(f"\n{name}: {status} in {took:.1f} s ({sum(r[3] for r in mine)} jobs, {calls} "
              f"Claude calls, {sum(r[4] or 0 for r in mine):.1f} credits)")  # fmt: skip
        for _, step, provider, n, credits in mine:
            print(f"  {n:3d} x {step} ({provider}), {credits or 0:.1f} credits")
    done = [n for n, (out, _, _) in made.items() if out and out["status"] == "delivered"]
    print(f"\n{len(done)} of {len(made)} delivered.")
    return 0 if len(done) == len(made) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--steps", action="store_true", help="the step-by-step director")
    parser.add_argument("--only", action="append", default=[], choices=list(ENGINES),
                        help="one engine (repeat for more); none: every engine")  # fmt: skip
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--limit", type=float, default=300, help="seconds to wait for a delivery")
    args = parser.parse_args()
    return run(args.port, not args.steps, args.limit, args.only)


if __name__ == "__main__":
    sys.exit(main())
