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
CARD, TITLE = 2.6, 2.9  # seconds a card on black shows; a title over a clip's opening
FADE, STEPS = 0.5, 6  # a card's words fade in and out over this long, in this many pictures
OVER = (0.07, 0.19, 0.56)  # how far down a title over a clip may sit (the darkest is used)
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


def title(words: str, width: int, height: int, solid: float = 1.0, down: float = 0.5,
          black: bool = False) -> bytes:  # fmt: skip
    """A time card's words (Movie Ad 1: "TEN MINUTES EARLIER"): small capitals set wide apart,
    `solid` of the way faded in, `down` the frame; on black, or see-through for over a clip."""
    font, gap = ImageFont.truetype(FONT, round(width * 17 / 480)), width * 6 / 480
    letters = words.upper()
    widths = [font.getlength(ch) for ch in letters]
    image = Image.new("RGBA", (width, height), (0, 0, 0, 255 if black else 0))
    pen, x = ImageDraw.Draw(image), (width - sum(widths) - gap * (len(letters) - 1)) / 2
    for ch, w in zip(letters, widths, strict=True):
        pen.text((x, height * down), ch, font=font, anchor="lm", stroke_width=0 if black else 1,
                 fill=(255, 255, 255, round(235 * solid)),
                 stroke_fill=(0, 0, 0, round(110 * solid)))  # fmt: skip
        x += w + gap
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def _fade(seconds: float) -> list[tuple[float, float]]:
    """(how solid, for how long): nothing for a moment, in over FADE, held, out over FADE."""
    step = FADE / STEPS
    up = [(k / STEPS, step) for k in range(1, STEPS)]
    return [(0.0, 0.2), *up, (1.0, seconds - 0.3 - 2 * len(up) * step), *reversed(up), (0.0, 0.1)]


def _listed(folder: Path, name: str, shown: list[tuple[bytes | None, float]]) -> list[str]:
    """Pictures and how long each shows, as ONE ffmpeg input (None: nothing shows)."""
    lines = ["ffconcat version 1.0"]
    for n, (png, seconds) in enumerate(shown):
        file = "none.png" if png is None else f"{name}{n}.png"
        if png is not None:
            (folder / file).write_bytes(png)
        lines += [f"file '{file}'", f"duration {max(seconds, 0.001):.3f}"]
    (folder / f"{name}.txt").write_text("\n".join([*lines, f"file '{lines[-2][6:-1]}'"]))
    return ["-f", "concat", "-safe", "0", "-i", f"{name}.txt"]


def _size(folder: Path, name: str) -> tuple[int, int, float]:
    asked = "stream=width,height:format=duration"
    probe = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", asked,
             "-of", "csv=p=0:s=x", name]  # fmt: skip
    size, length = subprocess.run(probe, cwd=folder, capture_output=True, text=True,  # noqa: S603
                                  timeout=60).stdout.split()  # fmt: skip
    width, height = (int(v) for v in size.split("x")[:2])
    return width, height, float(length)


def _ffmpeg(folder: Path, args: list[str]) -> bytes:
    done = subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-c:v", "libx264",  # noqa: S603, S607
                           "-movflags", "+faststart", "out.mp4"], cwd=folder,
                          capture_output=True, timeout=1800)  # fmt: skip
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-2000:])
    return (folder / "out.mp4").read_bytes()


def card_clip(words: str, like: bytes, seconds: float = CARD) -> bytes:
    """A card on black as a clip of its own, the size of `like` (a take of the same cut): the
    words fade in and out; its sound is silence."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "like.mp4").write_bytes(like)
        width, height, _ = _size(folder, "like.mp4")
        shown = [(title(words, width, height, solid, black=True), d) for solid, d in _fade(seconds)]
        quiet = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        made = ["-vf", "fps=30,format=yuv420p", "-c:a", "aac", "-t", f"{seconds:.2f}"]
        return _ffmpeg(folder, [*_listed(folder, "card", shown), *quiet, *made])


def _dark(folder: Path, at: float, height: int) -> float:
    """How far down a title over a clip sits: the darkest of the bands clear of the captions."""
    frame = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.2f}", "-i", "cut.mp4",  # noqa: S603, S607
                            "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"],
                           cwd=folder, capture_output=True, timeout=120).stdout  # fmt: skip
    grey, band = Image.open(io.BytesIO(frame)).convert("L"), round(height * 0.04)
    light = {d: grey.crop((0, round(height * d) - band, grey.width, round(height * d) + band))
             .resize((1, 1)).getpixel((0, 0)) for d in OVER}  # fmt: skip
    return min(light, key=light.get)


def burn(data: bytes, caps: list[dict], titles: tuple[dict, ...] = ()) -> bytes:
    """The cut with its captions, and each title over a clip's opening (`titles`: [{start,
    words}]), in the picture; its sound is copied as it is."""
    if not caps and not titles:
        return data
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "cut.mp4").write_bytes(data)
        width, height, length = _size(folder, "cut.mp4")
        Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(folder / "none.png")
        said = [(None if n < 0 else draw(caps[n]["words"], k, width, height), seconds)
                for n, k, seconds in states(caps, length)]  # fmt: skip
        over, at = [], 0.0
        for one in sorted(titles, key=lambda x: x["start"]):
            down = _dark(folder, one["start"] + 1.0, height)
            over += [(None, one["start"] - at),
                     *((title(one["words"], width, height, solid, down) if solid else None, d)
                       for solid, d in _fade(TITLE))]  # fmt: skip
            at = one["start"] + TITLE
        over.append((None, max(length - at, 0.04)))
        graph = ("[1:v]format=rgba[c];[0:v][c]overlay=eof_action=pass[x];[2:v]format=rgba[t];"
                 "[x][t]overlay=eof_action=pass,format=yuv420p[v]")  # fmt: skip
        return _ffmpeg(folder, ["-i", "cut.mp4", *_listed(folder, "said", said),
                                *_listed(folder, "over", over), "-filter_complex", graph,
                                "-map", "[v]", "-map", "0:a?", "-c:a", "copy"])  # fmt: skip
