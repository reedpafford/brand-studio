"""Song-ad workflow, run by hand against the live app (the recipe in docs/next/song-ad-workflow.md).

PAID CALLS: every run that calls KIE (`song`) or makes anything on the live site (looks, stills, prompts, takes)
costs money. Before it: Reed's OK on a cap. After it: a row in ops/SPEND.md (PR to main).
Keys and sign-in come only from the environment (BS_QA_EMAIL, BS_QA_PASSWORD, KIE_API_KEY) and are never printed,
logged, committed or put in chat. `ref`, `measure`, `retime`, `review` and `cut` are free.

  python song_ad.py ref <ad-library-id> <dir>          free: fetch a Meta ad, transcribe it, BPM, frame sheet
  python song_ad.py song <request.json> <dir>          paid (KIE, about $0.06): 2 Suno takes for locked lyrics
  python song_ad.py measure <song.mp3> <request.json>  free: line start/end times in the song
  python song_ad.py retime <project> <song.lines.json> <scene-starts> <end>   free: shot times = song times
  python song_ad.py review <project> <dir>             free: 4 frames from each clip's newest take
  python song_ad.py cut <project> <song.mp3> <dir>     free: takes trimmed to the song, song as the only sound
"""
import difflib, json, math, os, re, subprocess, sys, time
import requests

SITE = os.environ.get("BS_SITE", "https://srv2091584.hstgr.cloud") + "/api"
KIE = "https://api.kie.ai/api/v1"
SPLIT_OVER = 16  # a clip with people longer than this is split in two: long clips drift faces


# --- the live app ---------------------------------------------------------------------------
def retry(fn, tries=6):
    for i in range(tries):
        try:
            return fn()
        except requests.exceptions.ConnectionError:  # the site drops connections for under a minute
            if i == tries - 1:
                raise
            time.sleep(10 * (i + 1))


def site():
    s = requests.Session()
    login = {"email": os.environ["BS_QA_EMAIL"], "password": os.environ["BS_QA_PASSWORD"]}
    retry(lambda: s.post(SITE + "/auth/login", json=login, timeout=60).raise_for_status())
    return s


def call(s, method, path, **kw):
    r = retry(lambda: s.request(method, SITE + path, timeout=300, **kw)) if method == "GET" else \
        s.request(method, SITE + path, timeout=300, **kw)
    if r.status_code >= 400:
        sys.exit(f"{method} {path} -> {r.status_code} {r.text[:500]}")
    return r.json() if "json" in r.headers.get("content-type", "") else r.content


def download(s, file_id, path):
    if not os.path.exists(path):
        open(path + ".part", "wb").write(call(s, "GET", f"/files/{file_id}"))
        os.replace(path + ".part", path)
    return path


def seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout
    return float(out)


# --- 1. the reference ad ------------------------------------------------------------------
FETCH_AD = """
const { chromium } = require('playwright');
(async () => {
  const id = process.argv[process.argv.length - 1], b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 1600 } });
  await p.goto('https://www.facebook.com/ads/library/?id=' + id, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.waitForTimeout(9000);
  const found = await p.evaluate(id => { for (const v of document.querySelectorAll('video')) {  // the ad's own card
    let e = v; for (let i = 0; e && i < 25; i++, e = e.parentElement)
      if ((e.innerText || '').includes('Library ID: ' + id)) return [v.src, e.innerText]; } }, id);
  console.log(JSON.stringify(found || null)); await b.close();
})();
"""


def ref(ad_id, out):
    os.makedirs(out, exist_ok=True)
    node_path = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    res = subprocess.run(["node", "-e", FETCH_AD, ad_id], capture_output=True, text=True,
                         env={**os.environ, "NODE_PATH": node_path})
    found = json.loads(res.stdout.strip().splitlines()[-1]) if res.stdout.strip() else None
    if not found:
        sys.exit("No video found for that ad. " + res.stderr[-300:])
    open(f"{out}/ad.txt", "w").write(found[1])
    subprocess.run(["curl", "-sSL", "-o", f"{out}/ad.mp4", found[0]], check=True)  # the CDN wants a plain client
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{out}/ad.mp4", "-vf", "fps=1/3,scale=180:-1,tile=8x5",
                    f"{out}/frames_%d.jpg"], check=True)
    transcribe(f"{out}/ad.mp4", f"{out}/ad.lines.json")
    print("BPM", tempo(f"{out}/ad.mp4"), "| frames, transcript and ad text in", out)


def transcribe(path, out):
    import numpy as np
    from faster_whisper import WhisperModel
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(audio, word_timestamps=True)
    words = [[w.word, round(w.start, 2), round(w.end, 2)] for seg in segs for w in seg.words]
    json.dump(words, open(out, "w"))
    return words


def tempo(path):
    import librosa, numpy as np
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "22050", "-"],
                         capture_output=True).stdout
    return round(float(np.atleast_1d(librosa.beat.beat_track(y=np.frombuffer(pcm, np.float32), sr=22050)[0])[0]), 1)


# --- 2. the song (Suno through KIE) --------------------------------------------------------
def song(request_file, out):
    os.makedirs(out, exist_ok=True)
    head = {"Authorization": "Bearer " + os.environ["KIE_API_KEY"]}
    credits = lambda: requests.get(KIE + "/chat/credit", headers=head, timeout=60).json().get("data")
    before = credits()
    task = requests.post(KIE + "/jobs/createTask", headers=head, json=json.load(open(request_file)), timeout=60).json()
    task_id = task["data"]["taskId"]
    for _ in range(90):
        info = requests.get(KIE + "/jobs/recordInfo", headers=head, params={"taskId": task_id}, timeout=60).json()["data"]
        if info.get("state") in ("success", "fail"):
            break
        time.sleep(10)
    result = json.loads(info.get("resultJson") or "{}")
    urls = result.get("resultUrls") or [t.get("audioUrl") for t in result.get("data", [])]
    for i, url in enumerate(u for u in urls if u):
        path = f"{out}/take{i + 1}.mp3"
        open(path, "wb").write(requests.get(url, timeout=120).content)
        print(path, round(seconds(path), 1), "s", url)
    print("task", task_id, "| KIE credits", before, "->", credits(), "(log it in ops/SPEND.md)")


# --- 3. measure: when each locked line is sung ---------------------------------------------
def measure(song_file, request_file):
    lyrics = json.load(open(request_file))["input"]["lyrics"]
    lines = [l.strip() for l in lyrics.splitlines() if l.strip() and not l.strip().startswith("[")]
    norm = lambda w: re.sub(r"[^a-z0-9]", "", w.lower())
    want = [(i, norm(w)) for i, l in enumerate(lines) for w in l.split() if norm(w)]
    heard = [(norm(w), a, b) for w, a, b in transcribe(song_file, song_file + ".words.json") if norm(w)]
    match = difflib.SequenceMatcher(None, [w for _, w in want], [w for w, _, _ in heard], autojunk=False)
    times = {}
    for block in match.get_matching_blocks():  # Whisper mishears sung words; the matches anchor each line
        for k in range(block.size):
            i, (_, a, b) = want[block.a + k][0], heard[block.b + k]
            start, end = times.get(i, (a, b))
            times[i] = (min(start, a), max(end, b))
    out = [{"n": i + 1, "line": l, "start": times.get(i, (None,))[0], "end": times.get(i, (None, None))[1]}
           for i, l in enumerate(lines)]
    json.dump(out, open(song_file + ".lines.json", "w"), indent=1)
    for row in out:
        print(f"{row['n']:3d} {row['start'] or 0:7.2f} {row['end'] or 0:7.2f}  {row['line']}")
    print("BPM", tempo(song_file), "| length", round(seconds(song_file), 1), "s")


# --- 4. retime: the breakdown's shots follow the song --------------------------------------
def retime(project, starts, end):
    """starts: each scene's start in the song (seconds, one per SCENE, in order); end: where the video ends."""
    s = site()
    bd = call(s, "GET", f"/projects/{project}/breakdown")["breakdown"]
    marks = [float(x) for x in starts.split(",")] + [float(end)]
    if len(marks) - 1 != len(bd["scenes"]):
        sys.exit(f"{len(bd['scenes'])} scenes but {len(marks) - 1} song pieces")
    clips = []
    for i, scene in enumerate(bd["scenes"]):
        span, total, t = marks[i + 1] - marks[i], sum(x["seconds"] for x in scene["shots"]), marks[i]
        for j, shot in enumerate(scene["shots"]):  # scale the scene to its piece of the song
            shot["seconds"] = round(marks[i + 1] - t if j == len(scene["shots"]) - 1 else shot["seconds"] * span / total, 2)
            t += shot["seconds"]
        groups, people = [scene["shots"]], any(x["character_ids"] for x in scene["shots"])
        if span > SPLIT_OVER and people and len(scene["shots"]) > 1:
            run, cut = 0, 1
            for j, shot in enumerate(scene["shots"]):
                run += shot["seconds"]
                if run >= span / 2:
                    cut = max(1, min(j + 1, len(scene["shots"]) - 1))
                    break
            groups = [scene["shots"][:cut], scene["shots"][cut:]]
        for g in groups:
            clips.append({"id": f"c{len(clips) + 1}", "shot_ids": [x["id"] for x in g],
                          "seconds": max(4, math.ceil(sum(x["seconds"] for x in g))), "seam": ""})
    bd["clips"] = clips
    call(s, "PUT", f"/projects/{project}/breakdown", json=bd)
    plan, t = [], marks[0]
    for c in clips:
        span = sum(x["seconds"] for sc in bd["scenes"] for x in sc["shots"] if x["id"] in c["shot_ids"])
        plan.append({"clip": c["id"], "start": round(t, 2), "end": round(t + span, 2)})
        t += span
    json.dump(plan, open(f"project{project}.song-plan.json", "w"), indent=1)
    print(len(clips), "clips,", sum(c["seconds"] for c in clips), "s of video; plan in", f"project{project}.song-plan.json")
    for p in call(s, "GET", f"/projects/{project}/breakdown").get("problems", []):
        print("  problem:", p)


# --- 5. review: frames from every take -----------------------------------------------------
def review(project, out):
    s, rows = site(), []
    os.makedirs(out, exist_ok=True)
    for c in call(s, "GET", f"/projects/{project}/clips"):
        if not c.get("takes"):
            print(c["clip_id"], "has no take yet")
            continue
        take = download(s, c["takes"][-1]["file_id"], f"{out}/{c['clip_id']}-{c['takes'][-1]['file_id']}.mp4")
        d, frames = seconds(take), []
        for i in range(4):
            frames.append(f"{out}/{c['clip_id']}-f{i}.jpg")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(d * (i + .5) / 4), "-i", take, "-frames:v", "1", "-vf",
                            f"scale=180:320,drawtext=text='{c['clip_id']} {d * (i + .5) / 4:.1f}s':x=4:y=4:fontsize=16"
                            ":fontcolor=white:box=1:boxcolor=black@0.6", frames[-1]], check=True)
        rows.append(f"{out}/{c['clip_id']}-row.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", *sum([["-i", f] for f in frames], []),
                        "-filter_complex", "hstack=4", rows[-1]], check=True)
    for p in range(0, len(rows), 5):
        page = rows[p:p + 5]
        subprocess.run(["ffmpeg", "-v", "error", "-y", *sum([["-i", r] for r in page], []), "-filter_complex",
                        f"vstack={len(page)}" if len(page) > 1 else "null", f"{out}/page{p // 5 + 1}.jpg"], check=True)
    print("contact sheets in", out)


# --- 6. the final cut ----------------------------------------------------------------------
def cut(project, song_file, out):
    s, parts = site(), []
    os.makedirs(out, exist_ok=True)
    plan = json.load(open(f"project{project}.song-plan.json"))
    clips = {c["clip_id"]: c for c in call(s, "GET", f"/projects/{project}/clips")}
    for p in plan:
        c = clips[p["clip"]]
        take = download(s, c["takes"][-1]["file_id"], f"{out}/{p['clip']}-{c['takes'][-1]['file_id']}.mp4")
        need = p["end"] - p["start"]
        speed = min(1.0, seconds(take) / need)  # only a take shorter than its piece of the song is slowed
        parts.append(f"{out}/part-{p['clip']}.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", take, "-t", str(need), "-an", "-vf",
                        f"setpts=PTS/{speed},scale=720:1280:force_original_aspect_ratio=decrease,"
                        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
                        "-c:v", "libx264", "-crf", "18", parts[-1]], check=True)
    open(f"{out}/list.txt", "w").write("".join(f"file '{os.path.abspath(x)}'\n" for x in parts))
    end, final = plan[-1]["end"], f"{out}/final.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{out}/list.txt", "-i", song_file,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", f"afade=t=out:st={end - 1.5}:d=1.5",
                    "-c:a", "aac", "-b:a", "192k", "-t", str(end), "-movflags", "+faststart", final], check=True)
    print(final, round(seconds(final), 1), "s")


if __name__ == "__main__":
    steps = {"ref": ref, "song": song, "measure": measure, "retime": retime, "review": review, "cut": cut}
    if len(sys.argv) < 2 or sys.argv[1] not in steps:
        sys.exit(__doc__)
    steps[sys.argv[1]](*sys.argv[2:])
