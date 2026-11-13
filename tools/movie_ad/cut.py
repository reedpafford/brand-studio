"""Join the clips into the three versions: hook, half a second of black, then the body.
Each clip's newest good take is used. On each clip: basic captions (the script's own words, timed
to the words heard) and, where the alarm is going off, its sound laid in loud.
  python3 cut.py            builds out/RP5 - v1.mp4, v2, v3 and copies them to the Desktop
  CAPTIONS=0 python3 cut.py without captions
The alarm sound is siren/alarm.wav when Reed's recording of the real one is there (it is looped);
until then a stand-in is made here: a piercing, very high whistle (his words for it)."""
import difflib, json, os, re, shutil, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import plan

HERE = os.path.dirname(os.path.abspath(__file__))
OUT, PARTS = f"{HERE}/out", f"{HERE}/out/parts"
DESK = os.path.expanduser("~/Desktop/Palace Guard Ads")
W, H, SR = 480, 854, 44100
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "24",
       "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2"]
FONT = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
YELLOW = (255, 212, 0, 255)  # the word being spoken; the rest of the caption is white
CAP_Y = 620  # captions sit centred here, in the lower third
TITLE = ImageFont.truetype("/System/Library/Fonts/Avenir Next.ttc", 19, index=5)  # Medium, spaced wide
EARLIER = "TEN MINUTES EARLIER"  # on black after each hook, before the story goes back
# The script's own time jumps: the words, and how far down the picture they sit (a dark part of
# that clip's opening frame, clear of faces and of the captions).
TITLES = {"b7": ("TWENTY MINUTES LATER", 45), "d1": ("TWO DAYS LATER", 480)}
# Words a take says that the script doesn't have: that stretch of the take's own sound is silenced
MUTE = {"b4": [(0.0, 2.2)],    # take 3 opens on "Yeah, I know what you're talking about."
        "b5": [(20.3, 99, 18.6)]}  # take 5 repeats "I got the plate" inside her car: her own
#                                    breathing from 18.6 s on is laid there instead (a third number)
# The alarm's sound, per clip, as (second, level 0-1) points joined by straight lines: `bright` is
# the full whistle, `muffled` its dull, quieter form. Loud only at the pull; it dies down fast
# under dialogue and once the van drives off, and it is never heard where its light isn't lit
# (Reed, 13 Nov). "pull" = the frame the strobe first fires; "end" = the clip's end.
ALARM = {
    # the hook: on her lit face; gone to a murmur before the 911 call; lifts when the alarm is
    # seen firing in her hand (8.7-10.4 s); off before the hug, where its light is off
    "h1": {"bright": [(0, .75), (1.9, .75), (2.5, 0), (8.6, 0), (8.8, .14), (10.4, .14), (10.9, 0)],
           "muffled": [(1.9, 0), (2.5, .045), (10.9, .045), (11.8, 0)]},
    # the pull: full for the men's flinch and the heads turning; dies as they run for the van;
    # a murmur while the van leaves and the cart kid yells; back with the light filling her car
    # (18 s) and cut dead the frame that light goes out (take 5: 19.95 s)
    "b5": {"bright": [("pull", 0), ("pull+0.04", .85), (7.0, .85), (7.3, .6), (9.6, .6), (11.0, .15),
                      (12.0, 0), (17.9, 0), (18.3, .3), (19.9, .3), (19.96, 0)],
           "muffled": [(9.6, 0), (12.0, .07), (19.9, .07), (19.96, 0)]},
    # the demonstration in the kitchen: on with the light, off on the cut away from it (11.7 s)
    "c4": {"bright": [("pull", 0), ("pull+0.05", .2), (11.62, .2), (11.72, 0)], "muffled": []},
}


def run(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def take(s, key):
    return [t for t in s["clips"][key]["tries"] if t["status"] == "succeeded"][-1]["path"]


# ---------------------------------------------------------------- the alarm's sound
def alarm_wave(seconds, muffled=False):
    real = f"{HERE}/siren/alarm.wav"
    n = int(seconds * SR)
    if os.path.exists(real):  # Reed's recording, looped
        w = wave.open(real)
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
        x = x.reshape(-1, w.getnchannels()).mean(axis=1)
        x /= max(1e-6, np.abs(x).max())
        x = np.tile(x, n // len(x) + 2)[:n]
        return np.convolve(x, np.ones(6) / 6, mode="same") if muffled else x
    t = np.arange(n) / SR  # stand-in: a shrill whistle near 3.5 kHz with a fast flutter
    f = 3500 + 110 * np.sin(2 * np.pi * 13 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    if muffled:  # heard through a wall or a car door: the bare tone, no edge
        return np.sin(ph)
    x = np.sin(ph) + 0.30 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
    x *= 0.92 + 0.08 * np.sin(2 * np.pi * 26 * t)
    return np.tanh(1.6 * x) / np.tanh(1.6)


def level(points, n, pull):
    """The points as a level for every sample."""
    if not points:
        return np.zeros(n)
    end = n / SR
    def at(t):
        if isinstance(t, str):
            base, _, more = t.partition("+") if "+" in t else (t.partition("-")[0], "", "-" + t.partition("-")[2] if "-" in t else "")
            return {"pull": pull, "end": end}[base] + float(more or 0)
        return float(t)
    ts, ls = [at(t) for t, _ in points], [l for _, l in points]
    return np.interp(np.arange(n) / SR, ts, ls, left=0, right=0)


def strobe_at(path, after=0.5):
    """The second the alarm's strobe first fires: the first big jump in the picture's brightness."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "fps=24,scale=48:86,format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    lum = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 48 * 86).mean(axis=1)
    for i in range(int(after * 24) + 1, len(lum)):
        if lum[i] - lum[max(0, i - 3):i].min() > 18:
            return i / 24
    return after


def sound(s, key):
    """The clip's own sound with the alarm laid in; a wav."""
    path, out = take(s, key), f"{PARTS}/{key}.wav"
    run("-i", path, "-vn", "-ac", "1", "-ar", str(SR), out)
    w = wave.open(out)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    w.close()
    for a, b, *src in MUTE.get(key, []):
        i, j = int(a * SR), int(min(b, len(x) / SR) * SR)
        fill = x[int(src[0] * SR):int(src[0] * SR) + j - i].copy() if src else np.zeros(j - i)
        ramp = min(len(fill) // 2, SR // 10)
        fill[:ramp] *= np.linspace(0, 1, ramp); fill[-ramp:] *= np.linspace(1, 0, ramp)
        x[i:i + len(fill)] = fill; x[i + len(fill):j] = 0
    if key in ALARM:
        used = str(ALARM[key])
        pull = strobe_at(path) if "pull" in used else 0
        bright = level(ALARM[key]["bright"], len(x), pull)
        dull = level(ALARM[key]["muffled"], len(x), pull)
        x = (x * (1 - 0.5 * np.clip(bright * 2, 0, 1)) + alarm_wave(len(x) / SR + 1)[:len(x)] * bright
             + alarm_wave(len(x) / SR + 1, True)[:len(x)] * dull)  # the scene's own noise drops under it
        print(f"  {key}: alarm from {pull:.2f} s" if pull else f"  {key}: alarm from its first frame")
    x = np.tanh(x * 1.1) * 0.97
    w = wave.open(out, "w"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((x * 32767).astype(np.int16).tobytes()); w.close()
    return out


# ---------------------------------------------------------------- captions
norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower().replace("’", "").replace("'", ""))


def heard(path):
    js = path.replace(".mp4", ".json")
    if not os.path.exists(js):
        wav = path.replace(".mp4", ".wav")
        run("-i", path, "-ac", "1", "-ar", "16000", wav)
        subprocess.run(["whisper", wav, "--model", "small", "--language", "en", "--word_timestamps", "True",
                        "--output_format", "json", "--output_dir", os.path.dirname(path)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = []
    for seg in json.load(open(js))["segments"]:
        for w in seg.get("words", []):
            if norm(w["word"]):
                out.append((norm(w["word"]), w["start"], w["end"]))
    return out


def captions(s, key):
    """[(from, to, words)]: the script's lines in this clip, a few words at a time, each timed to
    where those words are heard (a word that isn't heard is placed inside its own shot)."""
    said = []  # (word as written, its shot's window, the line it belongs to)
    for shot in plan.CLIPS[key]["shots"]:
        a, b = map(float, re.match(r"Shot \d+, ([\d.]+)-([\d.]+) s", shot).groups())
        for n, q in enumerate(x for x in re.findall(r'"([^"]+)"', shot) if x != "Paige"):
            said += [(w, (a, b), (shot[:12], n)) for w in q.split()]
    if not said:
        return []
    got = heard(take(s, key))
    times = [None] * len(said)
    sm = difflib.SequenceMatcher(None, [norm(w) for w, _, _ in said], [g[0] for g in got], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (got[j1 + k][1], got[j1 + k][2])
        elif tag == "replace":
            a, b = got[j1][1], got[j2 - 1][2]
            for k in range(i2 - i1):
                times[i1 + k] = (a + (b - a) * k / (i2 - i1), a + (b - a) * (k + 1) / (i2 - i1))
    for k, (w, (a, b), _) in enumerate(said):  # a time far outside the word's own shot is a mishearing
        if times[k] and not (a - 0.8 <= times[k][0] <= b + 0.4):
            times[k] = None
    i = 0
    while i < len(said):  # words nobody heard: spread across the gap, inside their shot
        if times[i] is not None:
            i += 1; continue
        j = i
        while j < len(said) and times[j] is None and said[j][2] == said[i][2]:
            j += 1
        a, b = said[i][1]
        before = [t[1] for t in times[:i] if t]
        after = [t[0] for t in times[j:] if t]
        lo = max(before[-1] if before else 0, a + 0.2)
        hi = min(after[0] if after else 1e9, b)
        hi = max(hi, lo + 0.28 * (j - i))
        for k in range(i, j):
            times[k] = (lo + (hi - lo) * (k - i) / (j - i), lo + (hi - lo) * (k - i + 1) / (j - i))
        i = j
    clauses, cur = [], []  # a line's clauses (cut at its punctuation); a one-word clause joins the next
    for k, (w, _, line) in enumerate(said):
        if cur and line != said[cur[0]][2]:
            clauses.append(cur); cur = []
        cur.append(k)
        if re.search(r"[.?!,;:]$", w) and len(cur) >= 2:
            clauses.append(cur); cur = []
    if cur:
        clauses.append(cur)
    chunks = []
    for c in clauses:  # a long clause is cut into even pieces, so no word is left on its own
        text = " ".join(said[k][0] for k in c)
        n = max(-(-len(text) // 26), -(-len(c) // 5))
        size = -(-len(c) // n)
        chunks += [c[x:x + size] for x in range(0, len(c), size)]
    out = []
    for n, c in enumerate(chunks):
        a, b = times[c[0]][0], max(times[c[-1]][1], times[c[0]][0] + 0.4)
        nxt = times[chunks[n + 1][0]][0] if n + 1 < len(chunks) else None
        b = max(a + 0.3, nxt) if nxt is not None and nxt - b < 0.5 else b + 0.25
        out.append((round(a, 2), round(b, 2), [said[k][0] for k in c],
                    [round(times[k][0], 2) for k in c]))
    return out


def card(words, lit, out):
    """One caption line, the word being spoken (`lit`) in yellow."""
    text = " ".join(words)
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = draw.textbbox((0, 0), text, font=FONT, stroke_width=2)
    im = Image.new("RGBA", (box[2] - box[0] + 8, box[3] - box[1] + 8), (0, 0, 0, 0))
    d, x = ImageDraw.Draw(im), 4 - box[0]
    for n, w in enumerate(words):
        d.text((x, 4 - box[1]), w, font=FONT, fill=YELLOW if n == lit else (255, 255, 255, 255),
               stroke_width=2, stroke_fill=(0, 0, 0, 255))
        x += draw.textlength(w + " ", font=FONT)
    im.save(out)
    return im.size


def title(text, out, gap=5):
    """A time card's words: thin capitals set wide apart."""
    widths = [TITLE.getlength(ch) for ch in text]
    w, h = int(sum(widths) + gap * (len(text) - 1)) + 12, 40
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d, x = ImageDraw.Draw(im), 6
    for ch, cw in zip(text, widths):
        d.text((x, 8), ch, font=TITLE, fill=(255, 255, 255, 235), stroke_width=1, stroke_fill=(0, 0, 0, 120))
        x += cw + gap
    im.save(out)
    return im.size


def fades(n, tag, start, stop):
    return (f"[{n}:v]format=rgba,fade=t=in:st={start}:d=0.5:alpha=1,"
            f"fade=t=out:st={stop}:d=0.5:alpha=1[{tag}]")


def part(s, key):
    """One clip, re-encoded alike so the joins are clean: its sound (with the alarm), its time
    title when the script jumps in time, and its captions."""
    out, wav = f"{PARTS}/{key}.mp4", sound(s, key)
    caps = captions(s, key) if os.environ.get("CAPTIONS", "1") != "0" else []
    ins, chain, last, n = ["-i", take(s, key), "-i", wav], [f"[0:v]scale={W}:{H},setsar=1[v0]"], "v0", 2
    if key in TITLES:
        w, h = title(TITLES[key][0], f"{PARTS}/{key}-title.png")
        ins += ["-loop", "1", "-t", "2.9", "-i", f"{PARTS}/{key}-title.png"]
        chain += [fades(n, "tt", 0.2, 2.3), f"[{last}][tt]overlay={(W - w) // 2}:{TITLES[key][1]}:eof_action=pass[vt]"]
        last, n = "vt", n + 1
    for c, (a, b, words, starts) in enumerate(caps):
        for k in range(len(words)):
            png = f"{PARTS}/{key}-cap{c}-{k}.png"
            w, h = card(words, k, png)
            t0 = a if k == 0 else starts[k]
            t1 = starts[k + 1] if k + 1 < len(words) else b
            if t1 <= t0:
                continue
            ins += ["-i", png]
            chain.append(f"[{last}][{n}:v]overlay={(W - w) // 2}:{CAP_Y - h // 2}:enable='gte(t,{t0})*lt(t,{t1})'[c{n}]")
            last, n = f"c{n}", n + 1
    script = f"{PARTS}/{key}.filter"
    open(script, "w").write(";\n".join(chain))
    run(*ins, "-filter_complex_script", script, "-map", f"[{last}]", "-map", "1:a", "-shortest", *ENC, out)
    return out


def earlier():
    """The card between a hook and the story: black, the words fading in and out."""
    out, png = f"{PARTS}/earlier.mp4", f"{PARTS}/earlier.png"
    w, h = title(EARLIER, png)
    run("-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r=24:d=2.6", "-f", "lavfi", "-i",
        f"anullsrc=r={SR}:cl=stereo", "-loop", "1", "-t", "2.6", "-i", png, "-filter_complex",
        fades(2, "tt", 0.3, 1.8) + f";[0:v][tt]overlay={(W - w) // 2}:{(H - h) // 2}[v]",
        "-map", "[v]", "-map", "1:a", "-t", "2.6", *ENC, out)
    return out


if __name__ == "__main__":
    os.makedirs(PARTS, exist_ok=True)
    s = json.load(open(f"{HERE}/state.json"))
    black = earlier()
    body = [part(s, k) for k in plan.ORDER["body"]]
    for v, hook in plan.VERSIONS.items():
        files = [part(s, hook), black, *body]
        lst = f"{PARTS}/{v}.txt"
        open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
        out = f"{OUT}/RP5 - {v}.mp4"
        run("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out)
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                           capture_output=True, text=True).stdout.strip()
        shutil.copy(out, f"{DESK}/RP5 – {v}.mp4")
        print(v, f"{float(d):.1f} s", out)
