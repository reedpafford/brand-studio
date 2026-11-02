"""Static fomo coin page (real UI, big fomo header with the eyes) whose big number is the
position value and whose chart climbs to it. Usage: make_val.py VALUE GAINLINE seed out.png"""
import sys, random, os
from PIL import Image, ImageDraw, ImageFont
D=os.path.dirname(os.path.abspath(__file__)); F='/usr/share/fonts/opentype/inter/'
val,gain,seed,out=sys.argv[1],sys.argv[2],int(sys.argv[3]),sys.argv[4]
BG=(6,5,15); GREEN=(87,200,96)
base=Image.open(f'{D}/s14.png').convert('RGB'); W,H=base.size; d=ImageDraw.Draw(base)
d.rectangle((0,96,W,640),fill=BG)
d.text((24,104),val,font=ImageFont.truetype(F+'Inter-SemiBold.otf',60),fill=(255,255,255))
d.text((26,184),'▲ '+gain+'  1h',font=ImageFont.truetype(F+'Inter-Medium.otf',26),fill=GREEN)
random.seed(seed); n=80; s=[]; j=0
for i in range(n):
    if i%3==0: j=random.uniform(-0.05,0.05)
    s.append((i/(n-1))**1.6+j)
lo,hi=min(s)-0.05,max(s)+0.08; y0,y1=270,620
pts=[(int(8+(W-120)*i/(n-1)),int(y1-(v-lo)/(hi-lo)*(y1-y0))) for i,v in enumerate(s)]
d.line(pts,fill=GREEN,width=5,joint='curve'); x,y=pts[-1]
d.ellipse((x-14,y-14,x+14,y+14),outline=GREEN,width=3); d.ellipse((x-8,y-8,x+8,y+8),fill=GREEN)
HD=120; logo=Image.open('/home/user/brand-studio/assets/brands/fomo/logo.png').convert('RGBA').resize((92,92)); px=logo.load()
for yy in range(92):
    for xx in range(92):
        r,g,b,a=px[xx,yy]
        if r+g+b<150: px[xx,yy]=(r,g,b,0)
page=Image.new('RGB',(W,H+HD),BG); hd=ImageDraw.Draw(page); wm=ImageFont.truetype(F+'Inter-Bold.otf',60)
tw=hd.textlength('fomo',font=wm); x0=int((W-(92+14+tw))/2)
page.paste(logo,(x0,14),logo); hd.text((x0+106,20),'fomo',font=wm,fill=(232,234,255)); hd.line((24,HD-2,W-24,HD-2),fill=(30,30,42),width=2)
page.paste(base,(0,HD)); page.save(out); print(out)
