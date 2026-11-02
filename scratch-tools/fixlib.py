import re, sys; sys.path.insert(0,'.')
from bs import call
def setshot(p, n, text):
    L=p.split("\n"); i=[k for k,l in enumerate(L) if l.startswith(f"Shot {n} |")][0]
    t=re.match(r"Shot \d+ \| [\d-]+ s\. ",L[i]).group(0); L[i]=t+text; return "\n".join(L)
def keep_add(p, extra):
    L=p.split("\n"); i=[k for k,l in enumerate(L) if l.startswith("Keep: ")][0]; L[i]=L[i].rstrip(".")+"; "+extra+"."; return "\n".join(L)
def flash_open(p):
    L=p.split("\n"); i=[k for k,l in enumerate(L) if l.startswith("Shot 1 |")][0]
    if "white flash" not in L[i]: L[i]=re.sub(r"^(Shot 1 \| [\d-]+ s\. )", r"\1Opens on a bright white flash that fades in (a time jump). ", L[i])
    return "\n".join(L)
def put(pid, c, p):
    r=call("PUT",f"/projects/{pid}/clips/{c['id']}",{"prompt":p,"references":c["references"]}); print(c["clip_id"], r.get("problems")); return r
def clips(pid): return {c["clip_id"]:c for c in call("GET",f"/projects/{pid}/clips")}
WINS="every fomo screen shows green gains only, never red or a loss"
