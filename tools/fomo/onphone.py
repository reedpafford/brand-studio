"""Put an animated chart onto the phone screen in a clip: finds the real fomo screen (ref.png, e.g. assets/brands/fomo/screens/token-up.png) in each
frame and warps the new chart region onto it. Usage: onphone.py in.mp4 out.mp4 ref.png start_frame:anim_dir ..."""

import glob
import os
import subprocess
import sys

import cv2
import numpy as np

src, out, refp = sys.argv[1:4]
jobs = [(int(a.split(":")[0]), a.split(":")[1]) for a in sys.argv[4:]]
tmp = out + "_fr"
os.makedirs(tmp, exist_ok=True)
subprocess.run(
    ["ffmpeg", "-v", "error", "-y", "-i", src, f"{tmp}/%04d.png"], check=True
)
ref = cv2.imread(refp, 0)
sift = cv2.SIFT_create(4000)
kr, dr = sift.detectAndCompute(ref, None)
bf = cv2.BFMatcher()
Y0, Y1, HD = 96, 640, 120
FULL = os.environ.get("FULL")  # a still screen over the whole phone screen
mask = np.zeros(ref.shape, np.float32)
if FULL:
    mask[14:1216, 10:593] = 1
else:
    mask[Y0:Y1, 4:599] = 1
    mask = cv2.GaussianBlur(mask, (0, 0), 3)


def H_of(f):
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    g2 = cv2.resize(g, None, fx=2, fy=2)
    kf, df = sift.detectAndCompute(g2, None)
    m = [a for a, b in bf.knnMatch(dr, df, k=2) if a.distance < 0.75 * b.distance]
    if len(m) < 12:
        return None
    s = np.float32([kr[a.queryIdx].pt for a in m])
    d = np.float32([kf[a.trainIdx].pt for a in m]) / 2
    H, inl = cv2.findHomography(s, d, cv2.RANSAC, 4)
    return H if inl is not None and inl.sum() >= 20 else None


for start, ad in jobs:
    pages = sorted(glob.glob(f"{ad}/p*.png")) if not FULL else [FULL] * int(ad)
    Hs = []
    for k in range(len(pages)):
        f = cv2.imread(f"{tmp}/{start + k + 1:04d}.png")
        Hs.append(H_of(f))
    for k in range(len(Hs)):  # fill gaps, then smooth the corners over 3 frames
        if Hs[k] is None:
            Hs[k] = next(
                Hs[j]
                for j in sorted(range(len(Hs)), key=lambda j: abs(j - k))
                if Hs[j] is not None
            )
    C = np.float32([[0, 0], [603, 0], [603, 1230], [0, 1230]]).reshape(-1, 1, 2)
    pts = [cv2.perspectiveTransform(C, H).reshape(4, 2) for H in Hs]
    sm = [np.mean(pts[max(0, k - 1) : k + 2], axis=0) for k in range(len(pts))]
    for k, p in enumerate(pages):
        fp = f"{tmp}/{start + k + 1:04d}.png"
        f = cv2.imread(fp).astype(np.float32)
        H = cv2.getPerspectiveTransform(C.reshape(4, 2), sm[k].astype(np.float32))
        pg = cv2.imread(p) if FULL else cv2.imread(p)[HD : HD + 1230, :603]
        pg = cv2.resize(pg, (603, 1230))
        w = cv2.warpPerspective(
            pg, H, (f.shape[1], f.shape[0]), flags=cv2.INTER_AREA
        ).astype(np.float32)
        a = cv2.warpPerspective(mask, H, (f.shape[1], f.shape[0]))[..., None]
        w = (
            cv2.GaussianBlur(w, (0, 0), 0.6) * 0.92
        )  # match the clip's softness and screen brightness
        cv2.imwrite(fp, (f * (1 - a) + w * a).clip(0, 255).astype(np.uint8))
subprocess.run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-framerate",
        "24",
        "-i",
        f"{tmp}/%04d.png",
        "-i",
        src,
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-shortest",
        out,
    ],
    check=True,
)
print(out)
