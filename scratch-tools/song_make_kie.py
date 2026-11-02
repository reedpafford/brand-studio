import json, os, time, urllib.request
K="https://api.kie.ai/api/v1"; H={"Authorization":"Bearer "+os.environ["KIE_API_KEY"],"content-type":"application/json"}
def get(p): return json.load(urllib.request.urlopen(urllib.request.Request(K+p,headers=H),timeout=60))
STYLE="slow soulful R&B ballad, emotional piano and soft strings, warm raspy young male vocal, 72 BPM, heartfelt, gentle drums entering at the chorus, every line sung, vocals start immediately, no instrumental intro, tight 6-second soft piano outro at the end"
songs={
"ComingUp":("We Ain't Broke No More","""[Intro: vocals start immediately]
[Verse]
Mama worked the night shift, I'd hear her keys at dawn,
shoes by the door and the lights cut off,
eviction on the fridge, she said "baby, we'll be fine,"
I said one day I'ma pay you back for all that time.

[Pre-Chorus]
Studied on the bus ride, lost more than I won,
three a.m. on FOMO till I saw the sun.

[Chorus]
Now we're comin' up, comin' up slow,
every red day taught me what I know,
Mama, put your feet up, you don't gotta go,
we ain't broke no more, we ain't broke no more.

[Outro]
Keys in her hand and the tears on her face,
we ain't broke no more.

[Instrumental outro, 6 seconds]""")}
log={}
for key,(title,lyrics) in songs.items():
    req={"model":"ai-music-api/generate","callBackUrl":"https://example.com/cb","input":{"custom_mode":True,"instrumental":False,"title":title,"lyrics":lyrics,"style":STYLE,"negative_tags":"female vocal, rap, long instrumental intro, spoken word, long outro, upbeat","vocal_gender":"m","model":"V6"}}
    before=get("/chat/credit")["data"]
    tid=json.load(urllib.request.urlopen(urllib.request.Request(K+"/jobs/createTask",json.dumps(req).encode(),H),timeout=60))["data"]["taskId"]
    for _ in range(90):
        info=get(f"/jobs/recordInfo?taskId={tid}")["data"]
        if info.get("state") in ("success","fail"): break
        time.sleep(10)
    d=json.loads(info.get("resultJson") or "{}").get("data",[])
    for i,x in enumerate(d):
        open(f"{key}-take{i+1}.mp3","wb").write(urllib.request.urlopen(x["audio_url"],timeout=120).read()); print(key,i+1,x["duration"])
    after=get("/chat/credit")["data"]; log[key]={"task":tid,"state":info.get("state"),"before":before,"after":after}; print(log[key])
json.dump(log,open("log.json","w"),indent=1)
