"""Generate a take for each named clip (or all), retrying refusals/busy (not charged), then download."""
import sys, json, time, os; sys.path.insert(0,'.')
from bs import call, wait_job, download
pid=int(sys.argv[1]); only=set(sys.argv[2:])
clips=[c for c in call("GET",f"/projects/{pid}/clips") if not only or c["clip_id"] in only]
pending={c["clip_id"]:c for c in clips}; tries={k:0 for k in pending}; jobs={}
def submit(c):
    for n in range(4):
        try: return call("POST",f"/projects/{pid}/clips/{c['id']}/generate",{})["id"]
        except SystemExit as e: print("submit err", c["clip_id"], str(e)[:200], flush=True); time.sleep(15)
for k,c in pending.items():
    jid=submit(c); tries[k]=1
    if jid: jobs[k]=jid
os.makedirs(f"tk{pid}",exist_ok=True)
while jobs:
    for k,jid in list(jobs.items()):
        j=call("GET",f"/jobs/{jid}")
        if j["status"] in ("queued","running"): continue
        print(k, j["status"], round(j.get("credits") or 0,2), (j.get("error") or "")[:240], flush=True)
        del jobs[k]
        if j["status"]!="succeeded" and tries[k]<int(os.environ.get("TRIES","4")):
            tries[k]+=1; time.sleep(10); jid=submit(pending[k])
            if jid: jobs[k]=jid
    time.sleep(15)
for c in call("GET",f"/projects/{pid}/clips"):
    if (not only or c["clip_id"] in only) and c["takes"]:
        t=c["takes"][-1]; download(t["file_id"], f"tk{pid}/{c['clip_id']}.mp4"); print("got", c["clip_id"], len(c["takes"]), "takes", flush=True)
print("ALL DONE", flush=True)
