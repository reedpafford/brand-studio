"""Local cut for a song video: fit each clip's newest take to its window in the song, song as the
only sound, then the last (spoken) clip with its own voice over the song's instrumental, which keeps playing
underneath (lowered) and fades out at the end."""
import sys, json, subprocess, os; sys.path.insert(0,'.')
from bs import call, download
pid=int(sys.argv[1]); song=sys.argv[2]; windows=json.loads(sys.argv[3]); out=sys.argv[4]
picks=dict(a.split(":") for a in sys.argv[5:])
os.makedirs(f"cut{pid}",exist_ok=True)
cl=sorted(call("GET",f"/projects/{pid}/clips"),key=lambda c:int(c["clip_id"][1:]))
files=[]
for c in cl:
    i=int(picks.get(c["clip_id"],len(c["takes"])))-1
    p=f"cut{pid}/{c['clip_id']}.mp4"; download(c["takes"][i]["file_id"],p)
    cut=dict(x.split(":") for x in os.environ.get("CUT","").split(",") if x).get(c["clip_id"])
    if cut:
        a,b=cut.split("-"); q=p.replace(".mp4","_cut.mp4")
        subprocess.run(["ffmpeg","-v","error","-y","-i",p,"-vf",f"select='not(between(t,{a},{b}))',setpts=N/FRAME_RATE/TB","-af",f"aselect='not(between(t,{a},{b}))',asetpts=N/SR/TB",q],check=True); p=q
    files.append(p)
dur=lambda f: float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f],capture_output=True,text=True).stdout)
song_end=windows[-1][1]
parts=[]; fc=[]
for n,(f,(a,b)) in enumerate(zip(files[:-1],windows)):
    d=dur(f); fac=(b-a)/d
    fc.append(f"[{n}:v]setpts={fac:.5f}*PTS,scale=480:854,fps=30,setsar=1[v{n}]")
last=len(files)-1
fc.append(f"[{last}:v]scale=480:854,fps=30,setsar=1[v{last}]")
fc.append("".join(f"[v{n}]" for n in range(len(files)))+f"concat=n={len(files)}:v=1:a=0[v]")
si=len(files)
ld=dur(files[last]); total=song_end+ld
fc.append(f"[{si}:a]atrim=0:{total},asetpts=PTS-STARTPTS,aresample=44100,volume='if(lt(t,{song_end}),1,0.35)':eval=frame,afade=t=out:st={total-1.2}:d=1.2[sa]")
fc.append(f"[{last}:a]aresample=44100,asetpts=PTS-STARTPTS,adelay={int(song_end*1000)}:all=1,volume=1.6[la]")
fc.append("[sa][la]amix=inputs=2:duration=first:normalize=0[a]")
cmd=["ffmpeg","-v","error","-y"]+sum([["-i",f] for f in files],[])+["-i",song,"-filter_complex",";".join(fc),"-map","[v]","-map","[a]","-c:v","libx264","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k",out]
subprocess.run(cmd,check=True); print(out, dur(out))
