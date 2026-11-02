"""Custom fomo coin page from the real token screen: character face as the coin icon,
coin name, and a big fomo header with the eyes logo. Usage: make_coin.py face.jpg "NAME" TICKER out.png [price] [mcap]"""
import sys
from PIL import Image, ImageDraw, ImageFont
F='/usr/share/fonts/opentype/inter/'
face_path,name,ticker,out=sys.argv[1:5]
price=sys.argv[5] if len(sys.argv)>5 else None
base=Image.open('/home/user/brand-studio/assets/brands/fomo/screens/token-up.png').convert('RGB')
W=base.width; bg=(6,5,15); d=ImageDraw.Draw(base)
badge=base.crop((252,24,322,58))                     # the chain + platform badges
d.rectangle((70,12,330,92),fill=bg)                   # clear icon, title, ticker, badges
# coin icon: the character's face in a circle, with a teal ring
face=Image.open(face_path).convert('RGB'); s=min(face.size); face=face.crop(((face.width-s)//2,0,(face.width-s)//2+s,s)).resize((76,76))
m=Image.new('L',(76,76),0); ImageDraw.Draw(m).ellipse((0,0,75,75),fill=255)
d.ellipse((68,12,148,92),fill=(43,101,120)); base.paste(face,(70,14),m)
v=Image.open('/home/user/brand-studio/assets/brands/fomo/screens/token-up.png').convert('RGB').crop((120,64,152,96)); base.paste(v,(120,64))  # verified tick
f=ImageFont.truetype(F+'Inter-SemiBold.otf',24); d.text((162,24),name,font=f,fill=(255,255,255))
x=int(d.textlength(name,font=f))+170; base.paste(badge,(x,24))
d.text((162,63),ticker,font=ImageFont.truetype(F+'Inter-Medium.otf',19),fill=(182,184,192))
if price:
    gain=sys.argv[6] if len(sys.argv)>6 else '+241%'
    d.rectangle((14,92,400,200),fill=bg); d.text((22,104),price,font=ImageFont.truetype(F+'Inter-SemiBold.otf',38),fill=(255,255,255))
    d.text((24,166),'▲ '+gain+'  1h',font=ImageFont.truetype(F+'Inter-Medium.otf',19),fill=(87,200,96))
    pill=base.getpixel((560,280)); d.rounded_rectangle((514,266,596,292),radius=6,fill=pill); d.text((555,279),price,font=ImageFont.truetype(F+'Inter-SemiBold.otf',15),fill=(255,255,255),anchor='mm')
# team holdings ticker
card=base.getpixel((420,883)); d.rectangle((314,870,385,897),fill=card); d.text((316,872),ticker,font=ImageFont.truetype(F+'Inter-Medium.otf',17),fill=(84,87,93))
# big fomo header with the eyes
H=120; out_im=Image.new('RGB',(W,base.height+H),bg)
logo=Image.open('/home/user/brand-studio/assets/brands/fomo/logo.png').convert('RGBA').resize((92,92))
px=logo.load()
for yy in range(92):
    for xx in range(92):
        r,g,b,a=px[xx,yy]
        if r+g+b<150: px[xx,yy]=(r,g,b,0)
wm=ImageFont.truetype(F+'Inter-Bold.otf',60); hd=ImageDraw.Draw(out_im)
tw=hd.textlength('fomo',font=wm); x0=int((W-(92+14+tw))/2)
out_im.paste(logo,(x0,14),logo); hd.text((x0+106,20),'fomo',font=wm,fill=(232,234,255))
hd.line((24,H-2,W-24,H-2),fill=(30,30,42),width=2)
out_im.paste(base,(0,H)); out_im.save(out); print(out, out_im.size)
