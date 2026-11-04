"""Study one example ad, free and local: fetch it (or copy a file), find its shot cuts, grab
one frame per shot plus a contact sheet and labelled frame grids, transcribe it word by word
with the local faster-whisper, and measure its sound (loudness, silences, whether a bed of
sound runs under the gaps between lines). Everything lands in a scratch folder outside git,
`server/.study/<name>/`, ready for a model (you, in a session) to read and write
`app/guides/<target>/examples/<name>/study.md` from (template: app/guides/EXAMPLES.md).
No paid calls: the app's Gemini reel-read is not used.

    cd server && uv run --group reel python -m scripts.study_example <url-or-file> \\
        formats/dialogue altar-rejection
"""

import json
import re
import shutil
import sys
from pathlib import Path

from app.reel import _run, contact_sheet, cuts, fetch, frame_grids, probe, transcribe

SCRATCH = Path(__file__).resolve().parents[1] / ".study"
TARGET = re.compile(r"(formats|styles)/[a-z0-9-]+")
NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
MAX_SECONDS = 180  # examples can run longer than an imported reel
SILENCE_DB, SILENCE_S = -35, 0.4  # what counts as silence (as the altar breakdown used)
BED_DB = -45  # a gap between lines louder than this has sound under it (music or effects)


def shot_rows(cut_times: list[float], seconds: float) -> list[dict]:
    """The shot list: number, start, end and length of each shot, from the cut times."""
    edges = [0.0, *sorted(t for t in cut_times if 0 < t < seconds), seconds]
    spans = [(a, b) for a, b in zip(edges, edges[1:], strict=False) if b > a]
    return [
        {"n": n, "start": round(a, 2), "end": round(b, 2), "dur": round(b - a, 2)}
        for n, (a, b) in enumerate(spans, 1)
    ]


def pacing(rows: list[dict], seconds: float) -> dict:
    """Cuts per 10 s, the longest and shortest hold, how many shots are under a second."""
    if not rows:
        return {}
    durs = sorted(r["dur"] for r in rows)
    longest = max(rows, key=lambda r: r["dur"])
    shortest = min(rows, key=lambda r: r["dur"])
    return {
        "shots": len(rows),
        "cuts_per_10s": round((len(rows) - 1) / seconds * 10, 1) if seconds else 0,
        "median_shot": durs[len(durs) // 2],
        "longest": {"shot": longest["n"], "dur": longest["dur"]},
        "shortest": {"shot": shortest["n"], "dur": shortest["dur"]},
        "under_1s": sum(d < 1 for d in durs),
    }


def lines_in(row: dict, transcript: list[dict]) -> str:
    """The words spoken during a shot (any word that starts inside it), else ""."""
    words = [w for line in transcript for w in line.get("words") or []]
    if not words:  # no word timings: whole lines that start in the shot
        return " ".join(t["text"] for t in transcript if row["start"] <= t["start"] < row["end"])
    return " ".join(w["word"] for w in words if row["start"] <= w["start"] < row["end"])


def shot_table(rows: list[dict], transcript: list[dict]) -> str:
    """A markdown shot table to start the study from. Measured columns are filled; the ones
    a watcher must fill (shot size, camera, what happens, cut type) are left as `?`."""
    head = "| # | Time | Hold | Frame | Shot size | Camera | What happens | Line | Cut |"
    out = [head, "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        line = lines_in(r, transcript).replace("|", "/")
        frame = f"shot{r['n'] - 1}.jpg"
        out.append(
            f"| {r['n']} | {r['start']:.2f}-{r['end']:.2f} | {r['dur']:.2f} | {frame} "
            f"| ? | ? | ? | {line} | ? |"
        )
    return "\n".join(out) + "\n"


def silences(ffmpeg_log: str) -> list[list[float]]:
    """[start, end] of each silence ffmpeg's silencedetect reported."""
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", ffmpeg_log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", ffmpeg_log)]
    return [[round(max(a, 0), 2), round(b, 2)] for a, b in zip(starts, ends, strict=False)]


def loudness(ffmpeg_log: str) -> float | None:
    """Integrated loudness (LUFS) from ffmpeg's ebur128 summary."""
    found = re.findall(r"I:\s+(-?[\d.]+) LUFS", ffmpeg_log)
    return float(found[-1]) if found else None


def gaps(transcript: list[dict], seconds: float, least: float = 1.0) -> list[list[float]]:
    """Stretches with no speech at least `least` s long: where music or effects show."""
    edges = [0.0]
    for t in sorted(transcript, key=lambda t: t["start"]):
        edges += [t["start"], t["end"]]
    edges.append(seconds)
    pairs = zip(edges[::2], edges[1::2], strict=False)
    return [[round(a, 2), round(b, 2)] for a, b in pairs if b - a >= least]


def _mean_db(path: Path, start: float, end: float) -> float | None:
    af = f"atrim={start}:{end},volumedetect"
    done = _run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", af, "-f", "null", "-"], 60)
    found = re.findall(r"mean_volume: (-?[\d.]+) dB", done.stderr)
    return float(found[-1]) if found else None


def sound(path: Path, transcript: list[dict], seconds: float) -> dict:
    """Loudness, silences and the level of the gaps between lines. Whether a bed is music or
    effects is for the listener; this only says something is there."""
    af = f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_S},ebur128"
    done = _run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", af, "-f", "null", "-"], 120)
    quiet = gaps(transcript, seconds)
    levels = [{"span": g, "mean_db": _mean_db(path, *g)} for g in quiet[:8]]
    bed = [x for x in levels if x["mean_db"] is not None and x["mean_db"] > BED_DB]
    return {
        "loudness_lufs": loudness(done.stderr),
        "silences": silences(done.stderr),
        "speech_gaps": levels,
        "sound_under_gaps": bool(levels) and len(bed) == len(levels),
    }


def study(source: str, target: str, name: str) -> Path:
    if not TARGET.fullmatch(target) or not NAME.fullmatch(name):
        raise SystemExit("target is formats/<id> or styles/<id>; name is lower-case-with-dashes")
    folder = SCRATCH / name
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "frames").mkdir(parents=True)
    if Path(source).is_file():
        video = folder / "video.mp4"
        shutil.copyfile(source, video)
    else:
        video = fetch(source, folder)
    seconds = probe(video, MAX_SECONDS)
    times = cuts(video)
    rows = shot_rows(times, seconds)
    contact_sheet(video, times, seconds, folder / "frames")  # frames/shot<n>.jpg + contact.jpg
    frame_grids(video, times, seconds, folder / "frames")  # 3 labelled frames per shot
    transcript = transcribe(video, words=True)
    facts = {
        "source": source,
        "target": target,
        "name": name,
        "seconds": seconds,
        "pacing": pacing(rows, seconds),
        "shots": rows,
        "sound": sound(video, transcript, seconds),
        "study_goes_to": f"server/app/guides/{target}/examples/{name}/study.md",
    }
    (folder / "facts.json").write_text(json.dumps(facts, indent=2))
    (folder / "transcript.json").write_text(json.dumps(transcript, indent=2))
    (folder / "shots.md").write_text(shot_table(rows, transcript))
    return folder


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    out = study(*sys.argv[1:])
    print(f"Studied into {out}. Now read frames/, shots.md and transcript.json and write the")
    print("study.md the template in app/guides/EXAMPLES.md describes.")
