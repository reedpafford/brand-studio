"""Look at and listen to finished clips: a contact sheet (a frame every `STEP` seconds) and the
words heard against the words planned.   python3 review.py <clip> [...]"""
import json, os, re, subprocess, sys
import plan

HERE = os.path.dirname(os.path.abspath(__file__))
norm = lambda t: re.sub(r"[^a-z0-9 ]", "", t.lower().replace("’", "").replace("'", "")).split()
NUM = {"130": "one hundred thirty", "16": "sixteen", "40": "forty", "30": "thirty", "20": "twenty"}

for key in sys.argv[1:]:
    s = json.load(open(f"{HERE}/state.json"))
    made = [t for t in s["clips"][key]["tries"] if t["status"] == "succeeded"]
    path = made[-1]["path"]
    step = float(os.environ.get("STEP", "1"))
    n = int(plan.CLIPS[key]["seconds"] / step) + 1
    cols = min(n, 13)
    rows = -(-n // cols)
    sheet = path.replace(".mp4", "-sheet.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf",
                    f"fps={1/step},scale=180:-2,tile={cols}x{rows}", "-frames:v", "1", sheet])
    wav = path.replace(".mp4", ".wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", "16000", wav])
    subprocess.run(["whisper", wav, "--model", "small", "--language", "en", "--word_timestamps", "True",
                    "--output_format", "json", "--output_dir", f"{HERE}/clips"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    heard = json.load(open(wav.replace(".wav", ".json")))
    want = []
    for shot in plan.CLIPS[key]["shots"]:
        want += [q for q in re.findall(r'"([^"]+)"', shot) if q != "Paige"]
    w, h = norm(" ".join(want)), norm(heard["text"])
    for a, b in NUM.items():
        h = norm(" ".join(h).replace(a, b)); w = norm(" ".join(w).replace(a, b))
    print(f"== {key}: {sheet}")
    for seg in heard["segments"]:
        print(f"   {seg['start']:5.1f}-{seg['end']:5.1f}  {seg['text'].strip()}")
    missing = [x for x in w if x not in h]
    extra = [x for x in h if x not in w]
    print("   words planned", len(w), "heard", len(h), "| SAME" if w == h else f"| DIFFERENT: missing {missing[:12]} extra {extra[:12]}")
