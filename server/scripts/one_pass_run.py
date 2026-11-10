"""One Dialogue video from pasted words to its delivery, on the stand-in providers, through
the real HTTP API: a real server and a real worker on a throwaway SQLite database (made by
the migrations) and a port nobody uses. Free: no keys, no paid call. Prints how long it took
and how many jobs of each kind it made, so the one-pass director (app/one_pass.py) can be read
beside the step-by-step one on the same script.

    cd server && uv run python -m scripts.one_pass_run             # the one-pass director
    cd server && uv run python -m scripts.one_pass_run --steps     # the step-by-step one
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


def run(port: int, one_pass: bool, limit: float) -> int:
    token, here = secrets.token_hex(16), Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, **dict.fromkeys(PAID_KEYS, ""),  # no key: no paid call can be made
               "BS_DATABASE_URL": f"sqlite:///{tmp}/run.db", "BS_STORAGE_DIR": f"{tmp}/files",
               "BS_FAKE_PROVIDERS": "true", "BS_COOKIE_SECURE": "false", "BS_ENV": "dev",
               "BS_SETUP_TOKEN": token, "BS_WORKER_POLL_SECONDS": "0.2",
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
                began = time.monotonic()
                sent = c.post("/freestyles", json={"type": "dialogue", "look": "house",
                                                   "shape": "9:16", "text": SCRIPT,
                                                   "brand_id": brand, "mode": "auto"})  # fmt: skip
                sent.raise_for_status()
                fs = sent.json()["id"]

                def ended():
                    now = c.get(f"/freestyles/{fs}").json()
                    return now if now["status"] not in ("working", "waiting") else None

                out = _wait(ended, limit)
                took = time.monotonic() - began
            db = sqlite3.connect(f"{tmp}/run.db")
            rows = db.execute(
                "select coalesce(json_extract(input, '$.step'), kind), provider, count(*), "
                "sum(credits) from jobs where status = 'succeeded' group by 1, 2 order by 1, 2"
            ).fetchall()
        finally:
            for child in started:  # only the two this run started
                child.terminate()
            for child in started:
                child.wait(timeout=20)
            logs.close()
    name = "one-pass" if one_pass else "step-by-step"
    status = out["status"] if out else f"still going after {limit:.0f} s"
    print(f"{name} director: {status} in {took:.1f} s ({sum(r[2] for r in rows)} jobs, "
          f"{sum(r[3] or 0 for r in rows):.1f} credits)")  # fmt: skip
    for step, provider, n, credits in rows:
        print(f"  {n:3d} x {step} ({provider}), {credits or 0:.1f} credits")
    return 0 if out and out["status"] == "delivered" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--steps", action="store_true", help="the step-by-step director")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--limit", type=float, default=300, help="seconds to wait for delivery")
    args = parser.parse_args()
    return run(args.port, not args.steps, args.limit)


if __name__ == "__main__":
    sys.exit(main())
