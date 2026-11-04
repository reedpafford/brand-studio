"""6 fps contact sheets with the spoken words under each frame. watch6.py video.mp4 outprefix [secs_per_sheet]"""

import os
import subprocess
import sys

import numpy as np
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw, ImageFont

v, pre = sys.argv[1], sys.argv[2]
per = float(sys.argv[3]) if len(sys.argv) > 3 else 10
d = os.path.dirname(pre) or "."
os.makedirs(d, exist_ok=True)
pcm = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", v, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
    capture_output=True,
    check=True,
).stdout
a = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
words = []
for s in WhisperModel("small", compute_type="int8").transcribe(
    a, word_timestamps=True, language="en"
)[0]:
    words += [(w.start, w.end, w.word.strip()) for w in s.words]
tmp = pre + "_f"
os.makedirs(tmp, exist_ok=True)
subprocess.run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        v,
        "-vf",
        "fps=6,scale=100:-1",
        f"{tmp}/%05d.png",
    ],
    check=True,
)
fr = sorted(os.listdir(tmp))
n = int(per * 6)
cols = 12
F = ImageFont.load_default()
for si in range(0, len(fr), n):
    chunk = fr[si : si + n]
    rows = (len(chunk) + cols - 1) // cols
    W, H = 100, 178 + 24
    sheet = Image.new("RGB", (cols * W, rows * H), "black")
    dr = ImageDraw.Draw(sheet)
    for i, f in enumerate(chunk):
        t = (si + i) / 6
        im = Image.open(f"{tmp}/{f}")
        x, y = (i % cols) * W, (i // cols) * H
        sheet.paste(im, (x, y))
        ws = " ".join(w for s, e, w in words if s <= t + 1 / 6 and e >= t)
        dr.text((x + 2, y + 180), f"{t:.1f}", fill="yellow", font=F)
        dr.text((x + 28, y + 180), ws[:16], fill="white", font=F)
    sheet.save(f"{pre}_{si // n:02d}.jpg", quality=80)
print(" ".join(f"{a:.1f}-{b:.1f} {w}" for a, b, w in words))
