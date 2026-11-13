"""Make Movie Ad 1 (RP5) through the site: Seedream 5.5 sheets and Seedance 2.5 clips on KIE.
Everything is resumable (state.json): nothing is asked for twice, so nothing is paid twice.
  python3 film.py cast              create the eight people and ask Seedream for their sheets
  python3 film.py sheets            wait for the sheets, save them here to look at
  python3 film.py approve [names]   approve the sheets (all, or those named)
  python3 film.py redo <name>       ask for one person's sheet again
  python3 film.py file <key> <path|file id>   register a picture (a place, the van) by file
  python3 film.py show <clip>       free: the words and pictures a clip would send, and its price
  python3 film.py film <clips...>   paid: make the clips, at most CAP dollars in all (env CAP)
  python3 film.py spent             what the clips have cost so far
"""
import json, os, subprocess, sys, time
sys.path.insert(0, "/Users/reedpafford/BrandStudio-Footage/_tools/upload")
sys.path.insert(0, "/Users/reedpafford/conductor/workspaces/brand-studio/skopje/.context/night")
sys.path.insert(0, "/Users/reedpafford/conductor/workspaces/brand-studio/skopje/.context/pgtest")
import bsapi, bs
import plan

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = f"{HERE}/state.json"
MODEL, RES, RATE = "seedance-2.5-kie", "480p", 0.14
JSON = {"Content-Type": "application/json"}


def load():
    return json.load(open(STATE)) if os.path.exists(STATE) else {"cast": {}, "files": {}, "clips": {}}


def save(s):
    json.dump(s, open(STATE, "w"), indent=1)


def get(path):
    """A read that waits out a dropped connection (a long run must not die on one)."""
    for n in range(30):
        try:
            return bsapi.get(path)
        except OSError:
            time.sleep(10)
    raise SystemExit(f"the site did not answer: {path}")


def post(path, body=None):
    return bsapi.req("POST", path, json.dumps(body or {}).encode(), JSON)


def wait(job):
    while True:
        d = bsapi.get(f"/jobs/{job}/detail")[1]
        if d["status"] not in ("queued", "running"):
            return d
        time.sleep(8)


def references(key, s):
    """(character ids, prop ids, file ids, tags): pictures in the order the site attaches them
    (people, then the product, then plain files), and each one's [ImageN]."""
    chars, props, files, tags, n = [], [], [], {}, 0
    refs = plan.CLIPS[key]["refs"]
    if "alarm" in refs:
        props.append(plan.ALARM); n += 1; tags["alarm"] = f"[Image{n}]"
    for r in refs:  # a person goes as the file of their large-face sheet: the site's own look
        if r != "alarm":  # check redrew each saved sheet as three small full-body views
            files.append(s["cast"][r]["face_sheet"] if r in plan.CAST else s["files"][r])
            n += 1; tags[r] = f"[Image{n}]"
    return chars, props, files, tags


def body(key, s):
    chars, props, files, tags = references(key, s)
    words = plan.prompt(key, tags)
    heard = [v for v in plan.CLIPS[key]["voices"] if v in s.get("voices", {})]
    for n, v in enumerate(heard, 1):  # a sample of a voice from an earlier clip, to keep it theirs
        files.append(s["voices"][v])
        words += (f"\n[Audio{n}] is a recording of {plan.WHO[v]}'s voice: match its tone and accent for "
                  f"{plan.WHO[v]} only. The words in it are not said in this clip.")
    return {"brand_id": plan.BRAND, "model_id": MODEL, "prompt": words,
            "improved": False, "aspect_ratio": "9:16", "duration": plan.CLIPS[key]["seconds"],
            "resolution": RES, "generate_audio": True, "character_ids": chars, "prop_ids": props,
            "file_ids": files, "skip_screen_ids": [15]}


def spent(s):
    return sum(t.get("cost") or 0 for c in s["clips"].values() for t in c.get("tries", [])
               if t["status"] == "succeeded")  # a clip that never started cost nothing


cmd, *a = sys.argv[1:]
s = load()
if cmd == "cast":
    for key, (name, notes) in plan.CAST.items():
        c = s["cast"].setdefault(key, {})
        if "id" not in c:
            code, d = post("/library/character", {"name": name, "notes": notes, "brand_ids": [plan.BRAND]})
            if code != 201:
                sys.exit(f"{key}: could not create: {code} {str(d)[:300]}")
            c["id"] = d["id"]; save(s)
        if "job" not in c:
            code, d = post(f"/library/character/{c['id']}/sheet", {"model_id": "seedream-5.5"})
            print(key, c["id"], code, d.get("id") if code == 201 else str(d)[:300], flush=True)
            if code == 201:
                c["job"] = d["id"]; save(s)
elif cmd == "redo":
    c = s["cast"][a[0]]
    code, d = post(f"/library/character/{c['id']}/sheet", {"model_id": "seedream-5.5"})
    print(a[0], code, d.get("id") if code == 201 else str(d)[:300])
    if code == 201:
        c["job"] = d["id"]; c.pop("file", None); save(s)
elif cmd == "sheets":
    for key, c in s["cast"].items():
        if c.get("file") or "job" not in c:
            continue
        d = wait(c["job"])
        print(key, d["status"], d.get("cost_usd"), d.get("provider"), (d.get("error") or "")[:200], flush=True)
        if d["status"] == "succeeded":
            item = bsapi.get(f"/library/character/{c['id']}")[1]
            c["file"] = item.get("sheet_file_id"); c["cost"] = d.get("cost_usd"); save(s)
            bs.raw(f"/files/{c['file']}", f"{HERE}/sheet-{key}.png")
elif cmd == "approve":
    for key in a or list(s["cast"]):
        code, d = post(f"/library/character/{s['cast'][key]['id']}/sheet/approve")
        print(key, code, d.get("sheet_approved") if code == 200 else str(d)[:200])
elif cmd == "file":
    if a[1].isdigit():
        s["files"][a[0]] = int(a[1])
    else:
        import bsupload
        s["files"][a[0]] = bsupload.upload(a[1])
    save(s); print(a[0], s["files"][a[0]])
elif cmd == "voice":  # voice <who> <clip> <from s> <to s>: a sample cut from a made clip
    import bsupload
    who, key, a0, a1 = a
    src = [t for t in s["clips"][key]["tries"] if t["status"] == "succeeded"][-1]["path"]
    out = f"{HERE}/clips/voice-{who}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", a0, "-to", a1, "-i", src, "-ac", "1", "-ar", "44100", out], check=True)
    s.setdefault("voices", {})[who] = bsupload.upload(out); save(s); print(who, s["voices"][who])
elif cmd == "show":
    b = body(a[0], s)
    print(b["prompt"]); print({k: v for k, v in b.items() if k != "prompt"})
    print(post("/clips/estimate", b))
elif cmd == "spent":
    for k, c in s["clips"].items():
        print(k, [(t["job"], t["status"], t.get("cost")) for t in c.get("tries", [])])
    print("clips so far: $%.2f" % spent(s))
elif cmd == "film":
    cap, par = float(os.environ.get("CAP", "70")), int(os.environ.get("PAR", "3"))
    todo, running = list(a), {}
    os.makedirs(f"{HERE}/clips", exist_ok=True)
    for key, c in s["clips"].items():  # a run that was cut off: its clips are still being made
        for t in c["tries"]:
            if t["status"] == "running":
                running[key] = t
    while todo or running:
        while todo and len(running) < par:
            key = todo.pop(0)
            c = s["clips"].setdefault(key, {"tries": []})
            if any(t["status"] in ("succeeded", "running") for t in c["tries"]) and key not in os.environ.get("AGAIN", "").split(","):
                print(key, "already made or being made; AGAIN=<clip> to make another take"); continue
            price = plan.CLIPS[key]["seconds"] * RATE
            owed = sum(plan.CLIPS[k]["seconds"] * RATE for k in running)
            if spent(s) + owed + price > cap:
                print(f"{key}: not started, ${spent(s) + owed:.2f} spent or under way and this clip is ${price:.2f}: over the ${cap:.0f} limit")
                todo = []; break
            code, d = post("/clips", body(key, s))
            if code != 201:
                print(key, "not started:", code, str(d)[:300]); continue
            t = {"job": d["id"], "status": "running"}; c["tries"].append(t); save(s)
            running[key] = t
            print(time.strftime("%H:%M", time.gmtime()), key, "started, job", d["id"], flush=True)
            time.sleep(3)
        time.sleep(10)
        for key, t in list(running.items()):
            d = get(f"/jobs/{t['job']}/detail")[1]
            if d["status"] in ("queued", "running"):
                continue
            del running[key]
            t["status"], t["cost"] = d["status"], d.get("cost_usd") or 0
            t["error"] = (d.get("error") or "")[:300]
            if d["status"] == "succeeded":
                n = len([x for x in s["clips"][key]["tries"] if x["status"] == "succeeded"])
                t["file"] = d["output"]["file_ids"][0]
                t["path"] = f"{HERE}/clips/{key}" + ("" if n == 1 else f"-take{n}") + ".mp4"
                bs.raw(f"/files/{t['file']}", t["path"])
            save(s)
            print(time.strftime("%H:%M", time.gmtime()), key, t["status"], "cost", t["cost"], t["error"][:160],
                  "| total $%.2f" % spent(s), flush=True)
