"""Captions burned into a story video's cut (Movie Ad 1, Reed, 13 Nov 2026: "a little smaller,
and be more intentional ... have like the word being spoken yellow"): the script's own words,
a few at a time, each lit as it is said. `timed` places a take's scripted lines on the words
its listen heard; `for_cut` moves them into cut seconds, piece by piece; `chunks` groups them;
`burn` draws each state (Pillow, the house font) and lays them over the cut as ONE extra
input, a list of full-frame pictures and how long each shows (never an input a word)."""

import difflib
import io
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.models.clips import ClipTake
from app.models.jobs import Job

FONT = Path(__file__).parent / "fonts" / "Inter-SemiBold.otf"
ON = ("movie",)  # the styles whose story cuts are captioned unless switched off (Reed's so far)
WHITE, YELLOW, EDGE = (255, 255, 255, 255), (255, 212, 0, 255), (0, 0, 0, 255)
SIZE, DOWN = 22 / 480, 620 / 854  # the letters' height against the width; how far down they sit
LETTERS, WORDS = 26, 5  # the most a caption holds
END = re.compile(r"[.?!,;:]$")


def usual(project) -> bool:
    """Whether this video's cut is captioned until someone switches it."""
    from app import looks

    return looks.base(project.look) in ON


def _bare(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


def timed(lines: list[dict], heard: list[dict]) -> list[dict]:
    """Each scripted word with when it is said in the take: [{word, start, end, line}]. A word
    heard gets its heard time; one heard far outside its own shot was misheard, and with any
    never heard it is spread across the gap its neighbours leave, inside its shot."""
    said = [(w, line["start"], line["end"], n) for n, line in enumerate(lines)
            for w in line["text"].split()]  # fmt: skip
    times: list[tuple[float, float] | None] = [None] * len(said)
    match = difflib.SequenceMatcher(None, [_bare(s[0]) for s in said],
                                    [_bare(h["word"]) for h in heard], autojunk=False)  # fmt: skip
    for tag, i1, i2, j1, j2 in match.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
        elif tag == "replace":  # said another way ("16" for "sixteen"): shared out evenly
            a, b = heard[j1]["start"], heard[j2 - 1]["end"]
            for k in range(i2 - i1):
                times[i1 + k] = (a + (b - a) * k / (i2 - i1), a + (b - a) * (k + 1) / (i2 - i1))
    for k, (_, a, b, _) in enumerate(said):
        if times[k] and not a - 0.8 <= times[k][0] <= b + 0.4:
            times[k] = None
    i = 0
    while i < len(said):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(said) and times[j] is None and said[j][3] == said[i][3]:
            j += 1
        before = [t[1] for t in times[:i] if t]
        after = [t[0] for t in times[j:] if t]
        lo = max(before[-1] if before else 0.0, said[i][1] + 0.2)
        hi = max(min(after[0] if after else said[i][2], said[i][2]), lo + 0.28 * (j - i))
        for k in range(i, j):
            times[k] = (lo + (hi - lo) * (k - i) / (j - i), lo + (hi - lo) * (k - i + 1) / (j - i))
        i = j
    return [{"word": w, "start": round(t[0], 2), "end": round(t[1], 2), "line": n}
            for (w, _, _, n), t in zip(said, times, strict=True)]  # fmt: skip


def for_cut(db: Session, tl: dict) -> list[dict]:
    """The cut's captions: every picked take's scripted words in cut seconds, as each piece
    plays them (a word outside the stretch a piece keeps isn't in the cut), in chunks."""
    from app.item_checks import latest

    out = []
    for run, p in enumerate(tl["pieces"]):
        take = db.get(ClipTake, p["take_id"] or 0)
        row = latest(db, "words", [take.id]).get(take.id) if take else None
        job = db.get(Job, row.job_id) if row and row.job_id and row.status == "done" else None
        if job is None or job.input.get("silent"):
            continue
        heard = [w for line in (job.output or {}).get("heard") or [] for w in line["words"]]
        for w in timed(job.input.get("lines") or [], heard):
            at = p["start"] + w["start"] - p["from"]
            if p["start"] - 0.05 <= at and at + w["end"] - w["start"] <= p["end"] + 0.05:
                out.append({**w, "start": round(max(at, 0), 2), "line": (run, w["line"]),
                            "end": round(at + w["end"] - w["start"], 2)})  # fmt: skip
    return chunks(out)


def chunks(words: list[dict]) -> list[dict]:
    """A few words at a time: [{start, end, words, at}] (`at`: when each word is lit). A line
    breaks at its punctuation; a long clause is cut into even pieces, so no word is left on
    its own; a caption stays up until the next when that follows at once."""
    clauses, cur = [], []
    for k, w in enumerate(words):
        if cur and w["line"] != words[cur[0]]["line"]:
            clauses.append(cur)
            cur = []
        cur.append(k)
        if END.search(w["word"]) and len(cur) >= 2:
            clauses.append(cur)
            cur = []
    groups = []
    for c in [*clauses, *([cur] if cur else [])]:
        letters = len(" ".join(words[k]["word"] for k in c))
        size = -(-len(c) // max(-(-letters // LETTERS), -(-len(c) // WORDS)))
        groups += [c[x : x + size] for x in range(0, len(c), size)]
    out = []
    for n, g in enumerate(groups):
        start = words[g[0]]["start"]
        end = max(words[g[-1]]["end"], start + 0.4)
        after = words[groups[n + 1][0]]["start"] if n + 1 < len(groups) else None
        end = max(start + 0.3, after) if after is not None and after - end < 0.5 else end + 0.25
        out.append({"start": start, "end": round(end, 2), "words": [words[k]["word"] for k in g],
                    "at": [words[k]["start"] for k in g]})  # fmt: skip
    return out


def draw(words: list[str], lit: int, width: int, height: int) -> bytes:
    """One caption as a see-through picture the size of the frame: white with a dark edge,
    the word being said in yellow."""
    font = ImageFont.truetype(FONT, round(width * SIZE))
    edge = max(2, round(width / 240))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    x = (width - pen.textlength(" ".join(words), font=font)) / 2
    for n, word in enumerate(words):
        pen.text((x, height * DOWN), word, font=font, anchor="lm", stroke_width=edge,
                 fill=YELLOW if n == lit else WHITE, stroke_fill=EDGE)  # fmt: skip
        x += pen.textlength(word + " ", font=font)
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def states(caps: list[dict], length: float) -> list[tuple[int, int, float]]:
    """The pictures in order, each (caption, lit word, seconds shown); caption -1 is none."""
    out, at = [], 0.0
    for n, c in enumerate(caps):
        starts = [max(c["start"], at), *c["at"][1:], c["end"]]
        if starts[0] > at + 0.01:
            out.append((-1, 0, starts[0] - at))
        for k in range(len(c["words"])):
            if starts[k + 1] > starts[k]:
                out.append((n, k, starts[k + 1] - starts[k]))
        at = max(at, c["end"])
    return [*out, (-1, 0, max(length - at, 0.04))]


def burn(data: bytes, caps: list[dict]) -> bytes:
    """The cut with its captions in the picture; its sound is copied as it is."""
    if not caps:
        return data
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "cut.mp4").write_bytes(data)
        asked = "stream=width,height:format=duration"
        probe = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", asked,
                 "-of", "csv=p=0:s=x", "cut.mp4"]  # fmt: skip
        size, length = subprocess.run(probe, cwd=folder, capture_output=True, text=True,  # noqa: S603
                                      timeout=60).stdout.split()  # fmt: skip
        width, height = (int(v) for v in size.split("x")[:2])
        Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(folder / "none.png")
        listed = ["ffconcat version 1.0"]
        for n, k, seconds in states(caps, float(length)):
            name = "none.png" if n < 0 else f"{n}-{k}.png"
            if n >= 0:
                (folder / name).write_bytes(draw(caps[n]["words"], k, width, height))
            listed += [f"file '{name}'", f"duration {seconds:.3f}"]
        (folder / "list.txt").write_text("\n".join([*listed, "file 'none.png'"]))
        laid = "[1:v]format=rgba[c];[0:v][c]overlay=eof_action=pass,format=yuv420p[v]"
        done = subprocess.run(  # noqa: S603
            ["ffmpeg", "-v", "error", "-y", "-i", "cut.mp4", "-f", "concat", "-safe", "0",  # noqa: S607
             "-i", "list.txt", "-filter_complex", laid, "-map", "[v]", "-map", "0:a?",
             "-c:v", "libx264", "-c:a", "copy", "-movflags", "+faststart", "out.mp4"],
            cwd=folder, capture_output=True, timeout=1800)  # fmt: skip
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
        return (folder / "out.mp4").read_bytes()
