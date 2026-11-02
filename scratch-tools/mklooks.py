import sys, time; sys.path.insert(0,'.')
from bs import call, download
from PIL import Image
pid=int(sys.argv[1])
m=call("GET",f"/projects/{pid}/assets/missing-looks"); print(m)
if m["slot_ids"]: call("POST",f"/projects/{pid}/assets/make-missing",{})
time.sleep(20)
for _ in range(80):
    a=call("GET",f"/projects/{pid}/assets")
    if not any(x.get("sheet_status")=="drawing" for x in a): break
    time.sleep(10)
ims=[]
for x in a:
    if x["kind"]=="character" and x.get("only_here"):
        f=f"look_{pid}_{x['slot_id']}.jpg"; download(x["sheet_file_id"],f); print(x["role"],x["sheet_status"]); 
        i=Image.open(f).convert("RGB"); ims.append(i.resize((int(i.width*600/i.height),600)))
o=Image.new("RGB",(sum(i.width for i in ims),600)); X=0
for i in ims: o.paste(i,(X,0)); X+=i.width
o.save(f"looks{pid}.jpg")
