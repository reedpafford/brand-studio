"""Readable phone insert: fit a real brand screen onto the phone in one frame of a clip, then hold it with
a gentle push-in toward one spot, keeping the phone edge in frame (never full screen).
Usage: insert_hold.py clip.mp4 at_seconds screen.png focus_x focus_y out.mp4 [seconds=1.5] [zoom=1.75]
focus_x/focus_y are in screen.png pixels (e.g. the Spotlight card). Splice out.mp4 into the cut yourself."""

import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image

clip, at, scr, fx, fy, out = (
    sys.argv[1],
    sys.argv[2],
    sys.argv[3],
    float(sys.argv[4]),
    float(sys.argv[5]),
    sys.argv[6],
)
secs = float(sys.argv[7]) if len(sys.argv) > 7 else 1.5
zmax = float(sys.argv[8]) if len(sys.argv) > 8 else 1.75
tmp = tempfile.mkdtemp()
subprocess.run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-ss",
        at,
        "-i",
        clip,
        "-frames:v",
        "1",
        f"{tmp}/f.png",
    ],
    check=True,
)
f, r = cv2.imread(f"{tmp}/f.png"), cv2.imread(scr)
s = cv2.SIFT_create()
g = lambda im: cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
k1, d1 = s.detectAndCompute(g(r), None)
k2, d2 = s.detectAndCompute(g(f), None)
m = [
    a
    for a, b in cv2.BFMatcher().knnMatch(d1, d2, k=2)
    if a.distance < 0.75 * b.distance
]
if len(m) < 12:
    sys.exit(
        "The screen isn't found in that frame: pick a frame where the phone is large and upright."
    )
H, _ = cv2.findHomography(
    np.float32([k1[a.queryIdx].pt for a in m]),
    np.float32([k2[a.trainIdx].pt for a in m]),
    cv2.RANSAC,
    4.0,
)
h, w = r.shape[:2]
warp = cv2.warpPerspective(r, H, (f.shape[1], f.shape[0]))
msk = cv2.erode(
    cv2.warpPerspective(np.full((h, w), 255, np.uint8), H, (f.shape[1], f.shape[0])),
    np.ones((3, 3), np.uint8),
)
f[msk > 0] = warp[msk > 0]
cx, cy = cv2.perspectiveTransform(np.float32([[[fx, fy]]]), H)[0][0]
im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
W, Hh = im.size
n = max(2, int(secs * 24))
for i in range(n):
    t = i / (n - 1)
    t = t * t * (3 - 2 * t)
    z = 1 + (zmax - 1) * t
    cw, ch = W / z, Hh / z
    x = min(max(0, cx * t + W / 2 * (1 - t) - cw / 2), W - cw)
    y = min(max(0, cy * t + Hh / 2 * (1 - t) - ch / 2), Hh - ch)
    im.crop((x, y, x + cw, y + ch)).resize((W, Hh), Image.LANCZOS).save(
        f"{tmp}/{i:03d}.png"
    )
subprocess.run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-framerate",
        "24",
        "-i",
        f"{tmp}/%03d.png",
        "-pix_fmt",
        "yuv420p",
        out,
    ],
    check=True,
)
print(out)
