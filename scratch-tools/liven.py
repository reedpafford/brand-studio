import sys, re; sys.path.insert(0,'.')
from fixlib import *
pid=int(sys.argv[1])
for k,c in clips(pid).items():
    p=c["prompt"].replace("locked-off cinematic framing","dynamic, always-moving cinematic camera").replace("mostly locked off","always moving")
    reds=[l[:100] for l in p.split("\n") if l.startswith("Shot") and re.search(r"\b(red|dips|dive|loss|losing)\b",l,re.I) and "fomo" in l.lower()]
    if reds: print("CHECK RED", k, reds)
    if p!=c["prompt"]: put(pid,c,p)
