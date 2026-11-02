"""Animated fomo coin chart (real UI from assets/brands/fomo/screens/token-up.png, big fomo header with the eyes), rendered as
480x854 video frames. Usage: chart_anim.py kind seconds out.mp4   kind = climb | crash | rocket"""

import os
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

D = os.path.dirname(os.path.abspath(__file__))
F = "/usr/share/fonts/opentype/inter/"
REPO = os.path.abspath(os.path.join(D, "..", ".."))
SCREENS = os.path.join(REPO, "assets", "brands", "fomo")
kind, secs, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
BG = (6, 5, 15)
GREEN = (87, 200, 96)
RED = (235, 77, 75)
base = Image.open(f"{SCREENS}/screens/token-up.png").convert("RGB")
W, H = base.size
d = ImageDraw.Draw(base)
d.rectangle((0, 96, W, 640), fill=BG)  # clear price, change line and chart
# fomo header with the eyes
HD = 120
logo = Image.open(f"{SCREENS}/logo.png").convert("RGBA").resize((92, 92))
px = logo.load()
for yy in range(92):
    for xx in range(92):
        r, g, b, a = px[xx, yy]
        if r + g + b < 150:
            px[xx, yy] = (r, g, b, 0)
page = Image.new("RGB", (W, H + HD), BG)
hd = ImageDraw.Draw(page)
wm = ImageFont.truetype(F + "Inter-Bold.otf", 60)
tw = hd.textlength("fomo", font=wm)
x0 = int((W - (92 + 14 + tw)) / 2)
page.paste(logo, (x0, 14), logo)
hd.text((x0 + 106, 20), "fomo", font=wm, fill=(232, 234, 255))
hd.line((24, HD - 2, W - 24, HD - 2), fill=(30, 30, 42), width=2)
page.paste(base, (0, HD))
random.seed(5)


def walk(n, a, b, noise):
    v = [a + (b - a) * (i / (n - 1)) ** 1.3 for i in range(n)]
    out = []
    j = 0
    for i, x in enumerate(v):
        if i % 3 == 0:
            j = random.uniform(-noise, noise) * 2.2
        out.append(x + j)
    return out


# price series (the line), and how much of it is drawn over time
if kind == "climb":
    pre = walk(30, 0.21, 0.24, 0.004)
    s = pre + walk(60, 0.24, 0.37, 0.006)
    start = 30
if kind == "crash":
    pre = walk(60, 0.21, 0.37, 0.006)
    s = pre + walk(40, 0.37, 0.12, 0.006)
    start = 60
if kind == "rocket":
    pre = walk(60, 0.21, 0.37, 0.006) + walk(40, 0.37, 0.12, 0.006)
    s = pre + walk(70, 0.12, 1.84, 0.03)
    start = 100
T0 = s[start]
fps = 30
N = int(secs * fps)
f_big = ImageFont.truetype(F + "Inter-SemiBold.otf", 52)
f_ch = ImageFont.truetype(F + "Inter-Medium.otf", 24)
f_pill = ImageFont.truetype(F + "Inter-SemiBold.otf", 17)
os.makedirs(out + "_f", exist_ok=True)
for k in range(N):
    p = min(1, (k + 1) / (N * 0.85))
    upto = start + int(p * (len(s) - 1 - start))
    seg = s[: upto + 1]
    lo = min(seg + [s[0]]) * 0.93
    hi = max(seg) * 1.06
    im = page.copy()
    d = ImageDraw.Draw(im)
    cur = seg[-1]
    first = s[0]
    up = cur >= seg[start] if kind != "rocket" else True
    col = RED if (kind == "crash" and upto > start + 2) else GREEN
    pct = (cur / first - 1) * 100
    d.text(
        (24, HD + 104),
        f"${cur:,.3f}" if cur < 1 else f"${cur:,.2f}",
        font=f_big,
        fill=(255, 255, 255),
    )
    arrow = "▲" if pct >= 0 else "▼"
    d.text(
        (26, HD + 176),
        f"{arrow} {abs(pct):.1f}%  1h",
        font=f_ch,
        fill=GREEN if pct >= 0 else RED,
    )
    y0, y1 = HD + 250, HD + 620
    n = len(s)
    pts = [
        (int(8 + (W - 120) * i / (n - 1)), int(y1 - (v - lo) / (hi - lo) * (y1 - y0)))
        for i, v in enumerate(seg)
    ]
    if len(pts) > 1:
        glow = Image.new("RGB", im.size, (0, 0, 0))
        ImageDraw.Draw(glow).line(
            pts, fill=col if kind == "crash" and upto > start + 2 else GREEN, width=10
        )
        im = Image.blend(
            im,
            Image.composite(
                glow, im, glow.convert("L").point(lambda q: 255 if q else 0)
            ),
            0.25,
        )
        d = ImageDraw.Draw(im)
        RED0, RED1 = (60, 100) if kind != "climb" else (10**6, 10**6)
        d.line(pts[: RED0 + 1], fill=GREEN, width=5, joint="curve")
        if len(pts) > RED0 + 1:
            d.line(pts[RED0 : RED1 + 1], fill=RED, width=5, joint="curve")
        if len(pts) > RED1 + 1:
            d.line(pts[RED1:], fill=GREEN, width=5, joint="curve")
        x, y = pts[-1]
        d.ellipse((x - 14, y - 14, x + 14, y + 14), outline=col, width=3)
        d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=col)
        lab = f"${cur:,.3f}" if cur < 1 else f"${cur:,.2f}"
        w = d.textlength(lab, font=f_pill) + 16
        d.rounded_rectangle((x + 22, y - 15, x + 22 + w, y + 15), radius=6, fill=col)
        d.text((x + 30, y - 10), lab, font=f_pill, fill=(255, 255, 255))
        d.line((0, y, x - 16, y), fill=(70, 70, 80), width=1)
    im.save(f"{out}_f/p{k:04d}.png")
    # 480x854 frame: the page fills the height, slow push in (shake on the crash)
    z = 1 + 0.08 * k / N
    sh = H + HD
    scale = 854 * z / sh
    fr = im.resize((int(W * scale), int(sh * scale)), Image.LANCZOS)
    cx = fr.width // 2 + (
        random.randint(-6, 6) if kind == "crash" and upto > start + 3 else 0
    )
    cy = int(fr.height * 0.36)
    canvas = Image.new("RGB", (480, 854), BG)
    canvas.paste(fr, (240 - cx, int(854 * 0.36) - cy))
    canvas.save(f"{out}_f/{k:04d}.png")
subprocess.run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-framerate",
        "30",
        "-i",
        f"{out}_f/%04d.png",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        out,
    ],
    check=True,
)
print(out)
