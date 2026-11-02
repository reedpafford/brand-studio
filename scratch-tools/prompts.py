import sys, time; sys.path.insert(0,'.')
from bs import call, wait_job
import subprocess
pid=int(sys.argv[1])
call("POST",f"/projects/{pid}/storyboard/approve-all")
j=call("POST",f"/projects/{pid}/clips/prompts",{}); print(wait_job(j["id"])["status"])
cl=call("GET",f"/projects/{pid}/clips")
for c in cl:
    if c.get("problems"):
        p=c["prompt"].split("\n")
        # common fix: the audio line must start "Audio: only the spoken lines and"
        p0=p[0].replace("Audio: only the spoken lines, ","Audio: only the spoken lines and ")
        p[0]=p0; p[-1]=p0
        r=call("PUT",f"/projects/{pid}/clips/{c['id']}",{"prompt":"\n".join(p),"references":c["references"]})
        print(c["clip_id"], c["problems"], "->", r.get("problems"))
subprocess.run([sys.executable,"-I","fomo_say.py",str(pid)])
for c in call("GET",f"/projects/{pid}/clips"): print(c["clip_id"], c["seconds"], c.get("problems"))
