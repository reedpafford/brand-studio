import sys, json, time; sys.path.insert(0,'.')
from bs import call, download
pid, fid, note = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
print("price", call("GET",f"/projects/{pid}/storyboard/frames/{fid}/change"))
before=[x for x in call("GET",f"/projects/{pid}/storyboard") if x["id"]==fid][0]["file_id"]
call("POST",f"/projects/{pid}/storyboard/frames/{fid}/change",{"note":note})
time.sleep(20)
for _ in range(120):
    f=[x for x in call("GET",f"/projects/{pid}/storyboard") if x["id"]==fid][0]
    if f["file_id"]!=before and (f.get("change") or {}).get("status") in (None,"done"): break
    time.sleep(8)
download(f["file_id"], f"st{pid}/{f['clip_id']}.jpg"); print("done", f["clip_id"])
