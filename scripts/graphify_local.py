"""Optional, local code navigation. Never replaces specifications or source review."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

VERSION = "0.9.102"
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".context" / "graphify-local"
ENV = STATE / "venv"
CODE_ROOTS = ("server/app/", "server/tests/", "web/src/", "web/e2e/")
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".sql"}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def inputs():
    """Include current tracked and unignored code, never follow source symlinks."""
    paths = git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    result = {}
    for raw in paths.split(b"\0"):
        if not raw:
            continue
        name = os.fsdecode(raw)
        path = ROOT / name
        if not name.startswith(CODE_ROOTS) or path.suffix not in SUFFIXES:
            continue
        if path.name == "schema.d.ts" or not path.is_file() or path.is_symlink():
            continue
        if not path.resolve().is_relative_to(ROOT):
            continue
        result[name] = path.read_bytes()
    return dict(sorted(result.items()))


def signature(files):
    digest = hashlib.sha256()
    for name, data in files.items():
        digest.update(name.encode() + b"\0" + hashlib.sha256(data).digest())
    return {
        "root": str(ROOT),
        "head": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD").decode().strip(),
        "sha256": digest.hexdigest(),
        "version": VERSION,
    }


def run_graphify(*args, capture=False):
    executable = ENV / "bin" / "graphify"
    if not executable.exists():
        raise SystemExit("Run: python3 scripts/graphify_local.py setup")
    env = os.environ.copy()
    env["GRAPHIFY_BACKEND"] = "none"
    return subprocess.run(
        [str(executable), *map(str, args)], cwd=STATE, env=env,
        capture_output=capture, text=True,
    )


def setup():
    STATE.mkdir(parents=True, exist_ok=True)
    if not (ENV / "bin" / "python").exists():
        venv.create(ENV, with_pip=True)
    subprocess.run(
        [str(ENV / "bin" / "python"), "-m", "pip", "install", f"graphifyy=={VERSION}"],
        check=True,
    )


def build():
    STATE.mkdir(parents=True, exist_ok=True)
    files = inputs()
    stamp = signature(files)
    folder = Path(tempfile.mkdtemp(prefix="build-", dir=STATE))
    source = folder / "source"
    for name, data in files.items():
        dest = source / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    result = run_graphify(
        "extract", source, "--code-only", "--no-cluster", "--max-workers", "2",
        "--out", folder / "index",
    )
    if result.returncode:
        raise SystemExit(result.returncode)
    graph = folder / "index" / "graphify-out" / "graph.json"
    if not graph.is_file():
        raise SystemExit("No graph produced; keep using ordinary search.")
    if signature(inputs()) != stamp:
        raise SystemExit("Source changed during indexing; rebuild before querying.")
    stamp["graph"] = str(graph)
    temp = STATE / "manifest.tmp"
    temp.write_text(json.dumps(stamp, indent=2) + "\n")
    temp.replace(STATE / "manifest.json")
    print(f"Indexed {len(files)} source files. Source locations are relative to {ROOT}.")


def query(question, budget):
    manifest = STATE / "manifest.json"
    if not manifest.exists():
        raise SystemExit("Run: python3 scripts/graphify_local.py build")
    stamp = json.loads(manifest.read_text())
    current = signature(inputs())
    if any(stamp.get(key) != value for key, value in current.items()):
        raise SystemExit("Graph is stale for this workspace. Rebuild or use ordinary search.")
    print("Navigation hints only: read the cited source and applicable specs.", flush=True)
    result = run_graphify(
        "query", question, "--budget", budget, "--depth", "1", "--graph", stamp["graph"],
        capture=True,
    )
    output = result.stdout + result.stderr
    limit = budget * 4
    if len(output) > limit:
        print(output[:limit].rsplit("\n", 1)[0])
        print("[LOCAL OUTPUT LIMIT] More results omitted. Narrow the question or use source search.")
    else:
        print(output, end="")
    raise SystemExit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup")
    commands.add_parser("build")
    q = commands.add_parser("query")
    q.add_argument("question")
    q.add_argument("--budget", type=int, default=1200, choices=range(200, 4001), metavar="200..4000")
    args = parser.parse_args()
    if args.command == "setup":
        setup()
    elif args.command == "build":
        build()
    else:
        query(args.question, args.budget)


if __name__ == "__main__":
    main()
