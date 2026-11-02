import sys, re; sys.path.insert(0,'.')
from fixlib import *
pid=int(sys.argv[1])
for k,c in clips(pid).items():
    p=c["prompt"]
    if any("word for word" in x for x in (c.get("problems") or [])):
        alt=re.sub(r'(: ")([^"]*)(")', lambda m: m.group(1)+(m.group(2).replace("FOMO","fomo") if "FOMO" in m.group(2) else m.group(2).replace("fomo","FOMO"))+m.group(3), p)
        put(pid,c,alt)
    elif c.get("problems"):
        L=p.split("\n"); a=re.sub(r"^Audio: only the spoken lines?,? (and )?","Audio: only the spoken lines and ",L[0]).replace("no one speaks (no dialogue, narration or words)","no one speaks (no voices, narration or dialogue)"); L[0]=a; L[-1]=a
        put(pid,c,"\n".join(L))
    if "invented trading screen" in c["prompt"]: print("INVENTED",pid,k)
for c in call("GET",f"/projects/{pid}/clips"):
    if c.get("problems"): print("STILL",pid,c["clip_id"],c["problems"])
