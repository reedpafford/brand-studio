"""Render every board in html/ to ../boards/<id>.jpg with headless Chrome (1x). Usage: python3 render.py [id ...]"""
import os, subprocess, sys, re
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUTDIR = os.path.join(HERE, "..", "boards")
os.makedirs(OUTDIR, exist_ok=True)


def size(path):
    s = open(path).read()
    if 'class="screen p"' in s:
        return 390, 844 + 32
    if 'class="sheetboard"' in s:
        m = re.search(r'data-h="(\d+)"', s)
        return 1440, (int(m.group(1)) if m else 900) + 32
    return 1440, 900 + 32


def one(fn):
    bid = fn[:-5]
    w, h = size(os.path.join(HERE, "html", fn))
    png = f"/tmp/v6_{bid}.png"
    for attempt in range(3):
        try:
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                            f"--user-data-dir=/tmp/v6_chrome_{bid}", "--no-first-run", "--disable-extensions",
                            f"--window-size={w},{h}", f"--screenshot={png}", "file://" + os.path.join(HERE, "html", fn)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=45)
            break
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            subprocess.run(["pkill", "-f", f"v6_chrome_{bid} "])  # trailing space: P-1 must not match P-10
    Image.open(png).convert("RGB").crop((0, 0, w, h)).save(os.path.join(OUTDIR, bid + ".jpg"), quality=86, optimize=True)
    return bid


if __name__ == "__main__":
    files = sorted(f for f in os.listdir(os.path.join(HERE, "html")) if f.endswith(".html"))
    if len(sys.argv) > 1:
        files = [f for f in files if f[:-5] in sys.argv[1:] or any(f.startswith(a) for a in sys.argv[1:])]
    with ThreadPoolExecutor(4) as ex:
        for b in ex.map(one, files):
            print(b)
