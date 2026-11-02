"""Split clips, set per-shot screens, and swap words in a breakdown. restructure.py spec.json"""
import sys, json, math; sys.path.insert(0,'.')
from bs import call
spec=json.load(open(sys.argv[1])); pid=spec["pid"]
bd=call("GET",f"/projects/{pid}/breakdown")["breakdown"]
shots={s["id"]:s for sc in bd["scenes"] for s in sc["shots"]}
for sid,scr in spec.get("screens",{}).items(): shots[sid]["screen_ids"]=scr
for sid,pairs in spec.get("text",{}).items():
    for a,b in pairs:
        assert a in shots[sid]["action"], (sid,a); shots[sid]["action"]=shots[sid]["action"].replace(a,b)
for sid,act in spec.get("action",{}).items(): shots[sid]["action"]=act
if spec.get("clips"):
    old={c["id"]:c for c in bd["clips"]}; tmpl=dict(bd["clips"][0]); clips=[]
    for i,(ids,seam) in enumerate(spec["clips"]):
        c=dict(tmpl); c.update(id=f"c{i+1}",shot_ids=ids,seconds=max(4,math.ceil(sum(shots[s]["seconds"] for s in ids))),seam=seam)
        clips.append(c)
    bd["clips"]=clips
r=call("PUT",f"/projects/{pid}/breakdown",bd)
print(pid,"problems:",json.dumps(r.get("problems"))[:1500])
print([(c["id"],c["seconds"],len(c["shot_ids"])) for c in bd["clips"]], sum(c["seconds"] for c in bd["clips"]))
