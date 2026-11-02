import sys, json, time, os; sys.path.insert(0,'.')
from bs import call, wait_job, download
from PIL import Image, ImageDraw
pid=int(sys.argv[1]); only=sys.argv[2:] 
fr=call("GET",f"/projects/{pid}/storyboard")
jobs={}
for f in fr:
    if only and str(f["id"]) not in only: continue
    for n in range(3):
        try: jobs[f["id"]]=call("POST",f"/projects/{pid}/storyboard/frames/{f['id']}/render",{})["id"]; break
        except SystemExit as e: print("render err",f["id"],e); time.sleep(15)
for fid,jid in jobs.items():
    j=wait_job(jid); print(fid, j["status"], (j.get("error") or "")[:200])
fr=call("GET",f"/projects/{pid}/storyboard"); os.makedirs(f"st{pid}",exist_ok=True)
tiles=[]
for f in fr:
    fid=f.get("file_id") or (f.get("image") or {}).get("file_id")
    if not fid: print("no image", f["id"], list(f.keys())); continue
    p=f"st{pid}/{f['clip_id']}.jpg"; download(fid,p)
    im=Image.open(p).convert("RGB"); im.thumbnail((360,640)); d=ImageDraw.Draw(im); d.rectangle((0,0,60,22),fill="black"); d.text((4,4),f["clip_id"],fill="white"); tiles.append(im)
W=sum(t.width for t in tiles); H=max(t.height for t in tiles); out=Image.new("RGB",(W,H),"white"); x=0
for t in tiles: out.paste(t,(x,0)); x+=t.width
out.save(f"st{pid}/sheet.jpg",quality=85)
