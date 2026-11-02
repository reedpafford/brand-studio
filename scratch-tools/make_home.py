"""Rich Home screen from the real UI with any balance. make_home.py "$612,300.00" "+$88,410.52 (16.9%)" out.png"""
import sys
from PIL import Image, ImageDraw, ImageFont
F='/usr/share/fonts/opentype/inter/'
bal,gain,out=sys.argv[1:4]
im=Image.open('/home/user/brand-studio/assets/brands/fomo/screens/home-rich.png').convert('RGB'); d=ImageDraw.Draw(im)
bg=im.getpixel((420,240))
d.rectangle((26,126,445,230),fill=bg)
d.text((28,138),bal,font=ImageFont.truetype(F+'Inter-Bold.otf',48),fill=(255,255,255))
f2=ImageFont.truetype(F+'Inter-Medium.otf',24); d.text((30,198),gain,font=f2,fill=(76,175,80))
d.text((30+d.textlength(gain,font=f2)+8,198),'24h',font=f2,fill=(140,140,150))
im.save(out); print(out)
