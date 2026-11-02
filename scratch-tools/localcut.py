"""Local final cut: concat clip files in order at 480p, muting given spans. Usage:
localcut.py out.mp4 dir c1 c2 ... [mute=c1:3.6-4.95 ...]"""
import sys, subprocess
out, d = sys.argv[1], sys.argv[2]
clips=[a for a in sys.argv[3:] if not a.startswith(("mute=","duck="))]
mutes={}
for a in sys.argv[3:]:
    if a.startswith(("mute=","duck=")):
        c,span=a[5:].split(":"); s,e=span.split("-"); mutes.setdefault(c,[]).append((float(s),float(e),0 if a.startswith("mute=") else 0.12))
fc=[]
for n,c in enumerate(clips):
    fc.append(f"[{n}:v]scale=480:854:force_original_aspect_ratio=increase,crop=480:854,fps=30,setsar=1[v{n}]")
    vol="".join(f",volume={v}:enable='between(t,{s},{e})'" for s,e,v in mutes.get(c,[]))
    fc.append(f"[{n}:a]aresample=44100,asetpts=PTS-STARTPTS{vol}[a{n}]")
fc.append("".join(f"[v{n}][a{n}]" for n in range(len(clips)))+f"concat=n={len(clips)}:v=1:a=1[v][a]")
cmd=["ffmpeg","-v","error","-y"]+sum([["-i",f"{d}/{c}.mp4"] for c in clips],[])+["-filter_complex",";".join(fc),"-map","[v]","-map","[a]","-c:v","libx264","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k",out]
subprocess.run(cmd,check=True)
print(out, subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",out],capture_output=True,text=True).stdout.strip())
