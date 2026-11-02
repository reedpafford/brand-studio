"""Tiny client for the live Brand Studio API (cookie from ../cj.txt; never prints secrets)."""
import json, os, sys, time, http.cookiejar, urllib.request, urllib.error
B = os.environ.get("BS_SITE", "https://srv2091584.hstgr.cloud") + "/api"
HERE = os.path.dirname(os.path.abspath(__file__))
_cj = http.cookiejar.MozillaCookieJar(os.path.join(HERE, "..", "cj.txt"))
_cj.load(ignore_discard=True, ignore_expires=True)
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))

def call(method, path, body=None, raw=False, ok=(200, 201, 204), tries=6):
    data = json.dumps(body).encode() if body is not None else None
    for n in range(tries):
        req = urllib.request.Request(B + path, data, {"content-type": "application/json"}, method=method)
        try:
            with _op.open(req, timeout=120) as r:
                b = r.read()
                return b if raw else (json.loads(b) if b else None)
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:800]
            if e.code in (502, 503, 504) and n < tries - 1:
                time.sleep(10 * (n + 1)); continue
            raise SystemExit(f"{method} {path} -> {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if n < tries - 1: time.sleep(10 * (n + 1)); continue
            raise

def wait_job(jid, every=8, limit=1800):
    t0 = time.time()
    while True:
        j = call("GET", f"/jobs/{jid}")
        if j.get("status") in ("succeeded", "failed", "cancelled", "needs_owner_approval"):
            return j
        if time.time() - t0 > limit: return j
        time.sleep(every)

def download(file_id, path):
    data = call("GET", f"/files/{file_id}", raw=True)
    open(path + ".part", "wb").write(data); os.replace(path + ".part", path)

def ids(): 
    p = os.path.join(HERE, "ids.json")
    return json.load(open(p)) if os.path.exists(p) else {}

def save_ids(d): json.dump(d, open(os.path.join(HERE, "ids.json"), "w"), indent=1)

if __name__ == "__main__":
    m, p = sys.argv[1], sys.argv[2]
    body = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    print(json.dumps(call(m, p, body), indent=1)[:6000])
